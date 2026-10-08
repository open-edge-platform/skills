---
name: competitive-skill-metrics
description: >-
  Refresh and maintain competitive skill metrics that compare open-edge-platform/skills
  to NVIDIA/skills using a shared job taxonomy — not raw skill count. Use whenever the
  user asks to update competitive metrics, recompute the scorecard, remap jobs after
  skills are added/removed/renamed, measure skill depth or skills-per-job, check catalog
  drift vs NVIDIA, prepare management slides on skills competitiveness, or run
  refresh_scorecard.py. Do not use for authoring product skills or deploying Edge AI apps.
license: Apache-2.0
compatibility: >-
  Requires: Python 3.10+, network access to raw.githubusercontent.com (or gh CLI) for
  NVIDIA/skills README; optional git to shallow-clone NVIDIA/skills for depth stats.
  Run from an open-edge-platform/skills checkout.
metadata:
  author: open-edge-platform
  version: "1.0.0"
  tags: "competitive-metrics scorecard job-taxonomy nvidia granularity depth"
allowed-tools: bash python git gh
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Competitive Skill Metrics

Keep the **job-based** comparison of open-edge-platform (OEP) skills vs
[NVIDIA/skills](https://github.com/NVIDIA/skills) current as both catalogs evolve.

**Unit of value is a user job, not a skill folder.** Never recommend inflating skill
count for parity. Prefer deeper skills, progressive disclosure, and orchestrators.

## Artifacts (repo root = open-edge-platform/skills)

| Path | Role |
|------|------|
| [`docs/competitive-skill-metrics.md`](../../../docs/competitive-skill-metrics.md) | Narrative + rubric + scorecard (generated sections marked) |
| [`docs/data/job-catalog.csv`](../../../docs/data/job-catalog.csv) | Canonical job ↔ skill map (edit by hand for remaps) |
| [`docs/data/scorecard.json`](../../../docs/data/scorecard.json) | Machine-readable latest aggregates + drift |
| [`scripts/refresh_scorecard.py`](scripts/refresh_scorecard.py) | Inventory both catalogs; recompute; patch docs |

Load [`references/remap-guide.md`](references/remap-guide.md) when adding jobs or
changing OEP/NVIDIA skill mappings. Load
[`references/rubric-summary.md`](references/rubric-summary.md) when explaining metrics
to stakeholders.

## When to use

- “Update competitive metrics / scorecard”
- Skills were added, removed, or renamed in OEP or NVIDIA
- Management wants jobs-covered / depth / skills-per-job (not count-for-count)
- Quarterly competitive review
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

Default refresh (OEP depth + NVIDIA catalog counts from README; no NVIDIA depth):

```bash
python3 "$SKILL_DIR/scripts/refresh_scorecard.py" \
  --repo-root "$REPO_ROOT" \
  --write-docs --write-csv
```

With NVIDIA per-skill depth (network + disk; preferred for exec reviews):

```bash
python3 "$SKILL_DIR/scripts/refresh_scorecard.py" \
  --repo-root "$REPO_ROOT" \
  --clone-nvidia-depth \
  --write-docs --write-csv
```

Or reuse an existing clone:

```bash
python3 "$SKILL_DIR/scripts/refresh_scorecard.py" \
  --repo-root "$REPO_ROOT" \
  --nvidia-clone /path/to/NVIDIA/skills \
  --write-docs --write-csv
```

Offline / pinned NVIDIA README (or when network fails, script falls back to
`docs/data/nvidia-skills-README.cache.md`):

```bash
python3 "$SKILL_DIR/scripts/refresh_scorecard.py" \
  --repo-root "$REPO_ROOT" \
  --nvidia-readme "$REPO_ROOT/docs/data/nvidia-skills-README.cache.md" \
  --no-fetch-nvidia \
  --write-docs --write-csv
```

Successful live fetches refresh that cache file automatically.
The script:

1. Inventories `.agents/skills/` (excludes this meta-skill).
2. Fetches/parses the NVIDIA catalog table from their README.
3. Recomputes coverage, skills-per-job, depth, thin skills.
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
| `stale_nvidia_refs` | Fix renamed NVIDIA skills or wildcards |
| `unmapped_nvidia_overlap` | Review sample; map only when they complete a taxonomy job |
| `oep_thin_skills` | Recommend deepen with `references/` or merge — **not** more shards |

### Step 4 — Remap when needed (judgment required)

The script **does not invent job mappings**. When drift shows unmapped OEP skills or
meaningful new NVIDIA overlap skills:

1. Load [`references/remap-guide.md`](references/remap-guide.md).
2. Edit `docs/data/job-catalog.csv` (add/adjust rows; keep `job_id` stable when possible).
3. Re-run Step 2.
4. Summarize for the user: jobs covered delta, skills/job, new gaps, merge/split notes.

### Step 5 — Optional drift gate

```bash
python3 "$SKILL_DIR/scripts/refresh_scorecard.py" --repo-root "$REPO_ROOT" --check-only
```

Exits `1` if unmapped OEP skills or stale OEP/NVIDIA refs exist.

### Step 6 — Report to the user

Lead with the five headline metrics from the scorecard (jobs covered, E2E, depth,
skills/job, entry routing). Mention raw counts only as packaging context. List
actionable gaps and thin skills. Do **not** propose “add N skills to match NVIDIA count.”

## Edge cases

- **NVIDIA README parse fails:** Save a local copy (`gh api repos/NVIDIA/skills/readme -H Accept:application/vnd.github.raw > /tmp/nv-readme.md`) and pass `--nvidia-readme`.
- **Markers missing in the markdown:** Restore `docs/competitive-skill-metrics.md` from git; markers are required for `--write-docs`.
- **Sync would delete this skill:** It must remain listed in `skills-config.json` under product source `open-edge-platform/skills`.
- **Comparing CUDA/DOCA-only NVIDIA skills:** Out of taxonomy scope unless you deliberately add jobs; do not inflate the denominator for OEP coverage theater.

## Examples

**Input:** “Refresh competitive metrics vs NVIDIA.”

**Actions:** Run Step 2 (with `--clone-nvidia-depth` if network allows), show headline table + drift, stop unless remap needed.

**Input:** “We added `foo-bar-user`; update the scorecard.”

**Actions:** Refresh → see `foo-bar-user` in unmapped → propose job ID / domain → edit CSV → refresh again.
