<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Multi-CLI Skill Evaluation Runner

`run_multi_cli_eval.py` runs the [skill-creator](https://github.com/anthropics/skill-creator)
evaluation loop for a skill's `evals/evals.json` across **three different
coding-agent CLIs** in one pass — GitHub Copilot CLI, Claude Code CLI, and
OpenAI Codex CLI — then grades every run with an LLM judge and aggregates the
results into benchmark reports, both per-CLI (with the skill vs. without it)
and cross-CLI (which coding agent benefits most from the skill).

## What it does

For every `(cli, eval, configuration)` combination it:

1. Builds a prompt — either the bare eval prompt (`without_skill`) or the
   prompt prefixed with instructions to read and follow the skill's
   `SKILL.md` first (`with_skill`).
2. Runs it through the target CLI's non-interactive/headless mode
   (`copilot -p`, `claude -p`, `codex exec`).
3. Normalizes the output into the exact directory layout skill-creator's own
   tooling (`aggregate_benchmark.py`, `eval-viewer/generate_review.py`)
   expects, so those scripts work unmodified against the results.
4. Grades each run with an LLM judge against the eval's `expectations`
   (or `assertions`), writing `grading.json` in each run directory.
5. Aggregates:
   - **Per-CLI**: `with_skill` vs. `without_skill` pass rate / time / tokens,
     written to `<workspace>/<cli>/benchmark.json` + `benchmark.md`.
   - **Cross-CLI**: `with_skill` pass rate / time / tokens side-by-side for
     every CLI that ran, written to `<workspace>/benchmark.json` +
     `benchmark.md` (top level of the workspace).
6. Copies the full workspace tree to `<skill-path>/benchmark/` so results
   are persisted alongside the skill.

## Prerequisites

- Python 3.10+ (only stdlib is used — no extra `pip install` needed).
- At least one of the CLIs installed and authenticated:
  - GitHub Copilot CLI (`copilot`) — `npm install -g @github/copilot-cli` (or your org's install method), then `copilot` once interactively to authenticate.
  - Claude Code CLI (`claude`) — see [claude.ai/code](https://claude.ai/code), then `claude` once to authenticate.
  - OpenAI Codex CLI (`codex`) — `npm install -g @openai/codex`, requires Node >= 16; run `codex login` once to authenticate.
- The [skill-creator](https://github.com/anthropics/skills) skill
  installed globally (used for its `scripts/aggregate_benchmark.py` and
  `agents/grader.md`). Install it once for all three agents with:

  ```bash
  npx skills add anthropics/skills --skill skill-creator -a github-copilot -a claude-code -a codex -g
  ```

  This installs skill-creator to `~/.agents/skills/skill-creator` (Copilot/Codex)
  and `~/.claude/skills/skill-creator` (Claude Code), which are the default paths
  this script looks for. If your install lives elsewhere, override with:

  ```bash
  export SKILL_CREATOR_DIR=/path/to/skill-creator
  ```

  If skill-creator isn't found, eval **running** still works, but grading
  aggregation (`benchmark.json`/`benchmark.md`) will be skipped with a
  warning.

## Usage

### Simplest form — one required argument

Only `--skill-path` is required. Everything else has a sensible default:

```bash
python3 tools/run_multi_cli_eval.py --skill-path .agents/skills/my-skill
```

Defaults applied automatically:
- Evals loaded from `<skill-path>/evals/evals.json`
- Results written directly to `<skill-path>/benchmark/`
- CLI: `copilot` (using its own default model)
- Both `with_skill` and `without_skill` configs run
- Grader: `copilot` (using its own default model)

### Pin a model

```bash
python3 tools/run_multi_cli_eval.py \
  --skill-path .agents/skills/my-skill \
  --copilot-model claude-sonnet-4-6 \
  --grader-model claude-sonnet-4-6
```

### Run multiple CLIs for a cross-agent comparison

```bash
python3 tools/run_multi_cli_eval.py \
  --skill-path .agents/skills/my-skill \
  --clis copilot,claude \
  --copilot-model claude-sonnet-4-6 \
  --claude-model claude-sonnet-4-6
```

### Use a custom workspace or evals file

```bash
python3 tools/run_multi_cli_eval.py \
  --skill-path .agents/skills/my-skill \
  --evals-json /custom/path/evals.json \
  --workspace /tmp/my-eval-run
```

Results are still copied to `<skill-path>/benchmark/` at the end unless
`--workspace` already points there.

### Run only specific eval IDs

```bash
python3 tools/run_multi_cli_eval.py \
  --skill-path .agents/skills/my-skill \
  --eval-ids 1,3,5
```

### Skip grading or aggregation

```bash
# evals only, no grading
python3 tools/run_multi_cli_eval.py \
  --skill-path .agents/skills/my-skill \
  --skip-grading

# evals + grading, no benchmark aggregation
python3 tools/run_multi_cli_eval.py \
  --skill-path .agents/skills/my-skill \
  --skip-aggregate
```

### Use a different grading judge

```bash
python3 tools/run_multi_cli_eval.py \
  --skill-path .agents/skills/my-skill \
  --grader-cli claude \
  --grader-model claude-sonnet-4-6
```

### Dry run — see the plan without executing

```bash
python3 tools/run_multi_cli_eval.py \
  --skill-path .agents/skills/my-skill \
  --dry-run
```

### Full example with all explicit options

```bash
python3 tools/run_multi_cli_eval.py \
  --skill-path .agents/skills/my-skill \
  --evals-json .agents/skills/my-skill/evals/evals.json \
  --workspace /tmp/my-skill-eval-run \
  --clis copilot,claude,codex \
  --configs with_skill,without_skill \
  --copilot-model claude-sonnet-4-6 \
  --claude-model claude-sonnet-4-6 \
  --codex-model gpt-5.5 \
  --grader-cli copilot \
  --grader-model claude-sonnet-4-6 \
  --workers 4 \
  --timeout 600
```

## Output layout

```
<workspace>/
├── run_summary.json                    # per-run timing/token/error summary
├── benchmark.json / benchmark.md       # cross-CLI comparison
├── copilot/
│   ├── benchmark.json / benchmark.md   # with_skill vs without_skill, this CLI
│   └── eval-<id>-<name>/
│       └── <config>/
│           ├── eval_metadata.json
│           └── run-1/
│               ├── transcript.md
│               ├── timing.json
│               ├── grading.json
│               └── outputs/
│                   ├── response.md
│                   ├── metrics.json
│                   └── diagnostics.json
├── claude/  ... (same layout)
└── codex/   ... (same layout)
```

The full workspace is also copied to `<skill-path>/benchmark/` at the end,
unless the workspace was already set to that path (the default).

## Viewing results

Use skill-creator's own viewer against any per-CLI directory:

```bash
python3 $SKILL_CREATOR_DIR/eval-viewer/generate_review.py \
  <workspace>/copilot \
  --skill-name my-skill \
  --benchmark <workspace>/copilot/benchmark.json \
  --static <workspace>/copilot/review.html
```

(`--static` is required in headless environments — it writes a standalone
HTML file instead of starting a server.)

## Flag reference

| Flag | Default | Description |
|---|---|---|
| `--skill-path` | *(required)* | Path to the skill directory (contains `SKILL.md`) |
| `--evals-json` | `<skill-path>/evals/evals.json` | Path to the skill's evals JSON |
| `--workspace` | `<skill-path>/benchmark` | Output workspace directory |
| `--clis` | `copilot` | Comma-separated CLIs: `copilot`, `claude`, `codex` |
| `--configs` | `with_skill,without_skill` | Comma-separated configs to run |
| `--workers` | `4` | Max concurrent subprocess runs |
| `--timeout` | `600` | Per-run timeout in seconds |
| `--eval-ids` | *(all)* | Comma-separated eval IDs to restrict to |
| `--copilot-bin` | *(auto-detect)* | Explicit path to the `copilot` binary |
| `--claude-bin` | *(auto-detect)* | Explicit path to the `claude` binary |
| `--codex-bin` | *(auto-detect / nvm fallback)* | Explicit path to the `codex` binary |
| `--copilot-model` | *(CLI default)* | Model for copilot runs; also grader fallback when `--grader-cli copilot` |
| `--claude-model` | *(CLI default)* | Model for claude runs |
| `--codex-model` | *(CLI default)* | Model for codex runs |
| `--skill-name` | *(skill dir name)* | Skill name in benchmark metadata |
| `--grader-cli` | `copilot` | CLI to use as the LLM grading judge |
| `--grader-model` | `--copilot-model` or *(CLI default)* | Model for the grading judge |
| `--grader-workers` | `4` | Max concurrent grading calls |
| `--grader-timeout` | `180` | Per-grading-call timeout in seconds |
| `--skip-grading` | `false` | Skip LLM grading |
| `--skip-aggregate` | `false` | Skip `benchmark.json`/`.md` generation |
| `--dry-run` | `false` | Print the plan without running anything |

## Troubleshooting

When a run fails, the console reports the cause and points to
`outputs/diagnostics.json`. Common issues:

- **Authentication**: run the CLI interactively once (`copilot`, `claude`, or `codex login`).
- **Rate limits / quota**: check account usage and retry later, optionally with a different `--grader-cli`.
- **Invalid model**: verify the `--*-model` value and account access.
- **Codex sandbox on nested containers**: the `workspace-write` sandbox uses
  bubblewrap which can fail inside rootless containers; the script retries
  automatically with `--sandbox danger-full-access`.
- **Grader partial failure**: already-graded runs are skipped on rerun, so
  re-running the same command resumes where it left off.

## Notes

- **Codex model attribution**: Codex's JSON output doesn't expose which model
  served the request. Pass `--codex-model` explicitly for precise labeling.
- **Copilot token counts**: recovered via OpenTelemetry (`COPILOT_OTEL_FILE_EXPORTER_PATH`);
  falls back to `null` if a future CLI version removes those attributes.
- **Portability**: `evals.json` must follow skill-creator's schema —
  an `evals` array with `id`, `prompt`, and `assertions` or `expectations`.
