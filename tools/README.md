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

## Prerequisites

- Python 3.10+ (only stdlib is used — no extra `pip install` needed).
- At least one of the CLIs installed and authenticated:
  - GitHub Copilot CLI (`copilot`) — `npm install -g @github/copilot-cli` (or your org's install method), then `copilot` once interactively to authenticate.
  - Claude Code CLI (`claude`) — see [claude.ai/code](https://claude.ai/code), then `claude` once to authenticate.
  - OpenAI Codex CLI (`codex`) — `npm install -g @openai/codex`, requires Node >= 16; run `codex login` once to authenticate.
- The [skill-creator](https://github.com/anthropics/skill-creator) skill
  installed locally (used for its `scripts/aggregate_benchmark.py` and
  `agents/grader.md`). By default this script looks for it at
  `~/.agents/skills/skill-creator`; override with the `SKILL_CREATOR_DIR`
  environment variable if yours lives elsewhere:

  ```bash
  export SKILL_CREATOR_DIR=/path/to/skill-creator
  ```

  If skill-creator isn't found, eval **running** still works, but grading
  aggregation (`benchmark.json`/`benchmark.md`) will be skipped with a
  warning — grade/aggregate manually with skill-creator's own
  `aggregate_benchmark.py` in that case.

## Usage

Run the full pipeline (evals → grading → aggregation) for any skill. By default all three
CLIs run — omit `--clis` to use the default, or restrict to a subset as needed:

```bash
python3 tools/run_multi_cli_eval.py \
  --evals-json /path/to/my-skill/evals/evals.json \
  --skill-path /path/to/my-skill \
  --workspace /tmp/my-skill-eval-run \
  --clis copilot,claude,codex \
  --configs with_skill,without_skill \
  --grader-cli copilot
```

This produces:

```
/tmp/my-skill-eval-run/
├── run_summary.json                    # per-run timing/token/error summary
├── benchmark.json / benchmark.md       # cross-CLI comparison (written when ≥2 CLIs run)
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
│                   └── metrics.json
├── claude/  ... (same layout)
└── codex/   ... (same layout)
```

### Only run a subset of CLIs or configs

```bash
python3 tools/run_multi_cli_eval.py \
  --evals-json /path/to/my-skill/evals/evals.json \
  --skill-path /path/to/my-skill \
  --workspace /tmp/my-skill-eval-run \
  --clis copilot,claude \
  --configs with_skill
```

### Only run specific eval IDs

```bash
python3 tools/run_multi_cli_eval.py \
  --evals-json /path/to/my-skill/evals/evals.json \
  --skill-path /path/to/my-skill \
  --workspace /tmp/my-skill-eval-run \
  --eval-ids 1,3,5
```

### Skip grading or aggregation

Useful for a fast smoke test of the eval-running stage only, or if you want
to grade manually:

```bash
python3 tools/run_multi_cli_eval.py \
  --evals-json /path/to/my-skill/evals/evals.json \
  --skill-path /path/to/my-skill \
  --workspace /tmp/my-skill-eval-run \
  --clis copilot,claude,codex \
  --configs with_skill,without_skill \
  --skip-grading
```

To also skip aggregation:

```bash
python3 tools/run_multi_cli_eval.py \
  --evals-json /path/to/my-skill/evals/evals.json \
  --skill-path /path/to/my-skill \
  --workspace /tmp/my-skill-eval-run \
  --clis copilot,claude,codex \
  --configs with_skill,without_skill \
  --skip-grading \
  --skip-aggregate
```

### Choose which CLI acts as the grading judge

By default the script picks the first available CLI in the order
claude → copilot → codex. Override explicitly:

```bash
python3 tools/run_multi_cli_eval.py \
  --evals-json /path/to/my-skill/evals/evals.json \
  --skill-path /path/to/my-skill \
  --workspace /tmp/my-skill-eval-run \
  --grader-cli copilot
```

If your chosen judge CLI hits a rate limit or quota mid-run, re-running the
same command is safe — `grade_all_runs` only grades runs that don't already
have a `grading.json`, so it picks up where it left off (optionally with a
different `--grader-cli`).

### Point at a specific CLI binary

If a CLI isn't on `PATH` (e.g. Codex installed under an `nvm` Node version),
pass its path explicitly:

```bash
python3 tools/run_multi_cli_eval.py \
  --evals-json /path/to/my-skill/evals/evals.json \
  --skill-path /path/to/my-skill \
  --workspace /tmp/my-skill-eval-run \
  --codex-bin ~/.nvm/versions/node/v24.18.0/bin/codex
```

### Pin a specific model per CLI

By default each CLI picks its own built-in default model, and the benchmark
reports label the run with whatever model it turns out to have used
(see [Model tracking](#model-tracking-in-benchmark-reports) below). To pin a
specific model instead (e.g. to compare the same model across CLIs, or a
cheaper/faster model for quick iteration):

```bash
python3 tools/run_multi_cli_eval.py \
  --evals-json /path/to/my-skill/evals/evals.json \
  --skill-path /path/to/my-skill \
  --workspace /tmp/my-skill-eval-run \
  --copilot-model claude-sonnet-5 \
  --claude-model claude-sonnet-4-6 \
  --codex-model gpt-5.5
```

### Dry run (see the execution plan without running anything)

```bash
python3 tools/run_multi_cli_eval.py \
  --evals-json /path/to/my-skill/evals/evals.json \
  --skill-path /path/to/my-skill \
  --workspace /tmp/my-skill-eval-run \
  --dry-run
```

### Full flag reference

| Flag | Required | Default | Description |
|---|---|---|---|
| `--evals-json` | **yes** | — | Path to the skill's `evals/evals.json` |
| `--skill-path` | **yes** | — | Path to the skill directory (contains `SKILL.md`) |
| `--workspace` | **yes** | — | Output workspace directory |
| `--clis` | no | `copilot,claude,codex` | Comma-separated list of CLIs to run |
| `--configs` | no | `with_skill,without_skill` | Comma-separated configs to run |
| `--workers` | no | `4` | Max concurrent subprocess runs |
| `--timeout` | no | `300` | Per-run timeout in seconds |
| `--eval-ids` | no | *(all)* | Comma-separated eval IDs to restrict to |
| `--copilot-bin` | no | *(auto-detect)* | Explicit path to the `copilot` binary |
| `--claude-bin` | no | *(auto-detect)* | Explicit path to the `claude` binary |
| `--codex-bin` | no | *(auto-detect)* | Explicit path to the `codex` binary |
| `--copilot-model` | no | *(Copilot CLI default)* | Model to pass to `copilot` via `--model` |
| `--claude-model` | no | *(Claude Code CLI default)* | Model to pass to `claude` via `--model` |
| `--codex-model` | no | *(Codex CLI default)* | Model to pass to `codex` via `-m`/`--model` |
| `--skill-name` | no | skill directory name | Skill name used in benchmark metadata |
| `--grader-cli` | no | *(first of claude/copilot/codex found)* | CLI to use as the LLM grading judge |
| `--grader-workers` | no | `4` | Max concurrent grading calls |
| `--grader-timeout` | no | `180` | Per-grading-call timeout in seconds |
| `--skip-grading` | no | `false` | Only run evals, skip LLM grading |
| `--skip-aggregate` | no | `false` | Skip `benchmark.json`/`.md` generation |
| `--dry-run` | no | `false` | Print the execution plan without running anything |

## Viewing the results

Once the pipeline finishes, use skill-creator's own viewer against any
per-CLI directory (it needs no modification — the directory layout this
script produces is already compatible):

```bash
python3 $SKILL_CREATOR_DIR/eval-viewer/generate_review.py \
  /tmp/my-skill-eval-run/claude \
  --skill-name my-skill \
  --benchmark /tmp/my-skill-eval-run/claude/benchmark.json \
  --static /tmp/my-skill-eval-run/claude/review.html
```

(`--static` is required in headless environments without a display/browser —
it writes a standalone HTML file you can open locally instead of starting a
server.)

## Model tracking in benchmark reports

Each run's `timing.json` records a `model` field showing which model actually
answered the prompt, and the **Model** line in every `benchmark.md` is
derived from that (the most common value seen across that CLI's runs), not a
placeholder:

- **Copilot**: read directly from the CLI's own JSON event stream
  (`assistant.message`/`assistant.turn_start` events include the model that
  served each turn) — this is exact, whether or not you pinned one with
  `--copilot-model`.
- **Claude**: read from the `modelUsage` field in the CLI's JSON output. Claude
  Code sometimes routes small subagent/title-generation calls to a cheaper
  model (e.g. `claude-haiku-4-5`) alongside the model that produced the actual
  answer — this script picks whichever model produced the most output tokens,
  since that's the one whose response is being graded.
- **Codex**: its non-interactive JSON output (`codex exec --json`) does not
  expose which model served the request anywhere in the event stream, even
  with debug logging. If you passed `--codex-model`, that's what gets
  recorded (accurate, since you told it explicitly which model to use).
  Otherwise the report will say `unspecified (codex CLI default)` — pass
  `--codex-model` explicitly if you need a precise label for Codex runs.

If you're aggregating an older run that predates this field (`timing.json`
has no `model` key), the report will say
`unknown (recorded before model tracking was added — re-run to capture it)`.

## Notes and known limitations

- **Codex CLI setup**: requires Node.js ≥ 16. If your system default Node is
  older, install Codex under a newer Node version (e.g. via `nvm`) and pass
  `--codex-bin` pointing at that installation.
- **Copilot CLI token counts**: the Copilot CLI's `--output-format json` event
  stream does not expose a token-usage field (the final `result` event's
  `usage` object only has premium-request/duration fields). To recover real
  counts, this script sets `COPILOT_OTEL_FILE_EXPORTER_PATH` to a temporary
  file for each Copilot invocation, which makes the CLI additionally emit
  OpenTelemetry GenAI spans/metrics as JSON lines (see `copilot help
  monitoring`). It sums `gen_ai.usage.input_tokens` + `gen_ai.usage.output_tokens`
  across every `chat <model>` span (there can be more than one per run if the
  agent makes multiple LLM calls, e.g. across tool-use turns), then deletes
  the temp file. This is the officially documented telemetry mechanism, so it
  should remain stable across CLI updates; if a future Copilot CLI version
  removes/renames these attributes, `total_tokens` will fall back to `null`
  for that run rather than raising an error.
- **Codex model attribution**: see [Model tracking](#model-tracking-in-benchmark-reports)
  above — pin `--codex-model` explicitly if precise model labeling for Codex
  matters for your comparison.
- **Grader quota/rate limits**: LLM grading makes one CLI call per ungraded
  run. If the judge CLI hits a session limit partway through, re-run the
  command (optionally with a different `--grader-cli`) — already-graded runs
  are skipped automatically.
- **Portability**: this script assumes `evals.json` uses the schema
  documented in skill-creator's `references/schemas.md` (an `evals` array of
  objects with `id`, `prompt`, and either `assertions` or `expectations`).
  Both field names are accepted.
