# Remap guide

Use this when `refresh_scorecard.py` reports unmapped or stale skill references.

## Principles

1. **Jobs first.** A row is one user outcome with one success criterion.
2. **Split** only when tools, permissions, failure modes, or audiences differ.
3. **Do not split** for parameters (model name, install flavor, one API symbol).
4. **Orchestrate** when the user cannot know the leaf skill up front (`routing=entry`).
5. **Never** add skills only to raise raw count.

## CSV columns

| Column | Meaning |
|--------|---------|
| `job_id` | Stable ID (`DOMAIN-##`); keep stable across renames when the job is the same |
| `domain` | Taxonomy domain (`vss`, `cv-train`, `pai-runtime`, …) |
| `job` | Short success-oriented description |
| `e2e` | `Y` if path reaches a verified running/exported artifact |
| `oep_skills` | `;`-separated OEP skill directory names (empty = OEP gap) |
| `nvidia_skills` | `;`-separated NVIDIA skill names; `prefix*` wildcards allowed |
| `routing` | `entry` \| `leaf` \| `gap` \| `gap-nvidia-only` |
| `notes` | Fit / gap / thin / over-split notes |
| derived | `oep_skills_per_job`, `nvidia_skills_per_job`, `oep_median_words`, `oep_has_refs` — rewritten by the script |

## When an OEP skill is unmapped

Ask, in order:

1. Does it complete an **existing** job? → append to that row’s `oep_skills` (rare; prefer 1:1).
2. Is it a **new job** in an existing domain? → add a row with the next free `job_id`.
3. Is it a **contributor/extension** skill (add backend, add model)? → still a job, mark `e2e=N`.
4. Is it **meta/index tooling** (like this skill)? → exclude from product inventory (script already skips `competitive-skill-metrics`).

## When NVIDIA skills appear in the unmapped overlap sample

Map only if they clearly finish a taxonomy job. Patterns that inflate count without a new job:

- One skill per library/API (`doca-*`, many `tao-train-*`)
- One skill per install flavor (wheel / conda / debian / container)
- Calibration micro-steps that belong under one deploy job

Prefer updating `nvidia_skills` on an existing row (including wildcards like `i4h-workflow-dataset-*`) over adding NVIDIA-only vanity jobs — unless leadership wants an explicit **gap** row (`routing=gap`).

## After editing the CSV

```bash
python3 .agents/skills/competitive-skill-metrics/scripts/refresh_scorecard.py \
  --write-docs --write-csv
```

Confirm drift is clean (or only contains intentional NVIDIA overlap review noise).
