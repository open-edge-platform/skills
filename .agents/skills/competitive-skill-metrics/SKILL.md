---
name: competitive-skill-metrics
description: >-
  Refresh and maintain competitive skill metrics that compare open-edge-platform/skills
  to NVIDIA/skills, amd/skills, and qualcomm/skills using a shared job taxonomy — not
  raw skill count. Use whenever the user asks to update competitive metrics, recompute
  the scorecard, remap jobs after skills are added/removed/renamed, measure skill depth
  or skills-per-job, check catalog drift vs NVIDIA/AMD/Qualcomm, prepare management
  slides on skills competitiveness, or run refresh_scorecard.py. Do not use for
  authoring product skills or deploying Edge AI apps.
license: Apache-2.0
compatibility: >-
  Requires: Python 3.10+, network access to raw.githubusercontent.com (or gh CLI) for
  NVIDIA/AMD READMEs and Qualcomm skills.json; optional git to shallow-clone vendor
  repos for depth stats. Run from an open-edge-platform/skills checkout.
metadata:
  author: open-edge-platform
  version: "1.1.0"
  tags: "competitive-metrics scorecard job-taxonomy nvidia amd qualcomm granularity depth"
allowed-tools: bash python git gh
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Competitive Skill Metrics

Keep the **job-based** comparison of open-edge-platform (OEP) skills vs
[NVIDIA/skills](https://github.com/NVIDIA/skills),
[amd/skills](https://github.com/amd/skills), and
[qualcomm/skills](https://github.com/qualcomm/skills) current as catalogs evolve.

**Unit of value is a user job, not a skill folder.** Never recommend inflating skill
count for parity. Prefer deeper skills, progressive disclosure, and orchestrators.

## Artifacts (repo root = open-edge-platform/skills)

Paths under `docs/` are **repo-root-relative** (outside this skill package — do not use
`../` markdown links; skill-validator rejects path traversal). Resolve them via
`$REPO_ROOT` from Step 1. Skill-local files use normal relative links.

| Path | Role |
|------|------|
| `docs/competitive-skill-metrics.md` | Narrative + rubric + scorecard (generated sections marked) |
| `docs/data/job-catalog.csv` | Canonical job ↔ OEP/NVIDIA/AMD/Qualcomm skill map |
| `docs/data/scorecard.json` | Machine-readable latest aggregates + drift |
| `docs/data/nvidia-skills-README.cache.md` | Offline NVIDIA catalog cache |
| `docs/data/amd-skills-README.cache.md` | Offline AMD catalog cache |
| `docs/data/qualcomm-skills.json.cache.json` | Offline Qualcomm IOT skills.json cache |
| [`scripts/refresh_scorecard.py`](scripts/refresh_scorecard.py) | Inventory catalogs; recompute; patch docs |

Load [`references/remap-guide.md`](references/remap-guide.md) when adding jobs or
changing skill mappings. Load
[`references/rubric-summary.md`](references/rubric-summary.md) when explaining metrics
to stakeholders.

## When to use

- “Update competitive metrics / scorecard”
- Skills were added, removed, or renamed in OEP, NVIDIA, AMD, or Qualcomm
- Management wants jobs-covered / depth / skills-per-job (not count-for-count)
- Quarterly competitive review across vendors
- CI-style drift check (`--check-only`)

## Procedure

### Step 1 — Confirm repo root

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
test -f "$REPO_ROOT/docs/data/job-catalog.csv"
SKILL_DIR="$REPO_ROOT/.agents/skills/competitive-skill-metrics"
```

If `job-catalog.csv` is missing, stop and restore it from git history or recreate from
the taxonomy in `docs/competitive-skill-metrics.md`.

### Step 2 — Refresh inventories and scorecard (always)

Default refresh (OEP depth + vendor catalog inventories; no vendor depth clones):

```bash
python3 "$SKILL_DIR/scripts/refresh_scorecard.py" \
  --repo-root "$REPO_ROOT" \
  --write-docs --write-csv
```

With per-vendor depth (network + disk; preferred for exec reviews):

```bash
python3 "$SKILL_DIR/scripts/refresh_scorecard.py" \
  --repo-root "$REPO_ROOT" \
  --clone-nvidia-depth --clone-amd-depth --clone-qualcomm-depth \
  --write-docs --write-csv
```

Offline / pinned caches:

```bash
python3 "$SKILL_DIR/scripts/refresh_scorecard.py" \
  --repo-root "$REPO_ROOT" \
  --nvidia-readme "$REPO_ROOT/docs/data/nvidia-skills-README.cache.md" \
  --amd-readme "$REPO_ROOT/docs/data/amd-skills-README.cache.md" \
  --qualcomm-json "$REPO_ROOT/docs/data/qualcomm-skills.json.cache.json" \
  --no-fetch-nvidia --no-fetch-amd --no-fetch-qualcomm \
  --write-docs --write-csv
```

Successful live fetches refresh those cache files automatically.
The script:

1. Inventories `.agents/skills/` (excludes this meta-skill).
2. Fetches/parses NVIDIA + AMD README catalogs and Qualcomm `skills.json`.
3. Recomputes coverage, skills-per-job, depth, thin skills per vendor.
4. Writes `docs/data/scorecard.json`.
5. With `--write-csv`, refreshes derived columns on `job-catalog.csv`.
6. With `--write-docs`, patches sections between `<!-- BEGIN GENERATED:* -->` markers.

### Step 3 — Read the drift report

Open the **Drift report (auto)** section in `docs/competitive-skill-metrics.md` or:

```bash
python3 -c "import json;print(json.load(open('$REPO_ROOT/docs/data/scorecard.json'))['drift'])"
```

| Drift signal | Action |
|--------------|--------|
| `unmapped_oep_skills` | Map to an existing job or **add a job row** in the CSV (see remap guide) |
| `stale_oep_refs` | Fix renamed/removed skill names in `oep_skills` |
| `stale_nvidia_refs` / `stale_amd_refs` / `stale_qualcomm_refs` | Fix renamed refs or wildcards |
| `unmapped_nvidia_overlap` | Review sample; map only when they complete a taxonomy job |
| `unmapped_amd_skills` / `unmapped_qualcomm_skills` | Map or add competitor-only job rows |
| `oep_thin_skills` | Recommend deepen with `references/` or merge — **not** more shards |

### Step 4 — Remap when needed (judgment required)

The script **does not invent job mappings**. When drift shows unmapped OEP skills or
meaningful new vendor overlap skills:

1. Load [`references/remap-guide.md`](references/remap-guide.md).
2. Edit `docs/data/job-catalog.csv` (add/adjust rows; keep `job_id` stable when possible).
3. Re-run Step 2.
4. Summarize for the user: jobs covered delta per vendor, skills/job, new gaps, merge/split notes.

### Step 5 — Optional drift gate

```bash
python3 "$SKILL_DIR/scripts/refresh_scorecard.py" --repo-root "$REPO_ROOT" --check-only
```

Exits `1` if unmapped OEP skills or stale OEP/NVIDIA/AMD/Qualcomm refs exist.

### Step 6 — Report to the user

Lead with the headline metrics from the scorecard (jobs covered per vendor, E2E, depth,
skills/job, entry routing). Mention raw counts only as packaging context. Call out that
AMD (LLM/ROCm) and Qualcomm (QLI board bring-up) currently sit on **adjacent** product
surfaces — low jobs-covered % is expected, not an OEP coverage trick. Do **not** propose
“add N skills to match vendor count.”

## Edge cases

- **Vendor README / JSON parse fails:** Use caches under `docs/data/` or pass
  `--nvidia-readme` / `--amd-readme` / `--qualcomm-json`.
- **Markers missing in the markdown:** Restore `docs/competitive-skill-metrics.md` from git.
- **Sync would delete this skill:** It must remain listed in `skills-config.json` under
  product source `open-edge-platform/skills`.
- **CUDA/DOCA-only NVIDIA or planned AMD skills:** Out of taxonomy unless you deliberately
  add jobs; do not inflate the denominator for OEP coverage theater. Skip AMD `planned`
  table rows (no published link).

## Examples

**Input:** “Refresh competitive metrics vs NVIDIA, AMD, and Qualcomm.”

**Actions:** Run Step 2 (with depth clones if network allows), show headline table + drift,
stop unless remap needed.

**Input:** “We added `foo-bar-user`; update the scorecard.”

**Actions:** Refresh → see `foo-bar-user` in unmapped → propose job ID / domain → edit CSV → refresh again.
