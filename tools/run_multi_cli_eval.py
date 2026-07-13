#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
run_multi_cli_eval.py — skill-creator style eval runner across multiple CLI agents.

Runs the prompts in a skill's evals/evals.json against a real SKILL.md through
three different headless/non-interactive CLI agents:

  - GitHub Copilot CLI  (`copilot -p ...`)
  - Claude Code CLI     (`claude -p ...`)
  - OpenAI Codex CLI    (`codex exec ...`)

For each (cli, eval, configuration) triple it produces the exact directory
layout the skill-creator skill expects, so the existing tooling keeps working
unchanged:

    <workspace>/<cli>/eval-<id>-<name>/<config>/run-1/
        eval_metadata.json     # eval_id, eval_name, prompt, assertions
        transcript.md           # human-readable turn-by-turn transcript
        timing.json             # duration_ms / total_duration_seconds / total_tokens
        outputs/
            response.md          # final assistant message
            metrics.json         # tool_calls, total_tool_calls, total_steps, ...

`configuration` is one of:
  - with_skill:    the prompt is prefixed with instructions to read and follow
                   the skill's SKILL.md before answering.
  - without_skill: the bare eval prompt, run in a neutral scratch directory so
                   the CLI can't accidentally auto-discover the skill on its own.

After execution, this script also GRADES each run (using one of the CLIs as
an LLM judge, following the same criteria as skill-creator's agents/grader.md)
and AGGREGATES the results:

  1. Per-CLI benchmark: with_skill vs without_skill pass rate/time/tokens,
     written to <workspace>/<cli>/benchmark.json + benchmark.md (via the
     existing scripts.aggregate_benchmark, imported unmodified).
  2. Cross-CLI comparison: with_skill pass rate/time/tokens side-by-side for
     every CLI that was run, written to <workspace>/benchmark.json +
     <workspace>/benchmark.md — this answers "which coding agent performs
     best with this skill loaded?"

You can still point the normal skill-creator viewer at any of these:

    python eval-viewer/generate_review.py <workspace>/<cli> --static review.html

Usage:
    python3 run_multi_cli_eval.py \
        --evals-json /path/to/skill/evals/evals.json \
        --skill-path /path/to/skill \
        --workspace /path/to/output-workspace \
        --clis copilot,claude,codex \
        --configs with_skill,without_skill \
        --workers 4 \
        --timeout 300 \
        --grader-cli claude

Flags to control the extra stages:
    --skip-grading      Only run evals, skip the LLM-grading step.
    --skip-aggregate    Skip benchmark.json/.md generation (implies grading
                        still runs, but nothing is summarized).
    --grader-cli        Which CLI to use as the grading judge (default: the
                        first of claude/copilot/codex found on PATH). The
                        grader is always run against a "neutral" copy of the
                        instructions — it doesn't matter which CLI executed
                        the eval, the grader just reads transcript+outputs.

Prerequisites:
  - `copilot` and `claude` CLIs on PATH and already authenticated.
  - `codex` CLI on PATH and already authenticated (`codex login`). If it was
    installed under an nvm-managed Node version, pass --codex-bin explicitly
    or make sure `codex` resolves on PATH (e.g. `nvm use <version>` first).
"""
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Reuse skill-creator's own aggregation logic rather than reimplementing it —
# keeps the two-config (with_skill vs without_skill) stats identical to what
# the rest of the skill-creator toolchain produces. skill-creator is normally
# installed per-user under ~/.agents/skills/skill-creator; override with the
# SKILL_CREATOR_DIR env var if yours lives elsewhere.
SKILL_CREATOR_DIR = Path(os.environ.get("SKILL_CREATOR_DIR", str(Path.home() / ".agents" / "skills" / "skill-creator")))
if str(SKILL_CREATOR_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_CREATOR_DIR))
try:
    from scripts.aggregate_benchmark import (  # type: ignore
        calculate_stats,
        generate_benchmark,
        generate_markdown,
    )
except ImportError:
    calculate_stats = generate_benchmark = generate_markdown = None  # type: ignore


GRADER_MD_PATH = SKILL_CREATOR_DIR / "agents" / "grader.md"


# --------------------------------------------------------------------------
# Data types
# --------------------------------------------------------------------------

@dataclass
class RunResult:
    """Normalized result of one CLI invocation, independent of which CLI ran it."""
    response_text: str = ""
    transcript_lines: list[str] = field(default_factory=list)
    tool_calls: dict[str, int] = field(default_factory=dict)
    total_steps: int = 0
    errors_encountered: int = 0
    total_tokens: int | None = None
    duration_seconds: float = 0.0
    error: str | None = None
    raw_stdout: str = ""
    raw_stderr: str = ""
    model: str | None = None


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------

def build_prompt(eval_prompt: str, skill_path: str | None) -> str:
    """Build the task prompt. If skill_path is given, instruct the agent to
    read and follow that skill's SKILL.md before answering — this works
    identically across all three CLIs regardless of their native "skills"
    support, which makes the with/without comparison apples-to-apples."""
    if skill_path:
        return (
            f"You have access to a skill at this path: {skill_path}\n\n"
            "Read the skill's SKILL.md file (and any reference/example files it "
            "points you to, as needed) and follow its instructions to answer this "
            "task. Do not perform any real network calls, downloads, or start any "
            "real services — just produce the guidance, commands, and request "
            "payloads a user would need.\n\n"
            f"TASK: {eval_prompt}"
        )
    return (
        "Answer this task directly using your own general knowledge. Do not "
        "perform any real network calls, downloads, or start any real services "
        "— just produce the guidance, commands, and request payloads a user "
        f"would need.\n\nTASK: {eval_prompt}"
    )


# --------------------------------------------------------------------------
# CLI adapters
# --------------------------------------------------------------------------

def find_binary(name: str, override: str | None) -> str | None:
    if override:
        return override if shutil.which(override) or Path(override).exists() else None
    found = shutil.which(name)
    if found:
        return found
    # Fall back to nvm-managed installs (codex is commonly installed this way
    # because it requires a newer Node than the system default).
    for candidate in sorted(glob.glob(str(Path.home() / ".nvm/versions/node/*/bin" / name))):
        if Path(candidate).exists():
            return candidate
    return None


def _sum_copilot_otel_tokens(otel_path: Path) -> int | None:
    """Sum gen_ai.usage.{input,output}_tokens across all 'chat <model>' spans
    in a Copilot CLI OTel file-exporter JSONL dump.

    Copilot's --output-format json event stream doesn't expose token usage
    (the `result` event's `usage` object only has premium-request/duration
    fields). Setting COPILOT_OTEL_FILE_EXPORTER_PATH makes the CLI also emit
    OTel spans/metrics as JSON lines; each LLM call produces a "chat <model>"
    span with accurate gen_ai.usage.* attributes (per the OTel GenAI semantic
    conventions). Summing across all chat spans covers multi-turn/tool-calling
    runs where more than one LLM call happens.
    """
    if not otel_path.exists():
        return None
    total = 0
    found = False
    for line in otel_path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("type") != "span" or not evt.get("name", "").startswith("chat "):
            continue
        attrs = evt.get("attributes", {})
        in_tok = attrs.get("gen_ai.usage.input_tokens")
        out_tok = attrs.get("gen_ai.usage.output_tokens")
        if in_tok is None and out_tok is None:
            continue
        total += (in_tok or 0) + (out_tok or 0)
        found = True
    return total if found else None


def run_copilot(binary: str, prompt: str, cwd: Path, timeout: int, model: str | None = None) -> RunResult:
    cmd = [
        binary, "-p", prompt,
        "--allow-all-tools", "--allow-all-paths",
        "--no-color", "--output-format", "json",
        "-C", str(cwd),
    ]
    if model:
        cmd += ["--model", model]
    result = RunResult()
    start = time.monotonic()
    otel_fd, otel_path_str = tempfile.mkstemp(prefix="copilot-otel-", suffix=".jsonl")
    os.close(otel_fd)
    otel_path = Path(otel_path_str)
    env = os.environ.copy()
    env["COPILOT_OTEL_FILE_EXPORTER_PATH"] = otel_path_str
    try:
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env,
            )
        except subprocess.TimeoutExpired as e:
            result.error = f"Timed out after {timeout}s"
            result.raw_stdout = (e.stdout or "")
            result.duration_seconds = time.monotonic() - start
            return result
        result.duration_seconds = time.monotonic() - start
        result.raw_stdout = proc.stdout
        result.raw_stderr = proc.stderr
        result.total_tokens = _sum_copilot_otel_tokens(otel_path)
    finally:
        otel_path.unlink(missing_ok=True)

    last_message = ""
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = evt.get("type", "")
        if etype == "assistant.message":
            content = evt.get("data", {}).get("content", "")
            if content:
                last_message = content
                result.transcript_lines.append(f"**Assistant:** {content}")
            evt_model = evt.get("data", {}).get("model")
            if evt_model:
                result.model = evt_model
        elif etype == "tool.execution_start":
            tool_name = evt.get("data", {}).get("name") or evt.get("data", {}).get("toolName") or "unknown_tool"
            result.tool_calls[tool_name] = result.tool_calls.get(tool_name, 0) + 1
            result.total_steps += 1
            result.transcript_lines.append(f"**Tool call:** {tool_name}")
        elif etype in ("error", "session.error"):
            result.errors_encountered += 1

    if not last_message and proc.returncode != 0:
        result.error = f"copilot exited with code {proc.returncode}: {proc.stderr[:500]}"
    result.response_text = last_message
    if not result.model:
        result.model = model  # fall back to what we requested, if anything
    return result


def run_claude(binary: str, prompt: str, cwd: Path, timeout: int, model: str | None = None) -> RunResult:
    cmd = [
        binary, "-p", prompt,
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]
    if model:
        cmd += ["--model", model]
    result = RunResult()
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired as e:
        result.error = f"Timed out after {timeout}s"
        result.raw_stdout = (e.stdout or "")
        result.duration_seconds = time.monotonic() - start
        return result
    result.duration_seconds = time.monotonic() - start
    result.raw_stdout = proc.stdout
    result.raw_stderr = proc.stderr

    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (json.JSONDecodeError, IndexError):
        data = {}

    result.response_text = data.get("result", "") or ""
    result.total_steps = data.get("num_turns", 0) or 0
    usage = data.get("usage", {}) or {}
    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    cache_creation = usage.get("cache_creation_input_tokens", 0) or 0
    result.total_tokens = input_tokens + output_tokens + cache_read + cache_creation
    if data.get("is_error"):
        result.errors_encountered += 1
        result.error = data.get("result") or "claude reported is_error=true"
    result.transcript_lines.append(f"**Assistant:** {result.response_text}")
    result.transcript_lines.append(f"_num_turns={result.total_steps}, usage={usage}_")

    # modelUsage breaks tokens down per model actually invoked (Claude Code may
    # route some subagent/title-generation calls to a cheaper model, e.g.
    # haiku, alongside the main response model). Pick whichever model has the
    # most output tokens as "the" model, since that's the one that produced
    # the actual answer being graded.
    model_usage = data.get("modelUsage", {}) or {}
    if model_usage:
        result.model = max(model_usage, key=lambda m: model_usage[m].get("outputTokens", 0))
    if not result.model:
        result.model = model

    if not result.response_text and proc.returncode != 0:
        result.error = f"claude exited with code {proc.returncode}: {proc.stderr[:500]}"
    return result


def run_codex(binary: str, prompt: str, cwd: Path, timeout: int, model: str | None = None) -> RunResult:
    cmd = [
        binary, "exec", prompt,
        "--json",
        "--sandbox", "workspace-write",
        "--skip-git-repo-check",
        "-C", str(cwd),
    ]
    if model:
        cmd += ["-m", model]
    result = RunResult()
    start = time.monotonic()
    try:
        # Codex reads stdin for extra instructions if present; feed it /dev/null
        # equivalent (empty string) so it never blocks waiting on a pipe.
        proc = subprocess.run(
            cmd, input="", capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
    except subprocess.TimeoutExpired as e:
        result.error = f"Timed out after {timeout}s"
        result.raw_stdout = (e.stdout or "")
        result.duration_seconds = time.monotonic() - start
        return result
    result.duration_seconds = time.monotonic() - start
    result.raw_stdout = proc.stdout
    result.raw_stderr = proc.stderr

    last_message = ""
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("Reading additional input"):
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = evt.get("type", "")
        if etype == "item.completed":
            item = evt.get("item", {})
            itype = item.get("type", "")
            if itype == "agent_message":
                last_message = item.get("text", "") or last_message
                result.transcript_lines.append(f"**Assistant:** {item.get('text', '')}")
            elif itype == "command_execution":
                cmd_str = item.get("command") or "command"
                result.tool_calls["command_execution"] = result.tool_calls.get("command_execution", 0) + 1
                result.total_steps += 1
                result.transcript_lines.append(f"**Tool call (command_execution):** {cmd_str}")
            elif itype in ("mcp_tool_call", "file_change", "web_search"):
                result.tool_calls[itype] = result.tool_calls.get(itype, 0) + 1
                result.total_steps += 1
        elif etype == "turn.completed":
            usage = evt.get("usage", {})
            result.total_tokens = (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)
        elif etype in ("error", "turn.failed"):
            result.errors_encountered += 1

    if not last_message and proc.returncode != 0:
        result.error = f"codex exited with code {proc.returncode}: {proc.stderr[:500]}"
    result.response_text = last_message
    # Codex's JSON stream doesn't expose which model actually served the
    # request, so the best we can record is what was explicitly requested (or
    # "unspecified" — meaning whatever ~/.codex/config.toml / the CLI's own
    # built-in default resolves to, which is opaque to us).
    result.model = model or "unspecified (codex CLI default)"
    return result


CLI_RUNNERS = {
    "copilot": run_copilot,
    "claude": run_claude,
    "codex": run_codex,
}


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def load_evals(evals_json_path: Path) -> list[dict]:
    data = json.loads(evals_json_path.read_text())
    return data["evals"]


def slugify(text: str, max_len: int = 40) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:max_len]


def eval_dir_name(ev: dict) -> str:
    # Prefer an explicit eval_name if the evals.json provides one; otherwise
    # fall back to a short slug of the prompt itself (not expected_output,
    # which tends to produce long, awkward directory names).
    name = ev.get("eval_name") or slugify(ev["prompt"], max_len=30)
    return f"eval-{ev['id']}-{name}"


def run_one(cli: str, binary: str, ev: dict, config: str, skill_path: str, timeout: int,
            model: str | None = None) -> tuple[str, dict, RunResult]:
    prompt = build_prompt(ev["prompt"], skill_path if config == "with_skill" else None)
    scratch = Path(tempfile.mkdtemp(prefix=f"skilleval-{cli}-{ev['id']}-{config}-"))
    runner = CLI_RUNNERS[cli]
    result = runner(binary, prompt, scratch, timeout, model)
    return cli, ev, config, result


def save_run(workspace: Path, cli: str, ev: dict, config: str, result: RunResult) -> Path:
    run_dir = workspace / cli / eval_dir_name(ev) / config / "run-1"
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # eval_metadata.json (placed inside the config dir so eval-viewer's
    # generate_review.py finds it — it looks in the run dir and its immediate
    # parent, not two levels up).
    metadata = {
        "eval_id": ev["id"],
        "eval_name": ev.get("eval_name", eval_dir_name(ev)),
        "prompt": ev["prompt"],
        "assertions": ev.get("expectations", ev.get("assertions", [])),
    }
    (run_dir.parent / "eval_metadata.json").write_text(json.dumps(metadata, indent=2))

    # outputs/response.md
    (outputs_dir / "response.md").write_text(
        result.response_text or "(no response captured)"
    )

    # outputs/metrics.json
    metrics = {
        "tool_calls": result.tool_calls,
        "total_tool_calls": sum(result.tool_calls.values()),
        "total_steps": result.total_steps,
        "files_created": 0,
        "errors_encountered": result.errors_encountered + (1 if result.error else 0),
        "output_chars": len(result.response_text or ""),
        "transcript_chars": sum(len(line) for line in result.transcript_lines),
    }
    (outputs_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # transcript.md
    transcript_lines = [
        f"## Eval Prompt\n\n{ev['prompt']}\n",
        f"## Configuration\n\n{config} (CLI: {cli})\n",
        "## Transcript\n",
    ] + (result.transcript_lines or ["(no transcript events captured)"])
    if result.error:
        transcript_lines.append(f"\n## Error\n\n{result.error}")
    (run_dir / "transcript.md").write_text("\n\n".join(transcript_lines))

    # timing.json
    timing = {
        "total_tokens": result.total_tokens,
        "duration_ms": int(result.duration_seconds * 1000),
        "total_duration_seconds": round(result.duration_seconds, 1),
        "model": result.model,
    }
    (run_dir / "timing.json").write_text(json.dumps(timing, indent=2))

    return run_dir


# --------------------------------------------------------------------------
# Grading (LLM-as-judge, following skill-creator's agents/grader.md)
# --------------------------------------------------------------------------

def build_grader_prompt(eval_meta: dict, transcript_path: Path, outputs_dir: Path) -> str:
    """Build the grading instructions, following agents/grader.md's process
    but condensed for CLI invocation: read transcript+outputs, judge each
    expectation, emit JSON matching the schema the viewer/aggregator expect."""
    assertions = eval_meta.get("assertions", [])
    assertions_block = "\n".join(f"- {a}" for a in assertions) or "(no assertions provided)"

    return f"""You are grading an AI assistant's response to a task, evaluating whether \
it satisfies a list of expectations. Follow this process:

1. Read the transcript file at: {transcript_path}
2. Read all files in the outputs directory: {outputs_dir}
3. For each expectation below, decide PASS or FAIL based on clear evidence in the \
transcript/outputs. Burden of proof is on the expectation — if you can't find clear \
evidence, it fails. A technically-satisfied assertion whose underlying task outcome is \
wrong or incomplete should also fail.

Expectations to evaluate:
{assertions_block}

Write your grading result as a SINGLE JSON object (and nothing else — no markdown \
fences, no commentary before or after) to this exact path: {outputs_dir.parent / 'grading.json'}

The JSON must have this exact structure:
{{
  "expectations": [
    {{"text": "<expectation text>", "passed": true/false, "evidence": "<specific quote or description>"}}
  ],
  "summary": {{"passed": <int>, "failed": <int>, "total": <int>, "pass_rate": <float 0-1>}}
}}

Use the file-write tools available to you to actually create this file — do not just \
print the JSON in your final response."""


def run_grader(grader_cli: str, grader_binary: str, run_dir: Path, eval_meta: dict, timeout: int) -> bool:
    """Invoke the grader CLI to write grading.json into run_dir. Returns True on success."""
    transcript_path = run_dir / "transcript.md"
    outputs_dir = run_dir / "outputs"
    prompt = build_grader_prompt(eval_meta, transcript_path, outputs_dir)
    runner = CLI_RUNNERS[grader_cli]
    # Grader needs read access to the actual run_dir (not a scratch dir) so it can
    # read the transcript/outputs and write grading.json alongside them.
    result = runner(grader_binary, prompt, run_dir, timeout)

    grading_path = run_dir / "grading.json"
    if grading_path.exists():
        try:
            json.loads(grading_path.read_text())
            return True
        except json.JSONDecodeError:
            pass

    # Fall back: the grader CLI sometimes prints the JSON instead of writing the
    # file (especially CLIs run in restrictive sandboxes). Try to extract a JSON
    # object from its response text and write it ourselves.
    match = re.search(r"\{.*\}", result.response_text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            grading_path.write_text(json.dumps(parsed, indent=2))
            return True
        except json.JSONDecodeError:
            pass

    print(f"WARNING: grader did not produce valid grading.json for {run_dir}", file=sys.stderr)
    return False


def grade_all_runs(workspace: Path, cli: str, grader_cli: str, grader_binary: str,
                    workers: int, timeout: int) -> None:
    """Find every with_skill/without_skill run-*/ dir under workspace/<cli> that
    has a transcript but no grading.json yet, and grade it."""
    cli_dir = workspace / cli
    run_dirs = []
    for meta_path in cli_dir.glob("eval-*/*/eval_metadata.json"):
        config_dir = meta_path.parent
        eval_meta = json.loads(meta_path.read_text())
        for run_dir in sorted(config_dir.glob("run-*")):
            if (run_dir / "transcript.md").exists() and not (run_dir / "grading.json").exists():
                run_dirs.append((run_dir, eval_meta))

    if not run_dirs:
        print(f"  [{cli}] nothing to grade (all runs already graded or no transcripts found)")
        return

    print(f"  [{cli}] grading {len(run_dirs)} runs using '{grader_cli}' as judge...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_grader, grader_cli, grader_binary, run_dir, eval_meta, timeout): run_dir
            for run_dir, eval_meta in run_dirs
        }
        for future in as_completed(futures):
            run_dir = futures[future]
            try:
                ok = future.result()
            except Exception as e:  # noqa: BLE001
                print(f"    GRADE FAILED {run_dir}: {e}", file=sys.stderr)
                continue
            print(f"    graded {run_dir} [{'OK' if ok else 'FALLBACK-FAILED'}]")


# --------------------------------------------------------------------------
# Markdown helpers shared by per-CLI and cross-CLI reports
# --------------------------------------------------------------------------

def _consistency_label(mean: float, stddev: float) -> str:
    """Classify spread as consistent/variable/unreliable using the coefficient
    of variation (stddev / mean). Returned as a parenthetical hint so readers
    understand at a glance whether the average is trustworthy."""
    if mean == 0:
        return "unreliable" if stddev > 0 else "n/a"
    cv = stddev / mean
    if cv < 0.15:
        return "consistent"
    if cv <= 0.50:
        return "variable"
    return "unreliable"


def _fmt_tokens(value: float) -> str:
    """Abbreviate large token counts to k-notation for readability."""
    if abs(value) >= 1000:
        return f"{value/1000:.0f}k"
    return f"{value:.0f}"


_HOW_TO_READ = (
    "> **How to read this table** \u2014 "
    "**Avg** is the mean score across all evals; "
    "**Std Dev** (the \u00b1 spread) measures how much individual evals varied around that average "
    "\u2014 small spread means the agent behaved consistently, large spread means results were erratic; "
    "**Skill Lift** is the gain from loading the skill (with\u2009\u2212\u2009without)."
)


def generate_per_cli_markdown(benchmark: dict) -> str:
    """Human-readable benchmark.md for a single CLI, replacing skill-creator's
    generate_markdown(). Reads run_summary[\"with_skill\"], [\"without_skill\"],
    and [\"delta\"] from the benchmark produced by generate_benchmark()."""
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]
    ws = run_summary.get("with_skill", {})
    wos = run_summary.get("without_skill", {})
    delta = run_summary.get("delta", {})

    def _cell(stats: dict, key: str, fmt_fn) -> str:
        m = stats.get(key, {}).get("mean", 0)
        s = stats.get(key, {}).get("stddev", 0)
        label = _consistency_label(m, s)
        return f"{fmt_fn(m)} avg, \u00b1{fmt_fn(s)} spread ({label})"

    def _delta_cell(raw, key: str) -> str:
        """Re-format delta values from skill-creator's string representation.
        Pass rate delta is converted from decimal (+0.78) to percentage points (+78pp)."""
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return str(raw)
        if key == "pass_rate":
            return f"{val*100:+.0f}pp"
        if key == "tokens":
            sign = "+" if val >= 0 else ""
            return f"{sign}{_fmt_tokens(val)}"
        if key == "time_seconds":
            return f"{val:+.1f}s"
        return f"{val:+g}"

    lines = [
        f"# Skill Benchmark: {metadata['skill_name']}",
        "",
        f"**Model**: {metadata.get('executor_model', 'n/a')}",
        f"**Date**: {metadata.get('timestamp', 'n/a')}",
        f"**Evals**: {', '.join(map(str, metadata.get('evals_run', [])))} "
        f"({metadata.get('runs_per_configuration', 1)} run(s) each per configuration)",
        "",
        "## Summary",
        "",
        _HOW_TO_READ,
        "",
        "| Metric | Avg \u00b1 Std Dev (With Skill) | Avg \u00b1 Std Dev (Without Skill) | Skill Lift (\u0394) |",
        "|--------|---------------------------|-------------------------------|----------------|",
        f"| Pass Rate (% correct) "
        f"| {_cell(ws, 'pass_rate', lambda v: f'{v*100:.0f}%')} "
        f"| {_cell(wos, 'pass_rate', lambda v: f'{v*100:.0f}%')} "
        f"| {_delta_cell(delta.get('pass_rate', '0'), 'pass_rate')} |",
        f"| Time (s / question) "
        f"| {_cell(ws, 'time_seconds', lambda v: f'{v:.1f}s')} "
        f"| {_cell(wos, 'time_seconds', lambda v: f'{v:.1f}s')} "
        f"| {_delta_cell(delta.get('time_seconds', '0'), 'time_seconds')} |",
        f"| Tokens (context cost) "
        f"| {_cell(ws, 'tokens', _fmt_tokens)} "
        f"| {_cell(wos, 'tokens', _fmt_tokens)} "
        f"| {_delta_cell(delta.get('tokens', '0'), 'tokens')} |",
    ]

    if benchmark.get("notes"):
        lines.extend(["", "## Notes", ""])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# Cross-CLI aggregation
# --------------------------------------------------------------------------

def generate_cross_cli_markdown(benchmark: dict) -> str:
    """Cross-CLI markdown table showing all configs (with_skill / without_skill)
    and all CLIs side-by-side. run_summary is expected in the nested format
    run_summary[config][cli] produced by build_cross_cli_benchmark; the old flat
    format run_summary[cli] is also accepted for backward compatibility."""
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]

    # Detect nested (new) vs flat (old) format.
    first_val = next(iter(run_summary.values()), {})
    nested = isinstance(first_val, dict) and not any(k in first_val for k in ("mean", "stddev"))

    if nested:
        configs = list(run_summary.keys())
        clis = list(next(iter(run_summary.values()), {}).keys())
    else:
        configs = ["with_skill"]
        clis = [k for k in run_summary if k != "delta"]

    def get_stats(config: str, cli: str, key: str) -> dict:
        if nested:
            return run_summary.get(config, {}).get(cli, {}).get(key, {})
        return run_summary.get(cli, {}).get(key, {})

    def _cell_cross(config: str, cli: str, key: str, fmt_fn) -> str:
        stats = get_stats(config, cli, key)
        m = stats.get("mean", 0)
        s = stats.get("stddev", 0)
        label = _consistency_label(m, s)
        return f"{fmt_fn(m)} avg, \u00b1{fmt_fn(s)} spread ({label})"

    col_headers = " | ".join(f"{c.title()} (Avg \u00b1 Std Dev)" for c in clis)
    sep = "|".join(["---"] * len(clis))

    lines = [
        f"# Skill Benchmark: {metadata['skill_name']}",
        "",
        f"**Model**: {metadata['executor_model']}",
        f"**Date**: {metadata['timestamp']}",
        f"**Evals**: {', '.join(map(str, metadata['evals_run']))} "
        f"({metadata['runs_per_configuration']} run(s) each per configuration)",
        "",
        "## Summary",
        "",
        _HOW_TO_READ,
        "",
        f"| Metric | Config | {col_headers} |",
        f"|--------|--------|{sep}|",
    ]

    metrics = [
        ("Pass Rate (% correct)", "pass_rate", lambda v: f"{v*100:.0f}%"),
        ("Time (s / question)",   "time_seconds", lambda v: f"{v:.1f}s"),
        ("Tokens (context cost)", "tokens", _fmt_tokens),
    ]
    for metric_label, key, fmt_fn in metrics:
        for i, config in enumerate(configs):
            row_label = metric_label if i == 0 else ""
            cells = [_cell_cross(config, cli, key, fmt_fn) for cli in clis]
            lines.append(f"| {row_label} | {config} | {' | '.join(cells)} |")

    if benchmark.get("notes"):
        lines.extend(["", "## Notes", ""])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


def detect_cli_model(workspace: Path, cli: str) -> str:
    """Best-effort determination of which model a CLI actually used, based on
    the `model` field each run's timing.json records (see run_copilot /
    run_claude / run_codex). Returns the most common non-empty value across
    all of that CLI's runs, or a fallback label if nothing was recorded
    (e.g. an older run predating this field)."""
    from collections import Counter
    counts: Counter[str] = Counter()
    for timing_path in (workspace / cli).glob("eval-*/*/run-*/timing.json"):
        try:
            data = json.loads(timing_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        model = data.get("model")
        if model:
            counts[model] += 1
    if not counts:
        return "unknown (recorded before model tracking was added — re-run to capture it)"
    return counts.most_common(1)[0][0]


def build_cross_cli_benchmark(workspace: Path, clis: list[str], skill_name: str,
                               configs: list[str] | None = None) -> dict:
    """Build a benchmark.json comparing every config across every CLI that was run.
    run_summary is nested as run_summary[config][cli] so the markdown table can
    show with_skill vs without_skill lift for each CLI side-by-side."""
    if configs is None:
        configs = ["with_skill"]
    if calculate_stats is None:
        raise RuntimeError("Could not import scripts.aggregate_benchmark from skill-creator; "
                            f"expected it at {SKILL_CREATOR_DIR}")

    # run_summary[config][cli] = {pass_rate, time_seconds, tokens}
    run_summary: dict[str, Any] = {}
    runs: list[dict] = []

    for config in configs:
        run_summary[config] = {}
        for cli in clis:
            cli_dir = workspace / cli
            pass_rates, times, tokens = [], [], []
            for meta_path in sorted(cli_dir.glob(f"eval-*/{config}/eval_metadata.json")):
                eval_meta = json.loads(meta_path.read_text())
                config_dir = meta_path.parent
                for run_dir in sorted(config_dir.glob("run-*")):
                    grading_path = run_dir / "grading.json"
                    timing_path = run_dir / "timing.json"
                    if not grading_path.exists():
                        continue
                    grading = json.loads(grading_path.read_text())
                    timing = json.loads(timing_path.read_text()) if timing_path.exists() else {}
                    pr = grading.get("summary", {}).get("pass_rate", 0.0)
                    t = timing.get("total_duration_seconds", 0.0)
                    tok = timing.get("total_tokens") or 0
                    pass_rates.append(pr)
                    times.append(t)
                    tokens.append(tok)
                    runs.append({
                        "eval_id": eval_meta.get("eval_id"),
                        "configuration": f"{config}/{cli}",
                        "run_number": int(run_dir.name.split("-")[1]),
                        "result": {
                            "pass_rate": pr,
                            "passed": grading.get("summary", {}).get("passed", 0),
                            "failed": grading.get("summary", {}).get("failed", 0),
                            "total": grading.get("summary", {}).get("total", 0),
                            "time_seconds": t,
                            "tokens": tok,
                        },
                        "expectations": grading.get("expectations", []),
                    })
            run_summary[config][cli] = {
                "pass_rate": calculate_stats(pass_rates),
                "time_seconds": calculate_stats(times),
                "tokens": calculate_stats(tokens),
            }

    cli_models = {cli: detect_cli_model(workspace, cli) for cli in clis}

    benchmark = {
        "metadata": {
            "skill_name": skill_name,
            "skill_path": "<see per-cli benchmark.json for skill_path>",
            "executor_model": ", ".join(f"{cli}={cli_models[cli]}" for cli in clis),
            "analyzer_model": "run_multi_cli_eval.py (cross-CLI aggregation)",
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": sorted({r["eval_id"] for r in runs}),
            "runs_per_configuration": 1,
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": [
            f"Cross-CLI comparison of {configs} across: {', '.join(clis)}.",
            "Each CLI ran the identical eval prompts against the identical skill, using each "
            "CLI's own non-interactive/headless mode. run_summary is keyed "
            "run_summary[config][cli] — each config (with_skill/without_skill) shows the "
            "stats for that CLI under that configuration.",
            "Model per CLI: " + ", ".join(f"{cli}={cli_models[cli]}" for cli in clis) + ". "
            "Copilot and Claude report the actual model used per-run (see each run's "
            "timing.json); Codex's non-interactive JSON output does not expose which model "
            "served the request, so its value reflects what was explicitly requested via "
            "--codex-model, or 'unspecified' if the CLI's own built-in default was used.",
        ],
    }
    return benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evals-json", required=True, help="Path to the skill's evals/evals.json")
    parser.add_argument("--skill-path", required=True, help="Path to the skill directory (contains SKILL.md)")
    parser.add_argument("--workspace", required=True, help="Output workspace directory")
    parser.add_argument("--clis", default="copilot,claude,codex", help="Comma-separated list of CLIs to run")
    parser.add_argument("--configs", default="with_skill,without_skill", help="Comma-separated configs to run")
    parser.add_argument("--workers", type=int, default=4, help="Max concurrent subprocess runs")
    parser.add_argument("--timeout", type=int, default=300, help="Per-run timeout in seconds")
    parser.add_argument("--eval-ids", default="", help="Comma-separated eval IDs to restrict to (default: all)")
    parser.add_argument("--copilot-bin", default=None)
    parser.add_argument("--claude-bin", default=None)
    parser.add_argument("--codex-bin", default=None)
    parser.add_argument("--copilot-model", default=None,
                         help="Model to pass to copilot via --model (default: let Copilot CLI choose its own default)")
    parser.add_argument("--claude-model", default=None,
                         help="Model to pass to claude via --model (default: let Claude Code CLI choose its own default)")
    parser.add_argument("--codex-model", default=None,
                         help="Model to pass to codex via -m/--model (default: let Codex CLI choose its own default)")
    parser.add_argument("--skill-name", default=None, help="Skill name for benchmark metadata (default: skill dir name)")
    parser.add_argument("--grader-cli", default=None,
                         help="CLI to use as the LLM grading judge (default: first of claude/copilot/codex found)")
    parser.add_argument("--grader-workers", type=int, default=4, help="Max concurrent grading calls")
    parser.add_argument("--grader-timeout", type=int, default=180, help="Per-grading-call timeout in seconds")
    parser.add_argument("--skip-grading", action="store_true", help="Only run evals, skip LLM grading")
    parser.add_argument("--skip-aggregate", action="store_true", help="Skip benchmark.json/.md generation")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without running anything")
    args = parser.parse_args()

    evals_json_path = Path(args.evals_json).resolve()
    skill_path = str(Path(args.skill_path).resolve())
    skill_name = args.skill_name or Path(args.skill_path).resolve().name
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    clis = [c.strip() for c in args.clis.split(",") if c.strip()]
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    evals = load_evals(evals_json_path)
    if args.eval_ids:
        wanted = {int(x) for x in args.eval_ids.split(",")}
        evals = [e for e in evals if e["id"] in wanted]

    binaries: dict[str, str] = {}
    overrides = {"copilot": args.copilot_bin, "claude": args.claude_bin, "codex": args.codex_bin}
    for cli in clis:
        if cli not in CLI_RUNNERS:
            print(f"WARNING: unknown CLI '{cli}', skipping", file=sys.stderr)
            continue
        binary = find_binary(cli, overrides[cli])
        if not binary:
            print(f"WARNING: could not find '{cli}' binary on PATH, skipping this CLI", file=sys.stderr)
            continue
        binaries[cli] = binary

    if not binaries:
        print("ERROR: no usable CLIs found. Install/authenticate at least one of copilot/claude/codex.", file=sys.stderr)
        return 1

    jobs = [
        (cli, ev, config)
        for cli in binaries
        for ev in evals
        for config in configs
    ]

    models = {"copilot": args.copilot_model, "claude": args.claude_model, "codex": args.codex_model}
    model_summary = ", ".join(f"{c}: {models[c] or '(CLI default)'}" for c in binaries)

    print(f"Skill:      {skill_path}")
    print(f"Evals:      {[e['id'] for e in evals]}")
    print(f"CLIs:       {list(binaries.keys())}")
    print(f"Models:     {{{model_summary}}}")
    print(f"Configs:    {configs}")
    print(f"Workspace:  {workspace}")
    print(f"Total jobs: {len(jobs)}")

    if args.dry_run:
        for cli, ev, config in jobs:
            print(f"  [DRY RUN] {cli} / eval {ev['id']} ({ev.get('eval_name')}) / {config} / model={models[cli] or '(CLI default)'}")
        return 0

    results_summary = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(run_one, cli, binaries[cli], ev, config, skill_path, args.timeout, models[cli]): (cli, ev, config)
            for cli, ev, config in jobs
        }
        for future in as_completed(futures):
            cli, ev, config = futures[future]
            try:
                _, ev, config, result = future.result()
            except Exception as e:  # noqa: BLE001 - surface any adapter bug per-job, don't kill the batch
                print(f"FAILED  {cli} / eval {ev['id']} / {config}: {e}", file=sys.stderr)
                continue
            run_dir = save_run(workspace, cli, ev, config, result)
            status = "OK" if not result.error else f"ERROR: {result.error[:80]}"
            print(f"{'DONE':6} {cli:8} eval-{ev['id']:<2} {config:14} {result.duration_seconds:6.1f}s  -> {run_dir}  [{status}]")
            results_summary.append({
                "cli": cli, "eval_id": ev["id"], "config": config,
                "duration_seconds": result.duration_seconds,
                "tokens": result.total_tokens, "error": result.error,
                "model": result.model,
            })

    summary_path = workspace / "run_summary.json"
    summary_path.write_text(json.dumps(results_summary, indent=2))
    print(f"\nWrote run summary: {summary_path}")

    # ----------------------------------------------------------------------
    # Grading
    # ----------------------------------------------------------------------
    if not args.skip_grading:
        grader_cli = args.grader_cli
        grader_binary = None
        if grader_cli:
            grader_binary = binaries.get(grader_cli) or find_binary(
                grader_cli, {"copilot": args.copilot_bin, "claude": args.claude_bin, "codex": args.codex_bin}.get(grader_cli)
            )
        else:
            # Default preference order: claude, copilot, codex — Claude and
            # Copilot both have strong instruction-following for structured
            # JSON output; either works well as judge.
            for candidate in ("claude", "copilot", "codex"):
                if candidate in binaries:
                    grader_cli, grader_binary = candidate, binaries[candidate]
                    break
        if not grader_binary:
            print("WARNING: no grader CLI available/found — skipping grading.", file=sys.stderr)
        else:
            print(f"\n=== Grading (judge: {grader_cli}) ===")
            for cli in binaries:
                grade_all_runs(workspace, cli, grader_cli, grader_binary, args.grader_workers, args.grader_timeout)

    # ----------------------------------------------------------------------
    # Aggregation
    # ----------------------------------------------------------------------
    if not args.skip_aggregate:
        if generate_benchmark is None:
            print(f"WARNING: could not import scripts.aggregate_benchmark from {SKILL_CREATOR_DIR} — "
                  "skipping aggregation. Run it manually per-CLI instead.", file=sys.stderr)
        else:
            print("\n=== Per-CLI benchmarks (with_skill vs without_skill) ===")
            for cli in binaries:
                cli_dir = workspace / cli
                benchmark = generate_benchmark(cli_dir, skill_name=skill_name, skill_path=skill_path)
                # generate_benchmark() hard-codes runs_per_configuration=3 (its
                # original use case); fix it up to reflect what we actually ran.
                run_counts = {r["configuration"] for r in benchmark["runs"]}
                counts_per_config = [
                    sum(1 for r in benchmark["runs"] if r["configuration"] == c) for c in run_counts
                ]
                if counts_per_config:
                    per_eval = len({r["eval_id"] for r in benchmark["runs"]}) or 1
                    benchmark["metadata"]["runs_per_configuration"] = max(1, counts_per_config[0] // per_eval)
                benchmark["metadata"]["executor_model"] = detect_cli_model(workspace, cli)
                (cli_dir / "benchmark.json").write_text(json.dumps(benchmark, indent=2))
                (cli_dir / "benchmark.md").write_text(generate_per_cli_markdown(benchmark))
                summary = benchmark["run_summary"]
                configs_seen = [k for k in summary if k != "delta"]
                parts = [f"{c}={summary[c]['pass_rate']['mean']*100:.0f}%" for c in configs_seen]
                print(f"  [{cli}] {cli_dir / 'benchmark.json'}  ({', '.join(parts)})")

            if len(binaries) >= 2:
                print("\n=== Cross-CLI benchmark (all configs, compared across coding agents) ===")
                cross = build_cross_cli_benchmark(workspace, list(binaries.keys()), skill_name, configs=configs)
                (workspace / "benchmark.json").write_text(json.dumps(cross, indent=2))
                (workspace / "benchmark.md").write_text(generate_cross_cli_markdown(cross))
                for config in configs:
                    for cli in binaries:
                        pr = cross["run_summary"].get(config, {}).get(cli, {}).get("pass_rate", {}).get("mean", 0.0)
                        print(f"  {cli} ({config}): {pr*100:.1f}% pass rate")
                print(f"  Written to: {workspace / 'benchmark.json'} / {workspace / 'benchmark.md'}")

    print("\nOptional next step — open a review in your browser:")
    for cli in binaries:
        print(f"  python3 {SKILL_CREATOR_DIR}/eval-viewer/generate_review.py {workspace / cli} "
              f"--skill-name {skill_name} --benchmark {workspace / cli / 'benchmark.json'} "
              f"--static {workspace / cli / 'review.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
