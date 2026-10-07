#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Refresh competitive skill metrics for open-edge-platform vs NVIDIA catalogs.

Reads the job taxonomy CSV, inventories both skill catalogs, recomputes
coverage / depth / granularity aggregates, and patches the scorecard doc.

Examples:
  python refresh_scorecard.py
  python refresh_scorecard.py --nvidia-clone /tmp/nvidia-skills --write-docs
  python refresh_scorecard.py --check-only
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

META_SKILLS = frozenset({"competitive-skill-metrics"})
NVIDIA_README_CANDIDATES = (
    "https://raw.githubusercontent.com/NVIDIA/skills/main/README.md",
    "https://api.github.com/repos/NVIDIA/skills/readme",  # needs Accept header
)
NVIDIA_OVERLAP_PRODUCTS = frozenset(
    {
        "Video Search and Summarization",
        "DeepStream",
        "RAG Blueprint",
        "Physical AI",
        "Physical AI Augmentation",
        "Physical AI Auto-Labeling",
        "Physical AI Orchestration",
        "TAO Toolkit",
        "Holoscan SDK",
        "HoloHub",
        "Jetson Device",
        "Isaac for Healthcare Workflows",
        "NeMo Retriever",
        "Medical AI Skills",
        "AIQ",
        "Nemotron",
    }
)

BEGIN_SNAPSHOT = "<!-- BEGIN GENERATED:SNAPSHOT -->"
END_SNAPSHOT = "<!-- END GENERATED:SNAPSHOT -->"
BEGIN_SCORECARD = "<!-- BEGIN GENERATED:SCORECARD -->"
END_SCORECARD = "<!-- END GENERATED:SCORECARD -->"
BEGIN_AGGREGATES = "<!-- BEGIN GENERATED:AGGREGATES -->"
END_AGGREGATES = "<!-- END GENERATED:AGGREGATES -->"
BEGIN_DRIFT = "<!-- BEGIN GENERATED:DRIFT -->"
END_DRIFT = "<!-- END GENERATED:DRIFT -->"


@dataclass
class SkillDepth:
    name: str
    words: int
    files: int
    refs: int
    description: str = ""

    @property
    def thin(self) -> bool:
        return self.words < 400 and self.refs == 0

    @property
    def meets_depth_floor(self) -> bool:
        return self.words >= 500 or self.refs > 0


@dataclass
class CatalogInventory:
    source: str
    products: int
    skills: list[str]
    by_product: dict[str, list[str]] = field(default_factory=dict)
    depth: dict[str, SkillDepth] = field(default_factory=dict)


@dataclass
class DriftReport:
    unmapped_oep_skills: list[str] = field(default_factory=list)
    stale_oep_refs: list[str] = field(default_factory=list)
    stale_nvidia_refs: list[str] = field(default_factory=list)
    unmapped_nvidia_overlap: list[str] = field(default_factory=list)
    new_oep_since_csv: list[str] = field(default_factory=list)


def repo_root_from_script() -> Path:
    # .../.agents/skills/competitive-skill-metrics/scripts/refresh_scorecard.py
    return Path(__file__).resolve().parents[4]


def parse_args() -> argparse.Namespace:
    root = repo_root_from_script()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", type=Path, default=root, help="open-edge-platform/skills checkout")
    p.add_argument(
        "--job-catalog",
        type=Path,
        default=None,
        help="Path to job-catalog.csv (default: <repo>/docs/data/job-catalog.csv)",
    )
    p.add_argument(
        "--docs",
        type=Path,
        default=None,
        help="Path to competitive-skill-metrics.md",
    )
    p.add_argument(
        "--oep-skills-dir",
        type=Path,
        default=None,
        help="OEP installed skills dir (default: <repo>/.agents/skills)",
    )
    p.add_argument(
        "--nvidia-readme",
        type=Path,
        default=None,
        help="Local NVIDIA README.md (skips network fetch)",
    )
    p.add_argument(
        "--nvidia-clone",
        type=Path,
        default=None,
        help="Local NVIDIA/skills clone for per-skill depth stats",
    )
    p.add_argument(
        "--fetch-nvidia",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fetch NVIDIA README from GitHub when --nvidia-readme not set",
    )
    p.add_argument(
        "--clone-nvidia-depth",
        action="store_true",
        help="Shallow-clone NVIDIA/skills into a temp dir to compute depth (network + disk)",
    )
    p.add_argument("--write-docs", action="store_true", help="Patch generated sections in the markdown doc")
    p.add_argument("--write-csv", action="store_true", help="Rewrite job-catalog.csv derived columns")
    p.add_argument(
        "--write-json",
        action="store_true",
        default=True,
        help="Write docs/data/scorecard.json (default: on)",
    )
    p.add_argument("--no-write-json", action="store_true", help="Skip scorecard.json")
    p.add_argument(
        "--check-only",
        action="store_true",
        help="Exit 1 if drift (unmapped/stale refs) is non-empty; do not write",
    )
    p.add_argument("--date", default=None, help="Snapshot date YYYY-MM-DD (default: today UTC)")
    return p.parse_args()


def skill_description(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return ""
    fm = m.group(1)
    dm = re.search(
        r"description:\s*>?-?\s*\n?((?:.|\n)*?)(?=\n[a-zA-Z0-9_-]+:|\Z)",
        fm,
    )
    if dm:
        return " ".join(dm.group(1).split())
    dm = re.search(r"description:\s*(.+)", fm)
    return dm.group(1).strip().strip("\"'") if dm else ""


def measure_skill_dir(skill_dir: Path) -> SkillDepth | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    text = skill_md.read_text(encoding="utf-8", errors="ignore")
    files = [p for p in skill_dir.rglob("*") if p.is_file()]
    refs = [p for p in files if p.name != "SKILL.md"]
    return SkillDepth(
        name=skill_dir.name,
        words=len(text.split()),
        files=len(files),
        refs=len(refs),
        description=skill_description(text),
    )


def inventory_oep(skills_dir: Path) -> CatalogInventory:
    by_product: dict[str, list[str]] = defaultdict(list)
    depth: dict[str, SkillDepth] = {}
    skills: list[str] = []
    if not skills_dir.is_dir():
        raise FileNotFoundError(f"OEP skills dir not found: {skills_dir}")

    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir() or d.name in META_SKILLS:
            continue
        measured = measure_skill_dir(d)
        if not measured:
            continue
        skills.append(d.name)
        depth[d.name] = measured
        fam = d.name.split("-")[0]
        for prefix in (
            "physicalai-train",
            "physicalai-runtime",
            "metro-ai",
            "chatqna",
            "getitune",
            "anomalib",
            "multimodal",
            "vss",
        ):
            if d.name.startswith(prefix):
                fam = prefix
                break
        by_product[fam].append(d.name)

    return CatalogInventory(
        source=str(skills_dir),
        products=len(by_product),
        skills=skills,
        by_product=dict(by_product),
        depth=depth,
    )


def parse_nvidia_readme(text: str) -> CatalogInventory:
    by_product: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.startswith("| **") or "`" not in line:
            continue
        m = re.match(r"\|\s*\*\*([^*]+)\*\*\s*\|.*?\|\s*(.*?)\s*\|?\s*$", line)
        if not m:
            continue
        prod = m.group(1).strip()
        # Skip non-catalog tables (Getting Help links, etc.)
        skills = re.findall(r"`([^`]+)`", m.group(2))
        if not skills:
            continue
        # Heuristic: skill names are lowercase hyphenated
        skills = [s for s in skills if re.fullmatch(r"[a-z0-9][a-z0-9-]*", s)]
        if skills:
            by_product[prod] = skills

    all_skills = sorted({s for v in by_product.values() for s in v})
    return CatalogInventory(
        source="NVIDIA/skills README catalog",
        products=len(by_product),
        skills=all_skills,
        by_product=by_product,
    )


def fetch_nvidia_readme(path: Path | None, fetch: bool, cache_path: Path | None = None) -> str:
    if path:
        return path.read_text(encoding="utf-8", errors="ignore")

    errors: list[str] = []
    if fetch:
        url = NVIDIA_README_CANDIDATES[0]
        req = urllib.request.Request(url, headers={"User-Agent": "oep-competitive-skill-metrics/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
            return text
        except urllib.error.URLError as exc:
            errors.append(f"urllib {url}: {exc}")
            try:
                out = subprocess.check_output(
                    [
                        "gh",
                        "api",
                        "repos/NVIDIA/skills/readme",
                        "-H",
                        "Accept: application/vnd.github.raw",
                    ],
                    text=True,
                    stderr=subprocess.STDOUT,
                )
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(out, encoding="utf-8")
                return out
            except (subprocess.CalledProcessError, FileNotFoundError) as gh_exc:
                errors.append(f"gh api: {gh_exc}")

    if cache_path and cache_path.is_file():
        print(f"WARNING: using cached NVIDIA README at {cache_path}", file=sys.stderr)
        return cache_path.read_text(encoding="utf-8", errors="ignore")

    raise RuntimeError(
        "Failed to load NVIDIA README. Pass --nvidia-readme, enable fetch, or provide "
        f"cache at {cache_path}. Errors: {'; '.join(errors) or 'none'}"
    )


def find_nvidia_skill_dirs(clone: Path) -> dict[str, Path]:
    """Map skill name -> directory containing SKILL.md under a NVIDIA/skills clone."""
    found: dict[str, Path] = {}
    for skill_md in clone.rglob("SKILL.md"):
        parent = skill_md.parent
        name = parent.name
        # Prefer paths under skills/ if present
        found[name] = parent
    return found


def measure_nvidia_depth(clone: Path, skill_names: list[str] | None = None) -> dict[str, SkillDepth]:
    dirs = find_nvidia_skill_dirs(clone)
    names = skill_names if skill_names is not None else sorted(dirs)
    depth: dict[str, SkillDepth] = {}
    for name in names:
        d = dirs.get(name)
        if not d:
            continue
        measured = measure_skill_dir(d)
        if measured:
            depth[name] = measured
    return depth


def clone_nvidia(dest: Path) -> None:
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--single-branch",
        "https://github.com/NVIDIA/skills.git",
        str(dest),
    ]
    subprocess.check_call(cmd)


def split_skills(cell: str) -> list[str]:
    if not cell or not cell.strip():
        return []
    # Support ; and , separators; strip wildcards for existence checks later
    parts = re.split(r"[;,]", cell)
    return [p.strip() for p in parts if p.strip()]


def load_job_catalog(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def expand_nvidia_refs(ref: str, nvidia_skills: set[str]) -> list[str]:
    """Resolve skill refs; support simple `prefix*` and `*infix*` wildcards."""
    if "*" not in ref:
        return [ref] if ref in nvidia_skills else []
    if ref.endswith("*") and not ref.startswith("*"):
        prefix = ref[:-1]
        return sorted(s for s in nvidia_skills if s.startswith(prefix))
    needle = ref.replace("*", "")
    return sorted(s for s in nvidia_skills if needle in s)


def resolve_nvidia_cell(cell: str, nvidia_skills: set[str]) -> list[str]:
    """Expand every ref in a CSV cell to the distinct NVIDIA skills it matches."""
    return sorted({m for ref in split_skills(cell) for m in expand_nvidia_refs(ref, nvidia_skills)})


def compute_scorecard(
    jobs: list[dict[str, str]],
    oep: CatalogInventory,
    nvidia: CatalogInventory,
    snapshot_date: str,
) -> dict[str, Any]:
    oep_set = set(oep.skills)
    nvidia_set = set(nvidia.skills)

    def oep_list(row: dict[str, str]) -> list[str]:
        return split_skills(row.get("oep_skills", ""))

    def nv_list(row: dict[str, str]) -> list[str]:
        return resolve_nvidia_cell(row.get("nvidia_skills", ""), nvidia_set)

    total = len(jobs)
    oep_covered_rows = [r for r in jobs if oep_list(r)]
    nv_covered_rows = [r for r in jobs if nv_list(r)]
    oep_e2e = [r for r in oep_covered_rows if r.get("e2e", "").upper() == "Y"]
    both = [r for r in jobs if oep_list(r) and nv_list(r)]
    oep_only = [r for r in jobs if oep_list(r) and not nv_list(r)]
    nv_only = [r for r in jobs if nv_list(r) and not oep_list(r)]

    sps_oep = [len(oep_list(r)) for r in oep_covered_rows] or [0]
    sps_nv = [len(nv_list(r)) for r in nv_covered_rows] or [0]

    mapped_oep = sorted({s for r in jobs for s in oep_list(r)})
    jobs_per_skill: dict[str, list[str]] = defaultdict(list)
    for r in jobs:
        for s in oep_list(r):
            jobs_per_skill[s].append(r["job_id"])

    words = [oep.depth[s].words for s in mapped_oep if s in oep.depth]
    depth_floor_n = sum(
        1 for s in mapped_oep if s in oep.depth and oep.depth[s].meets_depth_floor
    )
    thin = sorted(
        s for s in mapped_oep if s in oep.depth and oep.depth[s].thin
    )

    nv_over_split = [
        r["job_id"] for r in jobs if len(nv_list(r)) >= 3
    ]

    entry_skills = sorted(
        {s for r in jobs if r.get("routing") == "entry" for s in oep_list(r)}
    )

    nvidia_depth_values = list(nvidia.depth.values())
    nvidia_median_words = (
        statistics.median([d.words for d in nvidia_depth_values]) if nvidia_depth_values else None
    )
    nvidia_depth_floor_pct = (
        100.0
        * sum(1 for d in nvidia_depth_values if d.meets_depth_floor)
        / len(nvidia_depth_values)
        if nvidia_depth_values
        else None
    )

    # Top NVIDIA products by skill count (raw count context)
    top_products = sorted(
        ((len(v), k) for k, v in nvidia.by_product.items()), reverse=True
    )[:8]

    return {
        "snapshot_date": snapshot_date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw_counts": {
            "oep_products_families": oep.products,
            "oep_skills": len(oep.skills),
            "nvidia_products": nvidia.products,
            "nvidia_skills": len(nvidia.skills),
            "nvidia_top_products": [{"product": k, "skills": n} for n, k in top_products],
        },
        "taxonomy": {
            "total_jobs": total,
            "oep_jobs_covered": len(oep_covered_rows),
            "oep_jobs_covered_pct": round(100.0 * len(oep_covered_rows) / total, 1) if total else 0,
            "nvidia_jobs_covered": len(nv_covered_rows),
            "nvidia_jobs_covered_pct": round(100.0 * len(nv_covered_rows) / total, 1) if total else 0,
            "oep_e2e_jobs": len(oep_e2e),
            "overlap_jobs": len(both),
            "oep_only_jobs": len(oep_only),
            "nvidia_only_jobs": len(nv_only),
            "nvidia_only_job_ids": [r["job_id"] for r in nv_only],
            "mean_skills_per_oep_covered_job": round(statistics.mean(sps_oep), 2),
            "mean_skills_per_nvidia_covered_job": round(statistics.mean(sps_nv), 2),
            "median_skills_per_oep_covered_job": statistics.median(sps_oep),
            "median_skills_per_nvidia_covered_job": statistics.median(sps_nv),
            "nvidia_jobs_skills_ge_3": nv_over_split,
            "oep_skills_mapped": len(mapped_oep),
            "oep_skills_total": len(oep_set),
            "oep_skills_jobs_gt_1": sorted(
                s for s, js in jobs_per_skill.items() if len(js) > 1
            ),
            "entry_skills": entry_skills,
        },
        "depth": {
            "oep_median_words": int(statistics.median(words)) if words else None,
            "oep_mean_words": int(statistics.mean(words)) if words else None,
            "oep_depth_floor_pct": round(100.0 * depth_floor_n / len(mapped_oep), 1)
            if mapped_oep
            else None,
            "oep_thin_skills": thin,
            "nvidia_skills_measured": len(nvidia_depth_values),
            "nvidia_median_words": int(nvidia_median_words) if nvidia_median_words is not None else None,
            "nvidia_depth_floor_pct": round(nvidia_depth_floor_pct, 1)
            if nvidia_depth_floor_pct is not None
            else None,
        },
        "oep_skill_set": sorted(oep_set),
        "nvidia_skill_set_size": len(nvidia_set),
    }


def compute_drift(
    jobs: list[dict[str, str]],
    oep: CatalogInventory,
    nvidia: CatalogInventory,
) -> DriftReport:
    oep_set = set(oep.skills)
    nvidia_set = set(nvidia.skills)
    mapped_oep = {s for r in jobs for s in split_skills(r.get("oep_skills", ""))}
    mapped_nv: set[str] = set()
    stale_nv: list[str] = []

    for r in jobs:
        for ref in split_skills(r.get("nvidia_skills", "")):
            matches = expand_nvidia_refs(ref, nvidia_set)
            if not matches:
                stale_nv.append(ref)
            mapped_nv.update(matches)

    overlap_skills = {
        s
        for prod, skills in nvidia.by_product.items()
        if prod in NVIDIA_OVERLAP_PRODUCTS
        for s in skills
    }
    # Heuristic: unmapped overlap skills that look like workflow (not pure API shards)
    # Flag all overlap skills not referenced for human review — capped list.
    unmapped_overlap = sorted(overlap_skills - mapped_nv)
    # Prefer ones that share prefixes with mapped ones for relevance
    mapped_prefixes = {s.split("-")[0] for s in mapped_nv}
    prioritized = [s for s in unmapped_overlap if s.split("-")[0] in mapped_prefixes]
    other = [s for s in unmapped_overlap if s not in prioritized]

    return DriftReport(
        unmapped_oep_skills=sorted(oep_set - mapped_oep),
        stale_oep_refs=sorted(mapped_oep - oep_set),
        stale_nvidia_refs=sorted(set(stale_nv)),
        unmapped_nvidia_overlap=(prioritized + other)[:40],
        new_oep_since_csv=sorted(oep_set - mapped_oep),
    )


def rewrite_csv(
    path: Path, jobs: list[dict[str, str]], oep: CatalogInventory, nvidia: CatalogInventory
) -> None:
    nvidia_set = set(nvidia.skills)
    fieldnames = [
        "job_id",
        "domain",
        "job",
        "e2e",
        "oep_skills",
        "nvidia_skills",
        "routing",
        "notes",
        "oep_skills_per_job",
        "nvidia_skills_per_job",
        "oep_median_words",
        "oep_has_refs",
    ]
    rows_out = []
    for r in jobs:
        oep_skills = split_skills(r.get("oep_skills", ""))
        nv_skills = resolve_nvidia_cell(r.get("nvidia_skills", ""), nvidia_set)
        words = [oep.depth[s].words for s in oep_skills if s in oep.depth]
        refs = any(oep.depth[s].refs > 0 for s in oep_skills if s in oep.depth)
        rows_out.append(
            {
                "job_id": r["job_id"],
                "domain": r.get("domain", ""),
                "job": r.get("job", ""),
                "e2e": r.get("e2e", ""),
                "oep_skills": r.get("oep_skills", ""),
                "nvidia_skills": r.get("nvidia_skills", ""),
                "routing": r.get("routing", ""),
                "notes": r.get("notes", ""),
                "oep_skills_per_job": str(len(oep_skills)),
                "nvidia_skills_per_job": str(len(nv_skills)),
                "oep_median_words": str(int(statistics.median(words))) if words else "",
                "oep_has_refs": ("Y" if refs else "N") if oep_skills else "",
            }
        )
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)


def replace_marked_section(text: str, begin: str, end: str, body: str) -> str:
    block = f"{begin}\n{body.rstrip()}\n{end}"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise RuntimeError(f"Markers not found in doc: {begin} ... {end}")
    return pattern.sub(lambda _: block, text)


def fmt_pct(n: float | None) -> str:
    if n is None:
        return "n/a"
    return f"{n:.0f}%" if abs(n - round(n)) < 0.05 else f"{n:.1f}%"


def render_snapshot(score: dict[str, Any]) -> str:
    rc = score["raw_counts"]
    top = ", ".join(f"{p['product']} ~{p['skills']}" for p in rc["nvidia_top_products"][:3])
    return f"""**Snapshot ({score['snapshot_date']}).**

| Catalog | Products | Skills (raw) | Notes |
|---------|----------|--------------|-------|
| open-edge-platform/skills | {rc['oep_products_families']} families / see README | **{rc['oep_skills']}** | Index in repo README; meta skill excluded |
| NVIDIA/skills | **{rc['nvidia_products']}** | **~{rc['nvidia_skills']}** | Catalog README; top: {top} |

Raw count favors API/docs sharding. This document defines a shared **job taxonomy** and a **scorecard** so both catalogs are judged on the same unit of value: a user job.

Companion data: [`data/job-catalog.csv`](data/job-catalog.csv) · [`data/scorecard.json`](data/scorecard.json)."""


def render_scorecard(score: dict[str, Any]) -> str:
    t = score["taxonomy"]
    d = score["depth"]
    nv_depth = (
        f"**~{d['nvidia_median_words']} words** (n={d['nvidia_skills_measured']})"
        if d["nvidia_median_words"] is not None
        else "n/a — pass `--clone-nvidia-depth` or `--nvidia-clone`"
    )
    nv_floor = (
        fmt_pct(d["nvidia_depth_floor_pct"])
        if d["nvidia_depth_floor_pct"] is not None
        else "n/a"
    )
    entry = ", ".join(f"`{s}`" for s in t["entry_skills"]) or "none mapped"
    return f"""| # | Metric | How to compute | OEP (this snapshot) | NVIDIA (same job set) | Why it beats count |
|---|--------|----------------|---------------------|------------------------|--------------------|
| 1 | **Jobs covered** | Jobs with ≥1 mapped skill / total jobs | **{t['oep_jobs_covered']} / {t['total_jobs']} ({fmt_pct(t['oep_jobs_covered_pct'])})** | **{t['nvidia_jobs_covered']} / {t['total_jobs']} ({fmt_pct(t['nvidia_jobs_covered_pct'])})** | Same denominator |
| 2 | **E2E jobs covered** | Jobs marked end-to-end with a full path | **{t['oep_e2e_jobs']}** | (see taxonomy; shards may stop at install/API) | “Can finish the outcome” |
| 3 | **Median skill depth** | Median `SKILL.md` words of mapped skills | **~{d['oep_median_words']} words** | {nv_depth} | Hard to fake with empty folders |
| 4 | **Granularity health** | Mean skills-per-job; target band 1–3 | **{t['mean_skills_per_oep_covered_job']:.2f}** | **~{t['mean_skills_per_nvidia_covered_job']:.2f}**; ≥3 on {', '.join(t['nvidia_jobs_skills_ge_3']) or 'none'} | Detects over-split |
| 5 | **Entry / routing coverage** | Domains with an orchestrator or clear progressive entry | {entry} | Mostly leaf catalog; few business-intent routers | Users need not know leaf names |

OEP depth floor (words ≥500 or refs >0): **{fmt_pct(d['oep_depth_floor_pct'])}**. NVIDIA depth floor: **{nv_floor}**.

**Optional sixth (governance):** % of skills with evals + security scan + skill card / signature. NVIDIA markets this heavily; track it so the debate does not shift to “unverified.”"""


def render_aggregates(score: dict[str, Any]) -> str:
    t = score["taxonomy"]
    nv_only = ", ".join(t["nvidia_only_job_ids"]) or "—"
    return f"""| Measure | OEP | NVIDIA (on this taxonomy) |
|---------|-----|---------------------------|
| Jobs covered | {t['oep_jobs_covered']} / {t['total_jobs']} | {t['nvidia_jobs_covered']} / {t['total_jobs']} |
| OEP-only jobs | {t['oep_only_jobs']} | — |
| NVIDIA-only jobs | — | {t['nvidia_only_jobs']} ({nv_only}) |
| Overlap jobs | {t['overlap_jobs']} | {t['overlap_jobs']} |
| Mean skills / covered job | **{t['mean_skills_per_oep_covered_job']:.2f}** | **~{t['mean_skills_per_nvidia_covered_job']:.2f}** |
| Jobs with NVIDIA skills/job ≥ 3 | — | {', '.join(t['nvidia_jobs_skills_ge_3']) or '—'} |
| OEP skills mapped | {t['oep_skills_mapped']} / {t['oep_skills_total']} | — |
| OEP jobs/skill > 1 | {len(t['oep_skills_jobs_gt_1'])} ({', '.join(t['oep_skills_jobs_gt_1']) or 'none'}) | — |

**Reading:** Compare on jobs and skills-per-job. NVIDIA raw skill count is dominated by products outside this taxonomy (DOCA, Jetson BSP, NeMo MBridge, per-model TAO trains)."""


def render_drift(drift: DriftReport, score: dict[str, Any]) -> str:
    d = score["depth"]
    thin = ", ".join(f"`{s}`" for s in d["oep_thin_skills"]) or "none"
    lines = [
        f"_Generated {score['generated_at']}_.",
        "",
        f"- **Unmapped OEP skills** ({len(drift.unmapped_oep_skills)}): "
        + (", ".join(f"`{s}`" for s in drift.unmapped_oep_skills) or "none"),
        f"- **Stale OEP refs in CSV** ({len(drift.stale_oep_refs)}): "
        + (", ".join(f"`{s}`" for s in drift.stale_oep_refs) or "none"),
        f"- **Stale / unresolved NVIDIA refs** ({len(drift.stale_nvidia_refs)}): "
        + (", ".join(f"`{s}`" for s in drift.stale_nvidia_refs) or "none"),
        f"- **OEP thin skills** (words <400 and no refs): {thin}",
        f"- **Unmapped NVIDIA overlap-product skills** (sample, review for remap): "
        + (", ".join(f"`{s}`" for s in drift.unmapped_nvidia_overlap[:15]) or "none")
        + (
            f" … +{len(drift.unmapped_nvidia_overlap) - 15} more"
            if len(drift.unmapped_nvidia_overlap) > 15
            else ""
        ),
    ]
    return "\n".join(lines)


def ensure_markers(docs_path: Path) -> None:
    """If markers missing (first run after skill add), inject after known headings."""
    text = docs_path.read_text(encoding="utf-8")
    if BEGIN_SNAPSHOT in text and BEGIN_SCORECARD in text and BEGIN_AGGREGATES in text:
        if BEGIN_DRIFT not in text:
            # Append drift section before thesis
            insert = (
                "\n## Drift report (auto)\n\n"
                f"{BEGIN_DRIFT}\n_Run refresh_scorecard.py_\n{END_DRIFT}\n"
            )
            if "## 8. One-paragraph thesis" in text:
                text = text.replace("## 8. One-paragraph thesis", insert + "\n## 8. One-paragraph thesis")
            else:
                text = text.rstrip() + "\n" + insert
            docs_path.write_text(text, encoding="utf-8")
        return

    # Fresh wrap of existing snapshot / scorecard / aggregates if present
    raise RuntimeError(
        f"{docs_path} is missing generation markers. Re-run after markers are present, "
        "or restore docs/competitive-skill-metrics.md from the skill bundle."
    )


def patch_docs(docs_path: Path, score: dict[str, Any], drift: DriftReport) -> None:
    ensure_markers(docs_path)
    text = docs_path.read_text(encoding="utf-8")
    text = replace_marked_section(text, BEGIN_SNAPSHOT, END_SNAPSHOT, render_snapshot(score))
    text = replace_marked_section(text, BEGIN_SCORECARD, END_SCORECARD, render_scorecard(score))
    text = replace_marked_section(text, BEGIN_AGGREGATES, END_AGGREGATES, render_aggregates(score))
    text = replace_marked_section(text, BEGIN_DRIFT, END_DRIFT, render_drift(drift, score))
    # Bump any leftover "**Snapshot (DATE).**" outside markers is handled by markers.
    docs_path.write_text(text, encoding="utf-8")


def print_summary(score: dict[str, Any], drift: DriftReport) -> None:
    t = score["taxonomy"]
    d = score["depth"]
    rc = score["raw_counts"]
    print(f"Snapshot {score['snapshot_date']}")
    print(f"  OEP skills: {rc['oep_skills']}  |  NVIDIA skills: ~{rc['nvidia_skills']} ({rc['nvidia_products']} products)")
    print(
        f"  Jobs covered: OEP {t['oep_jobs_covered']}/{t['total_jobs']} "
        f"({t['oep_jobs_covered_pct']}%)  |  NVIDIA {t['nvidia_jobs_covered']}/{t['total_jobs']} "
        f"({t['nvidia_jobs_covered_pct']}%)"
    )
    print(
        f"  Skills/job (mean): OEP {t['mean_skills_per_oep_covered_job']}  |  "
        f"NVIDIA {t['mean_skills_per_nvidia_covered_job']}"
    )
    print(
        f"  Depth median words: OEP {d['oep_median_words']}  |  "
        f"NVIDIA {d['nvidia_median_words'] if d['nvidia_median_words'] is not None else 'n/a'}"
    )
    print(
        f"  Drift: unmapped_oep={len(drift.unmapped_oep_skills)} "
        f"stale_oep={len(drift.stale_oep_refs)} stale_nv={len(drift.stale_nvidia_refs)} "
        f"nv_overlap_unmapped_sample={len(drift.unmapped_nvidia_overlap)}"
    )
    if drift.unmapped_oep_skills:
        print("  Unmapped OEP:", ", ".join(drift.unmapped_oep_skills))
    if drift.stale_oep_refs:
        print("  Stale OEP refs:", ", ".join(drift.stale_oep_refs))
    if drift.stale_nvidia_refs:
        print("  Stale NVIDIA refs:", ", ".join(drift.stale_nvidia_refs))


def main() -> int:
    args = parse_args()
    root: Path = args.repo_root.resolve()
    job_catalog = args.job_catalog or (root / "docs" / "data" / "job-catalog.csv")
    docs_path = args.docs or (root / "docs" / "competitive-skill-metrics.md")
    oep_dir = args.oep_skills_dir or (root / ".agents" / "skills")
    snapshot_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    write_json = args.write_json and not args.no_write_json

    if args.check_only:
        args.write_docs = False
        args.write_csv = False
        write_json = False

    oep = inventory_oep(oep_dir)
    cache_path = root / "docs" / "data" / "nvidia-skills-README.cache.md"
    nvidia_text = fetch_nvidia_readme(args.nvidia_readme, args.fetch_nvidia, cache_path=cache_path)
    nvidia = parse_nvidia_readme(nvidia_text)

    if args.nvidia_clone:
        nvidia.depth = measure_nvidia_depth(args.nvidia_clone)
    elif args.clone_nvidia_depth:
        print("Shallow-cloning NVIDIA/skills for depth stats…", file=sys.stderr)
        with tempfile.TemporaryDirectory(prefix="nvidia-skills-") as tmp:
            clone_nvidia(Path(tmp))
            nvidia.depth = measure_nvidia_depth(Path(tmp))

    jobs = load_job_catalog(job_catalog)
    score = compute_scorecard(jobs, oep, nvidia, snapshot_date)
    drift = compute_drift(jobs, oep, nvidia)

    print_summary(score, drift)

    out_json = root / "docs" / "data" / "scorecard.json"
    payload = {
        "scorecard": score,
        "drift": asdict(drift),
    }

    if write_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out_json}")

    if args.write_csv:
        rewrite_csv(job_catalog, jobs, oep, nvidia)
        print(f"Wrote {job_catalog}")

    if args.write_docs:
        patch_docs(docs_path, score, drift)
        print(f"Patched {docs_path}")

    if args.check_only:
        blocking = drift.unmapped_oep_skills or drift.stale_oep_refs or drift.stale_nvidia_refs
        return 1 if blocking else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
