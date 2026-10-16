#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Refresh competitive skill metrics for open-edge-platform vs NVIDIA / AMD / Qualcomm.

Reads the job taxonomy CSV, inventories vendor skill catalogs, recomputes
coverage / depth / granularity aggregates, and patches the scorecard doc.

Examples:
  python refresh_scorecard.py --write-docs --write-csv
  python refresh_scorecard.py --clone-nvidia-depth --write-docs
  python refresh_scorecard.py --check-only
"""

from __future__ import annotations

import argparse
import csv
import json
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

NVIDIA_README_URL = "https://raw.githubusercontent.com/NVIDIA/skills/main/README.md"
AMD_README_URL = "https://raw.githubusercontent.com/amd/skills/main/README.md"
QUALCOMM_SKILLS_JSON_URL = (
    "https://raw.githubusercontent.com/qualcomm/skills/main/IOT/qualcomm-linux/skills.json"
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

# AMD catalog focus areas used as "products" for raw-count context
AMD_SECTION_PRODUCTS = {
    "Client-native": ("local-ai-use", "local-ai-app-integration"),
    "Cross-stack": (
        "rocm-doctor",
        "lemonade-router-builder",
        "quark-install",
        "quark-torch-llm-ptq",
    ),
    "Server-native": (
        "serving-llms-on-instinct",
        "serving-llms-on-epyc",
        "hyperloom-workload-optimizer",
        "magpie-kernel-evaluator",
        "tracelens-analysis-orchestrator",
    ),
}

BEGIN_SNAPSHOT = "<!-- BEGIN GENERATED:SNAPSHOT -->"
END_SNAPSHOT = "<!-- END GENERATED:SNAPSHOT -->"
BEGIN_SCORECARD = "<!-- BEGIN GENERATED:SCORECARD -->"
END_SCORECARD = "<!-- END GENERATED:SCORECARD -->"
BEGIN_AGGREGATES = "<!-- BEGIN GENERATED:AGGREGATES -->"
END_AGGREGATES = "<!-- END GENERATED:AGGREGATES -->"
BEGIN_DRIFT = "<!-- BEGIN GENERATED:DRIFT -->"
END_DRIFT = "<!-- END GENERATED:DRIFT -->"

UA = "oep-competitive-skill-metrics/1.1"


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
    notes: str = ""


@dataclass
class DriftReport:
    unmapped_oep_skills: list[str] = field(default_factory=list)
    stale_oep_refs: list[str] = field(default_factory=list)
    stale_nvidia_refs: list[str] = field(default_factory=list)
    stale_amd_refs: list[str] = field(default_factory=list)
    stale_qualcomm_refs: list[str] = field(default_factory=list)
    unmapped_nvidia_overlap: list[str] = field(default_factory=list)
    unmapped_amd_skills: list[str] = field(default_factory=list)
    unmapped_qualcomm_skills: list[str] = field(default_factory=list)
    new_oep_since_csv: list[str] = field(default_factory=list)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[4]


def parse_args() -> argparse.Namespace:
    root = repo_root_from_script()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", type=Path, default=root)
    p.add_argument("--job-catalog", type=Path, default=None)
    p.add_argument("--docs", type=Path, default=None)
    p.add_argument("--oep-skills-dir", type=Path, default=None)
    p.add_argument("--nvidia-readme", type=Path, default=None)
    p.add_argument("--amd-readme", type=Path, default=None)
    p.add_argument("--qualcomm-json", type=Path, default=None)
    p.add_argument("--nvidia-clone", type=Path, default=None)
    p.add_argument("--amd-clone", type=Path, default=None)
    p.add_argument("--qualcomm-clone", type=Path, default=None)
    p.add_argument("--fetch-nvidia", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--fetch-amd", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--fetch-qualcomm", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--clone-nvidia-depth", action="store_true")
    p.add_argument("--clone-amd-depth", action="store_true")
    p.add_argument("--clone-qualcomm-depth", action="store_true")
    p.add_argument("--write-docs", action="store_true")
    p.add_argument("--write-csv", action="store_true")
    p.add_argument("--write-json", action="store_true", default=True)
    p.add_argument("--no-write-json", action="store_true")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--date", default=None)
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


def http_get_text(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_text_with_cache(
    *,
    local: Path | None,
    fetch: bool,
    url: str,
    cache_path: Path,
    gh_api: str | None = None,
    label: str,
) -> str:
    if local:
        return local.read_text(encoding="utf-8", errors="ignore")

    errors: list[str] = []
    if fetch:
        try:
            text = http_get_text(url)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(text, encoding="utf-8")
            return text
        except urllib.error.URLError as exc:
            errors.append(f"urllib {url}: {exc}")
            if gh_api:
                try:
                    out = subprocess.check_output(
                        ["gh", "api", gh_api, "-H", "Accept: application/vnd.github.raw"],
                        text=True,
                        stderr=subprocess.STDOUT,
                    )
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(out, encoding="utf-8")
                    return out
                except (subprocess.CalledProcessError, FileNotFoundError) as gh_exc:
                    errors.append(f"gh api: {gh_exc}")

    if cache_path.is_file():
        print(f"WARNING: using cached {label} at {cache_path}", file=sys.stderr)
        return cache_path.read_text(encoding="utf-8", errors="ignore")

    raise RuntimeError(
        f"Failed to load {label}. Pass a local path, enable fetch, or provide cache at "
        f"{cache_path}. Errors: {'; '.join(errors) or 'none'}"
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
        skills = re.findall(r"`([^`]+)`", m.group(2))
        skills = [s for s in skills if re.fullmatch(r"[a-z0-9][a-z0-9-]*", s)]
        if skills:
            by_product[prod] = skills

    all_skills = sorted({s for v in by_product.values() for s in v})
    if not all_skills:
        raise ValueError(
            "NVIDIA README parse returned an empty catalog; refusing to publish "
            "a zeroed scorecard (README table format may have changed)"
        )
    return CatalogInventory(
        source="NVIDIA/skills README catalog",
        products=len(by_product),
        skills=all_skills,
        by_product=by_product,
    )


def parse_amd_readme(text: str) -> CatalogInventory:
    """Parse published AMD skills from catalog tables; skip planned (no markdown link)."""
    by_product: dict[str, list[str]] = defaultdict(list)
    # Linked skills: [`name`](url) — published
    published = set(re.findall(r"\[`([a-z0-9][a-z0-9-]*)`\]\([^)]+\)", text))
    # Assign to focus-area products when known; else "Other"
    assigned: set[str] = set()
    for product, names in AMD_SECTION_PRODUCTS.items():
        for name in names:
            if name in published:
                by_product[product].append(name)
                assigned.add(name)
    for name in sorted(published - assigned):
        by_product["Other"].append(name)

    all_skills = sorted(published)
    if not all_skills:
        raise ValueError("AMD README parse returned an empty catalog")
    planned = sorted(
        set(re.findall(r"`([a-z0-9][a-z0-9-]*)`", text))
        - published
        - {"skills", "skill-card", "evals", "references", "scripts"}
    )
    # Filter planned to hyphenated skill-like tokens that appear as bare `name` in tables
    planned = [s for s in planned if s.count("-") >= 1 and s not in all_skills]
    notes = f"published={len(all_skills)}"
    if planned:
        notes += f"; planned_excluded={','.join(planned[:5])}"
    return CatalogInventory(
        source="amd/skills README catalog",
        products=len(by_product),
        skills=all_skills,
        by_product=dict(by_product),
        notes=notes,
    )


def parse_qualcomm_skills_json(text: str) -> CatalogInventory:
    """Parse Qualcomm IOT skills.json — logical skills + board/version shards."""
    data = json.loads(text)
    by_product: dict[str, list[str]] = defaultdict(list)
    skills: list[str] = []
    shard_count = 0
    for entry in data.get("skills", []):
        logical = entry.get("name", "").strip()
        if not logical:
            continue
        owner = entry.get("owner") or entry.get("category") or "qualcomm"
        versions = entry.get("versions") or []
        if not versions:
            skills.append(logical)
            by_product[owner].append(logical)
            continue
        # Logical name is map-friendly; shards are counted for over-split signal
        skills.append(logical)
        by_product[owner].append(logical)
        for ver in versions:
            path = (ver.get("path") or "").rstrip("/")
            leaf = path.split("/")[-1] if path else ""
            if leaf and leaf != logical:
                shard = f"{logical}--{leaf}"
                skills.append(shard)
                by_product[f"{owner}-variants"].append(shard)
                shard_count += 1
            elif leaf == logical:
                # single-folder skill (fan controller)
                shard_count += 1

    all_skills = sorted(set(skills))
    if not all_skills:
        raise ValueError("Qualcomm skills.json parse returned an empty catalog")
    logical_n = len(data.get("skills", []))
    return CatalogInventory(
        source="qualcomm/skills IOT/qualcomm-linux/skills.json",
        products=len({e.get("owner") or e.get("category") or "qualcomm" for e in data.get("skills", [])}),
        skills=all_skills,
        by_product=dict(by_product),
        notes=f"logical={logical_n}; version_shards≈{shard_count}",
    )


def find_skill_dirs(clone: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for skill_md in clone.rglob("SKILL.md"):
        parent = skill_md.parent
        found[parent.name] = parent
    return found


def measure_clone_depth(clone: Path, skill_names: list[str] | None = None) -> dict[str, SkillDepth]:
    dirs = find_skill_dirs(clone)
    names = skill_names if skill_names is not None else sorted(dirs)
    depth: dict[str, SkillDepth] = {}
    for name in names:
        # Qualcomm compound ids: configure-ethernet--qcs6490 → look up leaf
        leaf = name.split("--")[-1] if "--" in name else name
        d = dirs.get(name) or dirs.get(leaf)
        if not d:
            continue
        measured = measure_skill_dir(d)
        if measured:
            measured.name = name
            depth[name] = measured
    return depth


def shallow_clone(url: str, dest: Path) -> None:
    subprocess.check_call(
        ["git", "clone", "--depth", "1", "--single-branch", url, str(dest)]
    )


def split_skills(cell: str) -> list[str]:
    if not cell or not cell.strip():
        return []
    parts = re.split(r"[;,]", cell)
    return [p.strip() for p in parts if p.strip()]


def load_job_catalog(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def expand_refs(ref: str, catalog: set[str]) -> list[str]:
    if "*" not in ref:
        return [ref] if ref in catalog else []
    if ref.endswith("*") and not ref.startswith("*"):
        prefix = ref[:-1]
        return sorted(s for s in catalog if s.startswith(prefix))
    needle = ref.replace("*", "")
    return sorted(s for s in catalog if needle in s)


def resolve_cell(cell: str, catalog: set[str]) -> list[str]:
    return sorted({m for ref in split_skills(cell) for m in expand_refs(ref, catalog)})


def vendor_coverage(
    jobs: list[dict[str, str]],
    col: str,
    catalog: set[str],
) -> dict[str, Any]:
    def skills(row: dict[str, str]) -> list[str]:
        return resolve_cell(row.get(col, ""), catalog)

    covered = [r for r in jobs if skills(r)]
    sps = [len(skills(r)) for r in covered] or [0]
    over = [r["job_id"] for r in jobs if len(skills(r)) >= 3]
    only = [r["job_id"] for r in jobs if skills(r) and not split_skills(r.get("oep_skills", ""))]
    return {
        "jobs_covered": len(covered),
        "jobs_covered_pct": round(100.0 * len(covered) / len(jobs), 1) if jobs else 0,
        "mean_skills_per_covered_job": round(statistics.mean(sps), 2),
        "jobs_skills_ge_3": over,
        "vendor_only_job_ids": only,
        "vendor_only_jobs": len(only),
    }


def depth_stats(mapped: list[str], inv: CatalogInventory) -> dict[str, Any]:
    words = [inv.depth[s].words for s in mapped if s in inv.depth]
    floor_n = sum(1 for s in mapped if s in inv.depth and inv.depth[s].meets_depth_floor)
    thin = sorted(s for s in mapped if s in inv.depth and inv.depth[s].thin)
    measured = list(inv.depth.values())
    return {
        "median_words": int(statistics.median(words)) if words else None,
        "mean_words": int(statistics.mean(words)) if words else None,
        "depth_floor_pct": round(100.0 * floor_n / len(mapped), 1) if mapped else None,
        "thin_skills": thin,
        "skills_measured": len(measured),
        "catalog_median_words": int(statistics.median([d.words for d in measured])) if measured else None,
        "catalog_depth_floor_pct": round(
            100.0 * sum(1 for d in measured if d.meets_depth_floor) / len(measured), 1
        )
        if measured
        else None,
    }


def compute_scorecard(
    jobs: list[dict[str, str]],
    oep: CatalogInventory,
    nvidia: CatalogInventory,
    amd: CatalogInventory,
    qualcomm: CatalogInventory,
    snapshot_date: str,
) -> dict[str, Any]:
    oep_set = set(oep.skills)
    nv_set = set(nvidia.skills)
    amd_set = set(amd.skills)
    qc_set = set(qualcomm.skills)
    total = len(jobs)

    def oep_list(row: dict[str, str]) -> list[str]:
        return split_skills(row.get("oep_skills", ""))

    oep_covered = [r for r in jobs if oep_list(r)]
    oep_e2e = [r for r in oep_covered if r.get("e2e", "").upper() == "Y"]
    sps_oep = [len(oep_list(r)) for r in oep_covered] or [0]
    mapped_oep = sorted({s for r in jobs for s in oep_list(r)})
    jobs_per_skill: dict[str, list[str]] = defaultdict(list)
    for r in jobs:
        for s in oep_list(r):
            jobs_per_skill[s].append(r["job_id"])

    entry_skills = sorted(
        {s for r in jobs if r.get("routing") == "entry" for s in oep_list(r)}
    )

    nv_cov = vendor_coverage(jobs, "nvidia_skills", nv_set)
    amd_cov = vendor_coverage(jobs, "amd_skills", amd_set)
    qc_cov = vendor_coverage(jobs, "qualcomm_skills", qc_set)

    both_nv = sum(1 for r in jobs if oep_list(r) and resolve_cell(r.get("nvidia_skills", ""), nv_set))
    oep_only = sum(
        1
        for r in jobs
        if oep_list(r)
        and not resolve_cell(r.get("nvidia_skills", ""), nv_set)
        and not resolve_cell(r.get("amd_skills", ""), amd_set)
        and not resolve_cell(r.get("qualcomm_skills", ""), qc_set)
    )

    oep_depth = depth_stats(mapped_oep, oep)
    nv_top = sorted(((len(v), k) for k, v in nvidia.by_product.items()), reverse=True)[:8]

    return {
        "snapshot_date": snapshot_date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw_counts": {
            "oep_products_families": oep.products,
            "oep_skills": len(oep.skills),
            "nvidia_products": nvidia.products,
            "nvidia_skills": len(nvidia.skills),
            "nvidia_top_products": [{"product": k, "skills": n} for n, k in nv_top],
            "amd_products": amd.products,
            "amd_skills": len(amd.skills),
            "amd_notes": amd.notes,
            "qualcomm_products": qualcomm.products,
            "qualcomm_skills": len(qualcomm.skills),
            "qualcomm_notes": qualcomm.notes,
        },
        "taxonomy": {
            "total_jobs": total,
            "oep_jobs_covered": len(oep_covered),
            "oep_jobs_covered_pct": round(100.0 * len(oep_covered) / total, 1) if total else 0,
            "oep_e2e_jobs": len(oep_e2e),
            "oep_only_vs_all_vendors": oep_only,
            "overlap_jobs_oep_nvidia": both_nv,
            "mean_skills_per_oep_covered_job": round(statistics.mean(sps_oep), 2),
            "oep_skills_mapped": len(mapped_oep),
            "oep_skills_total": len(oep_set),
            "oep_skills_jobs_gt_1": sorted(s for s, js in jobs_per_skill.items() if len(js) > 1),
            "entry_skills": entry_skills,
            "nvidia": nv_cov,
            "amd": amd_cov,
            "qualcomm": qc_cov,
        },
        "depth": {
            "oep_median_words": oep_depth["median_words"],
            "oep_mean_words": oep_depth["mean_words"],
            "oep_depth_floor_pct": oep_depth["depth_floor_pct"],
            "oep_thin_skills": oep_depth["thin_skills"],
            "nvidia_skills_measured": len(nvidia.depth),
            "nvidia_median_words": depth_stats(list(nvidia.depth), nvidia)["catalog_median_words"]
            if nvidia.depth
            else None,
            "nvidia_depth_floor_pct": depth_stats(list(nvidia.depth), nvidia)["catalog_depth_floor_pct"]
            if nvidia.depth
            else None,
            "amd_skills_measured": len(amd.depth),
            "amd_median_words": depth_stats(list(amd.depth), amd)["catalog_median_words"]
            if amd.depth
            else None,
            "amd_depth_floor_pct": depth_stats(list(amd.depth), amd)["catalog_depth_floor_pct"]
            if amd.depth
            else None,
            "qualcomm_skills_measured": len(qualcomm.depth),
            "qualcomm_median_words": depth_stats(list(qualcomm.depth), qualcomm)["catalog_median_words"]
            if qualcomm.depth
            else None,
            "qualcomm_depth_floor_pct": depth_stats(list(qualcomm.depth), qualcomm)[
                "catalog_depth_floor_pct"
            ]
            if qualcomm.depth
            else None,
        },
        "oep_skill_set": sorted(oep_set),
        "nvidia_skill_set_size": len(nv_set),
        "amd_skill_set_size": len(amd_set),
        "qualcomm_skill_set_size": len(qc_set),
    }


def compute_drift(
    jobs: list[dict[str, str]],
    oep: CatalogInventory,
    nvidia: CatalogInventory,
    amd: CatalogInventory,
    qualcomm: CatalogInventory,
) -> DriftReport:
    oep_set = set(oep.skills)
    nv_set = set(nvidia.skills)
    amd_set = set(amd.skills)
    qc_set = set(qualcomm.skills)
    mapped_oep = {s for r in jobs for s in split_skills(r.get("oep_skills", ""))}

    def stale_and_mapped(col: str, catalog: set[str]) -> tuple[list[str], set[str]]:
        stale: list[str] = []
        mapped: set[str] = set()
        for r in jobs:
            for ref in split_skills(r.get(col, "")):
                matches = expand_refs(ref, catalog)
                if not matches:
                    stale.append(ref)
                mapped.update(matches)
        return sorted(set(stale)), mapped

    stale_nv, mapped_nv = stale_and_mapped("nvidia_skills", nv_set)
    stale_amd, mapped_amd = stale_and_mapped("amd_skills", amd_set)
    stale_qc, mapped_qc = stale_and_mapped("qualcomm_skills", qc_set)

    overlap_skills = {
        s
        for prod, skills in nvidia.by_product.items()
        if prod in NVIDIA_OVERLAP_PRODUCTS
        for s in skills
    }
    unmapped_overlap = sorted(overlap_skills - mapped_nv)
    mapped_prefixes = {s.split("-")[0] for s in mapped_nv}
    prioritized = [s for s in unmapped_overlap if s.split("-")[0] in mapped_prefixes]
    other = [s for s in unmapped_overlap if s not in prioritized]

    # Logical Qualcomm / AMD names only for unmapped review (exclude --variant shards)
    amd_logical = {s for s in amd_set if "--" not in s}
    qc_logical = {s for s in qc_set if "--" not in s}

    return DriftReport(
        unmapped_oep_skills=sorted(oep_set - mapped_oep),
        stale_oep_refs=sorted(mapped_oep - oep_set),
        stale_nvidia_refs=stale_nv,
        stale_amd_refs=stale_amd,
        stale_qualcomm_refs=stale_qc,
        unmapped_nvidia_overlap=(prioritized + other)[:40],
        unmapped_amd_skills=sorted(amd_logical - mapped_amd),
        unmapped_qualcomm_skills=sorted(qc_logical - mapped_qc),
        new_oep_since_csv=sorted(oep_set - mapped_oep),
    )


def rewrite_csv(
    path: Path,
    jobs: list[dict[str, str]],
    oep: CatalogInventory,
    nvidia: CatalogInventory,
    amd: CatalogInventory,
    qualcomm: CatalogInventory,
) -> None:
    nv_set, amd_set, qc_set = set(nvidia.skills), set(amd.skills), set(qualcomm.skills)
    fieldnames = [
        "job_id",
        "domain",
        "job",
        "e2e",
        "oep_skills",
        "nvidia_skills",
        "amd_skills",
        "qualcomm_skills",
        "routing",
        "notes",
        "oep_skills_per_job",
        "nvidia_skills_per_job",
        "amd_skills_per_job",
        "qualcomm_skills_per_job",
        "oep_median_words",
        "oep_has_refs",
    ]
    rows_out = []
    for r in jobs:
        oep_skills = split_skills(r.get("oep_skills", ""))
        nv_skills = resolve_cell(r.get("nvidia_skills", ""), nv_set)
        amd_skills = resolve_cell(r.get("amd_skills", ""), amd_set)
        qc_skills = resolve_cell(r.get("qualcomm_skills", ""), qc_set)
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
                "amd_skills": r.get("amd_skills", ""),
                "qualcomm_skills": r.get("qualcomm_skills", ""),
                "routing": r.get("routing", ""),
                "notes": r.get("notes", ""),
                "oep_skills_per_job": str(len(oep_skills)),
                "nvidia_skills_per_job": str(len(nv_skills)),
                "amd_skills_per_job": str(len(amd_skills)),
                "qualcomm_skills_per_job": str(len(qc_skills)),
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


def _depth_cell(median: int | None, n: int | None, hint: str) -> str:
    if median is not None:
        return f"**~{median} words** (n={n})"
    return f"n/a — {hint}"


def render_snapshot(score: dict[str, Any]) -> str:
    rc = score["raw_counts"]
    top = ", ".join(f"{p['product']} ~{p['skills']}" for p in rc["nvidia_top_products"][:3])
    return f"""**Snapshot ({score['snapshot_date']}).**

| Catalog | Products | Skills (raw) | Notes |
|---------|----------|--------------|-------|
| open-edge-platform/skills | {rc['oep_products_families']} families / see README | **{rc['oep_skills']}** | Index in repo README; meta skill excluded |
| [NVIDIA/skills](https://github.com/NVIDIA/skills) | **{rc['nvidia_products']}** | **~{rc['nvidia_skills']}** | Catalog README; top: {top} |
| [amd/skills](https://github.com/amd/skills) | **{rc['amd_products']}** | **{rc['amd_skills']}** | {rc.get('amd_notes') or 'README catalog; LLM/ROCm focus'} |
| [qualcomm/skills](https://github.com/qualcomm/skills) | **{rc['qualcomm_products']}** | **{rc['qualcomm_skills']}** | {rc.get('qualcomm_notes') or 'IOT/qualcomm-linux skills.json'} |

Raw count favors API/docs/board sharding. This document defines a shared **job taxonomy** and a **scorecard** so catalogs are judged on the same unit of value: a user job.

Companion data: [`data/job-catalog.csv`](data/job-catalog.csv) · [`data/scorecard.json`](data/scorecard.json)."""


def render_scorecard(score: dict[str, Any]) -> str:
    t = score["taxonomy"]
    d = score["depth"]
    nv, amd, qc = t["nvidia"], t["amd"], t["qualcomm"]
    entry = ", ".join(f"`{s}`" for s in t["entry_skills"]) or "none mapped"
    nv_depth = _depth_cell(d["nvidia_median_words"], d["nvidia_skills_measured"], "`--clone-nvidia-depth`")
    amd_depth = _depth_cell(d["amd_median_words"], d["amd_skills_measured"], "`--clone-amd-depth`")
    qc_depth = _depth_cell(
        d["qualcomm_median_words"], d["qualcomm_skills_measured"], "`--clone-qualcomm-depth`"
    )
    return f"""| # | Metric | OEP | NVIDIA | AMD | Qualcomm |
|---|--------|-----|--------|-----|----------|
| 1 | **Jobs covered** | **{t['oep_jobs_covered']} / {t['total_jobs']} ({fmt_pct(t['oep_jobs_covered_pct'])})** | **{nv['jobs_covered']} / {t['total_jobs']} ({fmt_pct(nv['jobs_covered_pct'])})** | **{amd['jobs_covered']} / {t['total_jobs']} ({fmt_pct(amd['jobs_covered_pct'])})** | **{qc['jobs_covered']} / {t['total_jobs']} ({fmt_pct(qc['jobs_covered_pct'])})** |
| 2 | **E2E jobs (OEP)** | **{t['oep_e2e_jobs']}** | — | — | — |
| 3 | **Median skill depth** | **~{d['oep_median_words']} words** | {nv_depth} | {amd_depth} | {qc_depth} |
| 4 | **Mean skills / covered job** | **{t['mean_skills_per_oep_covered_job']:.2f}** | **~{nv['mean_skills_per_covered_job']:.2f}** (≥3: {', '.join(nv['jobs_skills_ge_3']) or 'none'}) | **~{amd['mean_skills_per_covered_job']:.2f}** (≥3: {', '.join(amd['jobs_skills_ge_3']) or 'none'}) | **~{qc['mean_skills_per_covered_job']:.2f}** (≥3: {', '.join(qc['jobs_skills_ge_3']) or 'none'}) |
| 5 | **Entry / routing** | {entry} | leaf catalog | leaf catalog | board-variant shards |

OEP depth floor (words ≥500 or refs >0): **{fmt_pct(d['oep_depth_floor_pct'])}**. NVIDIA: **{fmt_pct(d['nvidia_depth_floor_pct'])}**. AMD: **{fmt_pct(d['amd_depth_floor_pct'])}**. Qualcomm: **{fmt_pct(d['qualcomm_depth_floor_pct'])}**.

**Reading:** AMD/Qualcomm currently cover different product surfaces (LLM/ROCm serve; QLI board bring-up) than OEP’s Edge CV/VSS/RAG taxonomy — low jobs-covered % is expected until they publish overlapping Edge AI jobs. Do not inflate OEP coverage by shrinking the shared denominator.

**Optional sixth (governance):** % of skills with evals + security scan + skill card / signature."""


def render_aggregates(score: dict[str, Any]) -> str:
    t = score["taxonomy"]
    nv, amd, qc = t["nvidia"], t["amd"], t["qualcomm"]
    return f"""| Measure | OEP | NVIDIA | AMD | Qualcomm |
|---------|-----|--------|-----|----------|
| Jobs covered | {t['oep_jobs_covered']} / {t['total_jobs']} | {nv['jobs_covered']} / {t['total_jobs']} | {amd['jobs_covered']} / {t['total_jobs']} | {qc['jobs_covered']} / {t['total_jobs']} |
| Vendor-only jobs (no OEP map) | — | {nv['vendor_only_jobs']} ({', '.join(nv['vendor_only_job_ids']) or '—'}) | {amd['vendor_only_jobs']} ({', '.join(amd['vendor_only_job_ids']) or '—'}) | {qc['vendor_only_jobs']} ({', '.join(qc['vendor_only_job_ids']) or '—'}) |
| OEP∩NVIDIA overlap jobs | {t['overlap_jobs_oep_nvidia']} | {t['overlap_jobs_oep_nvidia']} | — | — |
| Mean skills / covered job | **{t['mean_skills_per_oep_covered_job']:.2f}** | **~{nv['mean_skills_per_covered_job']:.2f}** | **~{amd['mean_skills_per_covered_job']:.2f}** | **~{qc['mean_skills_per_covered_job']:.2f}** |
| Jobs with skills/job ≥ 3 | — | {', '.join(nv['jobs_skills_ge_3']) or '—'} | {', '.join(amd['jobs_skills_ge_3']) or '—'} | {', '.join(qc['jobs_skills_ge_3']) or '—'} |
| OEP skills mapped | {t['oep_skills_mapped']} / {t['oep_skills_total']} | — | — | — |

**Reading:** Compare on jobs and skills-per-job. NVIDIA raw count is dominated by products outside Edge AI overlap (DOCA, Jetson BSP, TAO model shards). AMD is LLM/ROCm-centric. Qualcomm IOT skills are early and board-variant heavy."""


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
        f"- **Stale / unresolved AMD refs** ({len(drift.stale_amd_refs)}): "
        + (", ".join(f"`{s}`" for s in drift.stale_amd_refs) or "none"),
        f"- **Stale / unresolved Qualcomm refs** ({len(drift.stale_qualcomm_refs)}): "
        + (", ".join(f"`{s}`" for s in drift.stale_qualcomm_refs) or "none"),
        f"- **OEP thin skills** (words <400 and no refs): {thin}",
        f"- **Unmapped NVIDIA overlap-product skills** (sample): "
        + (", ".join(f"`{s}`" for s in drift.unmapped_nvidia_overlap[:12]) or "none")
        + (
            f" … +{len(drift.unmapped_nvidia_overlap) - 12} more"
            if len(drift.unmapped_nvidia_overlap) > 12
            else ""
        ),
        f"- **Unmapped AMD skills** ({len(drift.unmapped_amd_skills)}): "
        + (", ".join(f"`{s}`" for s in drift.unmapped_amd_skills) or "none"),
        f"- **Unmapped Qualcomm logical skills** ({len(drift.unmapped_qualcomm_skills)}): "
        + (", ".join(f"`{s}`" for s in drift.unmapped_qualcomm_skills) or "none"),
    ]
    return "\n".join(lines)


def ensure_markers(docs_path: Path) -> None:
    text = docs_path.read_text(encoding="utf-8")
    if BEGIN_SNAPSHOT in text and BEGIN_SCORECARD in text and BEGIN_AGGREGATES in text:
        if BEGIN_DRIFT not in text:
            insert = (
                "\n## Drift report (auto)\n\n"
                f"{BEGIN_DRIFT}\n_Run refresh_scorecard.py_\n{END_DRIFT}\n"
            )
            if "## 8. One-paragraph thesis" in text:
                text = text.replace(
                    "## 8. One-paragraph thesis", insert + "\n## 8. One-paragraph thesis"
                )
            else:
                text = text.rstrip() + "\n" + insert
            docs_path.write_text(text, encoding="utf-8")
        return
    raise RuntimeError(
        f"{docs_path} is missing generation markers. Restore docs/competitive-skill-metrics.md."
    )


def patch_docs(docs_path: Path, score: dict[str, Any], drift: DriftReport) -> None:
    ensure_markers(docs_path)
    text = docs_path.read_text(encoding="utf-8")
    text = replace_marked_section(text, BEGIN_SNAPSHOT, END_SNAPSHOT, render_snapshot(score))
    text = replace_marked_section(text, BEGIN_SCORECARD, END_SCORECARD, render_scorecard(score))
    text = replace_marked_section(text, BEGIN_AGGREGATES, END_AGGREGATES, render_aggregates(score))
    text = replace_marked_section(text, BEGIN_DRIFT, END_DRIFT, render_drift(drift, score))
    docs_path.write_text(text, encoding="utf-8")


def print_summary(score: dict[str, Any], drift: DriftReport) -> None:
    t = score["taxonomy"]
    d = score["depth"]
    rc = score["raw_counts"]
    nv, amd, qc = t["nvidia"], t["amd"], t["qualcomm"]
    print(f"Snapshot {score['snapshot_date']}")
    print(
        f"  Raw skills: OEP {rc['oep_skills']} | NVIDIA ~{rc['nvidia_skills']} | "
        f"AMD {rc['amd_skills']} | Qualcomm {rc['qualcomm_skills']}"
    )
    print(
        f"  Jobs covered / {t['total_jobs']}: "
        f"OEP {t['oep_jobs_covered']} ({t['oep_jobs_covered_pct']}%) | "
        f"NVIDIA {nv['jobs_covered']} ({nv['jobs_covered_pct']}%) | "
        f"AMD {amd['jobs_covered']} ({amd['jobs_covered_pct']}%) | "
        f"Qualcomm {qc['jobs_covered']} ({qc['jobs_covered_pct']}%)"
    )
    print(
        f"  Depth median words: OEP {d['oep_median_words']} | "
        f"NVIDIA {d['nvidia_median_words'] if d['nvidia_median_words'] is not None else 'n/a'} | "
        f"AMD {d['amd_median_words'] if d['amd_median_words'] is not None else 'n/a'} | "
        f"QC {d['qualcomm_median_words'] if d['qualcomm_median_words'] is not None else 'n/a'}"
    )
    print(
        f"  Drift: unmapped_oep={len(drift.unmapped_oep_skills)} "
        f"stale_nv={len(drift.stale_nvidia_refs)} stale_amd={len(drift.stale_amd_refs)} "
        f"stale_qc={len(drift.stale_qualcomm_refs)} "
        f"unmapped_amd={len(drift.unmapped_amd_skills)} unmapped_qc={len(drift.unmapped_qualcomm_skills)}"
    )


def maybe_clone_depth(args: argparse.Namespace, vendor: str, inv: CatalogInventory) -> None:
    clone_flag = getattr(args, f"clone_{vendor}_depth")
    clone_path = getattr(args, f"{vendor}_clone")
    urls = {
        "nvidia": "https://github.com/NVIDIA/skills.git",
        "amd": "https://github.com/amd/skills.git",
        "qualcomm": "https://github.com/qualcomm/skills.git",
    }
    if clone_path:
        inv.depth = measure_clone_depth(clone_path)
    elif clone_flag:
        print(f"Shallow-cloning {vendor} skills for depth stats…", file=sys.stderr)
        with tempfile.TemporaryDirectory(prefix=f"{vendor}-skills-") as tmp:
            shallow_clone(urls[vendor], Path(tmp))
            inv.depth = measure_clone_depth(Path(tmp))


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

    nvidia_text = fetch_text_with_cache(
        local=args.nvidia_readme,
        fetch=args.fetch_nvidia,
        url=NVIDIA_README_URL,
        cache_path=root / "docs" / "data" / "nvidia-skills-README.cache.md",
        gh_api="repos/NVIDIA/skills/readme",
        label="NVIDIA README",
    )
    nvidia = parse_nvidia_readme(nvidia_text)

    amd_text = fetch_text_with_cache(
        local=args.amd_readme,
        fetch=args.fetch_amd,
        url=AMD_README_URL,
        cache_path=root / "docs" / "data" / "amd-skills-README.cache.md",
        gh_api="repos/amd/skills/readme",
        label="AMD README",
    )
    amd = parse_amd_readme(amd_text)

    qc_text = fetch_text_with_cache(
        local=args.qualcomm_json,
        fetch=args.fetch_qualcomm,
        url=QUALCOMM_SKILLS_JSON_URL,
        cache_path=root / "docs" / "data" / "qualcomm-skills.json.cache.json",
        label="Qualcomm skills.json",
    )
    qualcomm = parse_qualcomm_skills_json(qc_text)

    maybe_clone_depth(args, "nvidia", nvidia)
    maybe_clone_depth(args, "amd", amd)
    maybe_clone_depth(args, "qualcomm", qualcomm)

    jobs = load_job_catalog(job_catalog)
    score = compute_scorecard(jobs, oep, nvidia, amd, qualcomm, snapshot_date)
    drift = compute_drift(jobs, oep, nvidia, amd, qualcomm)

    print_summary(score, drift)

    out_json = root / "docs" / "data" / "scorecard.json"
    payload = {"scorecard": score, "drift": asdict(drift)}

    if write_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out_json}")

    if args.write_csv:
        rewrite_csv(job_catalog, jobs, oep, nvidia, amd, qualcomm)
        print(f"Wrote {job_catalog}")

    if args.write_docs:
        patch_docs(docs_path, score, drift)
        print(f"Patched {docs_path}")

    if args.check_only:
        blocking = (
            drift.unmapped_oep_skills
            or drift.stale_oep_refs
            or drift.stale_nvidia_refs
            or drift.stale_amd_refs
            or drift.stale_qualcomm_refs
        )
        return 1 if blocking else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
