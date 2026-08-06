#!/usr/bin/env python3
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
import collections
import datetime
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
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_seconds: float = 0.0
    error: str | None = None
    raw_stdout: str = ""
    raw_stderr: str = ""
    model: str | None = None
    exit_code: int | None = None


_AUTH_PATTERNS = re.compile(
    r"not logged in|not authenticated|unauthenticated|authentication required|"
    r"please log in|login required|invalid api key|missing api key|unauthorized|"
    r"no credentials|credential.*(?:missing|not found|expired)",
    re.IGNORECASE,
)
_RATE_LIMIT_PATTERNS = re.compile(
    r"rate.?limit|too many requests|quota|usage limit|credit balance",
    re.IGNORECASE,
)
_MODEL_PATTERNS = re.compile(
    r"model.*(?:not found|invalid|unavailable|unsupported|access)|"
    r"(?:not found|invalid|unavailable|unsupported).*model",
    re.IGNORECASE,
)
# Codex's default `workspace-write` sandbox shells out through bubblewrap,
# which creates an isolated network namespace even though network access is
# already denied by policy. When run.py's own process is itself inside a
# nested/rootless container (as it is here), that namespace/interface setup
# can fail outright — codex then can't run *any* shell command (including a
# plain file read of SKILL.md), but still exits 0 and produces a fluent
# "I couldn't read the file" assistant message. That message is non-empty and
# exit_code is 0, so it sails past the existing error checks and gets graded
# as a normal (very low) pass rate instead of being flagged as an infra
# failure — which is exactly what happened to every codex with_skill run in
# /tmp/model-download-user-eval-run.
_CODEX_SANDBOX_INIT_PATTERNS = re.compile(
    r"bwrap:|RTM_NEWADDR|sandbox initialization error|"
    r"failed to (?:create|set up) (?:the )?(?:network )?namespace|"
    r"clone\(CLONE_NEWNET",
    re.IGNORECASE,
)
_LOGIN_GUIDANCE = {
    "copilot": "Run `copilot` interactively and complete GitHub authentication, then retry.",
    "claude": "Run `claude` interactively and complete authentication (or run `/login`), then retry.",
    "codex": "Run `codex login`, verify the login succeeds, then retry.",
}


def _text(value: str | bytes | None) -> str:
    """Normalize subprocess output, including TimeoutExpired byte strings."""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def _diagnostic_excerpt(text: str, limit: int = 1200) -> str:
    """Collapse process output into a bounded, readable console diagnostic."""
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[:limit] + "..."


def finalize_process_result(cli: str, result: RunResult, returncode: int) -> None:
    """Turn process status/output into a useful, actionable error message."""
    result.exit_code = returncode
    combined = "\n".join(part for part in (result.raw_stderr, result.raw_stdout) if part)
    excerpt = _diagnostic_excerpt(combined)

    reasons: list[str] = []
    if returncode != 0:
        reasons.append(f"{cli} exited with code {returncode}")
    if not result.response_text.strip():
        reasons.append("no assistant response was captured")
    # Codex can exit 0 with a non-empty, fluent-sounding response that is
    # actually just it explaining that its sandbox failed to initialize
    # before it could run any tool (see _CODEX_SANDBOX_INIT_PATTERNS above).
    # That's not a real answer to the eval — flag it even though the other
    # two checks above would otherwise consider this run "successful".
    sandbox_init_failed = cli == "codex" and bool(_CODEX_SANDBOX_INIT_PATTERNS.search(combined))
    if sandbox_init_failed and not reasons:
        reasons.append("codex's sandbox failed to initialize before it could execute any tool")
    if not reasons:
        return

    if sandbox_init_failed:
        hint = (
            "Codex's `workspace-write` sandbox uses bubblewrap, which sets up an isolated "
            "network namespace even though network access is denied by policy; that setup can "
            "fail when codex itself is run inside a nested/rootless container (this environment). "
            "This run was already retried once with --sandbox danger-full-access; if it still "
            "fails, that retry isn't working around the nesting issue either — investigate the "
            "host's container/namespace permissions, or run this script outside the outer sandbox."
        )
    elif _AUTH_PATTERNS.search(combined):
        hint = _LOGIN_GUIDANCE[cli]
    elif _RATE_LIMIT_PATTERNS.search(combined):
        hint = "The CLI reported a rate limit or quota problem; check account usage and retry later."
    elif _MODEL_PATTERNS.search(combined):
        hint = "The requested model may be invalid or unavailable; verify the corresponding --*-model value and account access."
    elif not combined.strip():
        hint = "The CLI produced no stdout or stderr; run the displayed binary interactively to verify its installation and login state."
    else:
        hint = "Review the captured CLI output below; also verify authentication, model access, configuration, and network connectivity."

    details = f" CLI output: {excerpt}" if excerpt else ""
    result.error = f"{'; '.join(reasons)}. {hint}{details}"


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


def _codex_default_model() -> str:
    """Best-effort detection of the Codex default model.

    Tries three sources in order of reliability:
    1. ~/.codex/state_5.sqlite — most recent model actually used (most accurate).
    2. ~/.codex/config.toml / config.yaml — user-configured default.
    3. ~/.codex/models_cache.json — lowest-priority listed model as last resort.
    """
    import sqlite3

    # Source 1: most-recently-used model from the Codex SQLite state DB.
    for db_name in ("state_5.sqlite", "state_4.sqlite", "state.sqlite"):
        db_path = Path.home() / ".codex" / db_name
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT model FROM threads WHERE model IS NOT NULL "
                        "ORDER BY rowid DESC LIMIT 1"
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        return row[0]
                finally:
                    conn.close()
            except Exception:  # noqa: BLE001
                pass

    # Source 2: explicit default in the user config file.
    for config_name in ("config.toml", "config.yaml", "config.yml"):
        config_path = Path.home() / ".codex" / config_name
        if config_path.exists():
            try:
                text = config_path.read_text()
                # Simple regex extraction — avoids a toml/yaml dependency.
                m = re.search(r"""(?m)^\s*model\s*[=:]\s*["']?([^\s"'\n]+)["']?""", text)
                if m:
                    return m.group(1)
            except OSError:
                pass

    # Source 3: models_cache.json — lowest priority (= highest priority number means default).
    cache = Path.home() / ".codex" / "models_cache.json"
    try:
        data = json.loads(cache.read_text())
        models = [
            m for m in data.get("models", [])
            if isinstance(m, dict) and m.get("visibility") == "list"
        ]
        models.sort(key=lambda m: m.get("priority", 999))
        if models:
            return models[0]["slug"]
    except (OSError, json.JSONDecodeError, KeyError):
        pass

    return "unknown (codex CLI default)"


def _read_copilot_otel_tokens(otel_path: Path) -> tuple[int | None, int | None, int | None]:
    """Read gen_ai.usage.{input,output}_tokens from all 'chat <model>' OTel spans.

    Returns (total, input_tokens, output_tokens); all None if no spans found.
    """
    if not otel_path.exists():
        return None, None, None
    total_in = total_out = 0
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
        total_in += in_tok or 0
        total_out += out_tok or 0
        found = True
    if not found:
        return None, None, None
    return total_in + total_out, total_in, total_out


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
            result.raw_stdout = _text(e.stdout)
            result.raw_stderr = _text(e.stderr)
            result.duration_seconds = time.monotonic() - start
            return result
        result.duration_seconds = time.monotonic() - start
        result.raw_stdout = proc.stdout
        result.raw_stderr = proc.stderr
        total, inp, out = _read_copilot_otel_tokens(otel_path)
        result.total_tokens = total
        result.input_tokens = inp
        result.output_tokens = out
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

    result.response_text = last_message
    if not result.model:
        result.model = model  # fall back to what we requested, if anything
    finalize_process_result("copilot", result, proc.returncode)
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
        result.raw_stdout = _text(e.stdout)
        result.raw_stderr = _text(e.stderr)
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
    result.input_tokens = input_tokens + cache_read + cache_creation
    result.output_tokens = output_tokens
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

    finalize_process_result("claude", result, proc.returncode)
    return result


def run_codex(binary: str, prompt: str, cwd: Path, timeout: int, model: str | None = None,
              sandbox: str = "workspace-write", _is_retry: bool = False) -> RunResult:
    cmd = [
        binary, "exec", prompt,
        "--json",
        "--sandbox", sandbox,
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
        result.raw_stdout = _text(e.stdout)
        result.raw_stderr = _text(e.stderr)
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
            result.input_tokens = usage.get("input_tokens", 0) or 0
            result.output_tokens = usage.get("output_tokens", 0) or 0
            result.total_tokens = result.input_tokens + result.output_tokens
        elif etype in ("error", "turn.failed"):
            result.errors_encountered += 1

    result.response_text = last_message

    # See _CODEX_SANDBOX_INIT_PATTERNS: bubblewrap's network-namespace setup for
    # `workspace-write` can fail when codex itself runs inside a nested/rootless
    # container, silently turning every tool call into a failure that codex then
    # narrates as a normal (if useless) assistant message. Retry once with
    # `danger-full-access`, which skips bubblewrap sandboxing entirely — the same
    # trust model already used for claude (--dangerously-skip-permissions) and
    # copilot (--allow-all-tools --allow-all-paths) in this script, and safe here
    # because every eval prompt already instructs the agent not to perform real
    # network calls, downloads, or start real services.
    combined_for_retry_check = "\n".join(part for part in (result.raw_stderr, result.raw_stdout) if part)
    if (
        not _is_retry
        and sandbox == "workspace-write"
        and _CODEX_SANDBOX_INIT_PATTERNS.search(combined_for_retry_check)
    ):
        retry_result = run_codex(
            binary, prompt, cwd, timeout, model,
            sandbox="danger-full-access", _is_retry=True,
        )
        retry_result.transcript_lines.insert(
            0,
            "_Note: the initial attempt used `--sandbox workspace-write`, but codex's bubblewrap "
            "sandbox failed to initialize a network namespace in this environment; this run was "
            "automatically retried with `--sandbox danger-full-access`._",
        )
        return retry_result

    # Codex's JSON stream doesn't expose which model actually served the request;
    # fall back to the explicit --codex-model arg or read the default from the cache.
    result.model = model or _codex_default_model()
    finalize_process_result("codex", result, proc.returncode)
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
            model: str | None = None) -> tuple[str, dict, str, RunResult]:
    prompt = build_prompt(ev["prompt"], skill_path if config == "with_skill" else None)
    scratch = Path(tempfile.mkdtemp(prefix=f"skilleval-{cli}-{ev['id']}-{config}-"))
    try:
        runner = CLI_RUNNERS[cli]
        try:
            result = runner(binary, prompt, scratch, timeout, model)
        except OSError as error:
            result = RunResult(
                error=(
                    f"Could not start {cli} binary `{binary}`: {error}. "
                    "Verify the path, executable permissions, and runtime dependencies."
                ),
                raw_stderr=str(error),
            )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
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

    # Keep enough raw process output to diagnose authentication, quota, model,
    # configuration, and CLI parsing failures without creating unbounded logs.
    diagnostics = {
        "error": result.error,
        "exit_code": result.exit_code,
        "stderr": result.raw_stderr[-8000:],
        "stdout": result.raw_stdout[-8000:],
        "output_truncated": len(result.raw_stderr) > 8000 or len(result.raw_stdout) > 8000,
    }
    (outputs_dir / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2))

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
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
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


def run_grader(grader_cli: str, grader_binary: str, run_dir: Path, eval_meta: dict, timeout: int) -> tuple[bool, str | None]:
    """Invoke the grader CLI to write grading.json into run_dir. Returns (success, grader_model)."""
    transcript_path = run_dir / "transcript.md"
    outputs_dir = run_dir / "outputs"
    prompt = build_grader_prompt(eval_meta, transcript_path, outputs_dir)
    runner = CLI_RUNNERS[grader_cli]
    # Grader needs read access to the actual run_dir (not a scratch dir) so it can
    # read the transcript/outputs and write grading.json alongside them.
    result = runner(grader_binary, prompt, run_dir, timeout)

    graded_by = {"cli": grader_cli, "model": result.model}
    grading_path = run_dir / "grading.json"
    if grading_path.exists():
        try:
            parsed = json.loads(grading_path.read_text())
            # Record who graded this run — grading.json is otherwise the only
            # persisted trace of the grading step, and on a rerun where every
            # run is already graded, grade_all_runs() has nothing left to grade
            # and so can't report a model; without this, the aggregated report
            # falls back to "n/a (grading skipped)" even though real grading
            # data (just from an earlier session) is right there on disk.
            if isinstance(parsed, dict):
                parsed["graded_by"] = graded_by
                grading_path.write_text(json.dumps(parsed, indent=2))
            return True, result.model
        except json.JSONDecodeError:
            pass

    # Fall back: the grader CLI sometimes prints the JSON instead of writing the
    # file (especially CLIs run in restrictive sandboxes). Try to extract a JSON
    # object from its response text and write it ourselves.
    match = re.search(r"\{.*\}", result.response_text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                parsed["graded_by"] = graded_by
            grading_path.write_text(json.dumps(parsed, indent=2))
            return True, result.model
        except json.JSONDecodeError:
            pass

    print(f"WARNING: grader did not produce valid grading.json for {run_dir}", file=sys.stderr)
    return False, result.model


def grade_all_runs(workspace: Path, cli: str, grader_cli: str, grader_binary: str,
                    workers: int, timeout: int) -> str | None:
    """Grade all ungraded runs under workspace/<cli>. Returns the grader model if detected."""
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
        return None

    print(f"  [{cli}] grading {len(run_dirs)} runs using '{grader_cli}' as judge...")
    detected_model: str | None = None
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_grader, grader_cli, grader_binary, run_dir, eval_meta, timeout): run_dir
            for run_dir, eval_meta in run_dirs
        }
        for future in as_completed(futures):
            run_dir = futures[future]
            try:
                ok, model = future.result()
            except Exception as e:  # noqa: BLE001
                print(f"    GRADE FAILED {run_dir}: {e}", file=sys.stderr)
                continue
            if model and detected_model is None:
                detected_model = model
            print(f"    graded {run_dir} [{'OK' if ok else 'FALLBACK-FAILED'}]")
    return detected_model


# --------------------------------------------------------------------------
# Markdown helpers shared by cross-CLI reports
# --------------------------------------------------------------------------

def _fmt_tokens(value: float) -> str:
    """Abbreviate large token counts to k-notation for readability."""
    if abs(value) >= 1000:
        return f"{value/1000:.0f}k"
    return f"{value:.0f}"


# --------------------------------------------------------------------------
# Cross-CLI aggregation
# --------------------------------------------------------------------------


def detect_grader_identity(workspace: Path, clis: list[str]) -> tuple[str | None, str | None]:
    """Recover (grader_cli, grader_model) from grading.json's "graded_by" field.

    Used as a fallback when the current invocation didn't freshly grade
    anything (e.g. every run was already graded in an earlier session) — in
    that case grade_all_runs() has nothing to report a model for, even though
    real grading data is sitting on disk. Returns the most common (cli, model)
    pair across all runs, or (None, None) if no run carries the field (e.g.
    grading.json predates this field being written)."""
    counts: collections.Counter[tuple[str, str]] = collections.Counter()
    for cli in clis:
        for grading_path in (workspace / cli).glob("eval-*/*/run-*/grading.json"):
            try:
                data = json.loads(grading_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            graded_by = data.get("graded_by") if isinstance(data, dict) else None
            if isinstance(graded_by, dict) and graded_by.get("cli") and graded_by.get("model"):
                counts[(graded_by["cli"], graded_by["model"])] += 1
    if not counts:
        return None, None
    return counts.most_common(1)[0][0]


def detect_cli_model(workspace: Path, cli: str) -> str:
    """Best-effort determination of which model a CLI actually used, based on
    the `model` field each run's timing.json records (see run_copilot /
    run_claude / run_codex). Returns the most common non-empty value across
    all of that CLI's runs, or a fallback label if nothing was recorded
    (e.g. an older run predating this field)."""
    counts: collections.Counter[str] = collections.Counter()
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
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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


def _prompt_cell(ev: dict) -> str:
    """First 80 chars of the eval prompt, plain text."""
    p = ev["prompt"]
    return (p[:80] + "...") if len(p) > 80 else p


def generate_consolidated_benchmark_md(
    workspace: Path,
    clis: list[str],
    skill_name: str,
    evals: list[dict],
    grader_cli: str | None,
    grader_model: str | None,
) -> str:
    """Consolidated cross-CLI benchmark.md.

    Writes 4 summary mini-tables (evals passed, pass rate, time, tokens) plus a
    per-eval detail table with a Mean ±σ footer row. Generated for 1–3 CLIs.
    """
    if calculate_stats is None:
        return f"# Skill Benchmark: {skill_name}\n\nAggregation skipped (skill-creator not found).\n"

    configs = ["with_skill", "without_skill"]
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cli_models = {cli: detect_cli_model(workspace, cli) for cli in clis}

    # Collect per-config per-CLI aggregates
    agg: dict[str, dict[str, dict]] = {
        c: {cli: {"pass_rates": [], "time_total": 0.0, "tokens_total": 0,
                  "evals_passed": 0, "evals_total": 0}
            for cli in clis}
        for c in configs
    }
    # per_eval[ev_id][config][cli] = (passed, total) or None
    per_eval: dict = {ev["id"]: {c: {} for c in configs} for ev in evals}

    for cli in clis:
        for ev in evals:
            ev_id = ev["id"]
            base = workspace / cli / eval_dir_name(ev)
            for config in configs:
                cell = agg[config][cli]
                cell["evals_total"] += 1
                grading_path = base / config / "run-1" / "grading.json"
                timing_path = base / config / "run-1" / "timing.json"
                per_eval[ev_id][config][cli] = None
                if grading_path.exists():
                    try:
                        g = json.loads(grading_path.read_text())
                        s = g.get("summary", {})
                        pr = s.get("pass_rate", 0.0)
                        cell["pass_rates"].append(pr)
                        if pr >= 1.0:
                            cell["evals_passed"] += 1
                        per_eval[ev_id][config][cli] = (s.get("passed", 0), s.get("total", 0))
                    except (json.JSONDecodeError, OSError):
                        pass
                if timing_path.exists():
                    try:
                        t = json.loads(timing_path.read_text())
                        cell["time_total"] += t.get("total_duration_seconds", 0.0) or 0.0
                        cell["tokens_total"] += t.get("total_tokens", 0) or 0
                    except (json.JSONDecodeError, OSError):
                        pass

    pr_stats: dict[str, dict[str, dict]] = {
        c: {cli: calculate_stats(agg[c][cli]["pass_rates"]) for cli in clis}
        for c in configs
    }

    def _agent_label(cli: str) -> str:
        return f"{cli.title()} (`{cli_models[cli]}`)"

    def _evals_cell(config: str, cli: str) -> str:
        d = agg[config][cli]
        return f"{d['evals_passed']} / {d['evals_total']}"

    def _lift_evals(cli: str) -> str:
        diff = agg["with_skill"][cli]["evals_passed"] - agg["without_skill"][cli]["evals_passed"]
        sign = "+" if diff >= 0 else ""
        arrow = " \u2191" if diff > 0 else (" \u2193" if diff < 0 else "")
        return f"**{sign}{diff}{arrow}**"

    def _pass_rate_cell(config: str, cli: str) -> str:
        s = pr_stats[config][cli]
        return f"{s['mean']*100:.0f}% \u00b1{s['stddev']*100:.0f}%"

    def _lift_pass_rate(cli: str) -> str:
        diff_pp = (pr_stats["with_skill"][cli]["mean"] - pr_stats["without_skill"][cli]["mean"]) * 100
        sign = "+" if diff_pp >= 0 else ""
        arrow = " \u2191" if diff_pp > 0 else ""
        return f"**{sign}{diff_pp:.0f}pp{arrow}**"

    def _time_cell(config: str, cli: str) -> str:
        return f"{agg[config][cli]['time_total']:.0f} s"

    def _delta_time(cli: str) -> str:
        diff = agg["with_skill"][cli]["time_total"] - agg["without_skill"][cli]["time_total"]
        sign = "+" if diff >= 0 else ""
        return f"{sign}{diff:.0f} s \u2193"

    def _tokens_cell(config: str, cli: str) -> str:
        return _fmt_tokens(agg[config][cli]["tokens_total"])

    def _delta_tokens(cli: str) -> str:
        diff = agg["with_skill"][cli]["tokens_total"] - agg["without_skill"][cli]["tokens_total"]
        sign = "+" if diff >= 0 else ""
        return f"{sign}{_fmt_tokens(diff)} \u2193"

    def _mini_table(title: str, wos_fn, ws_fn, lift_fn) -> list[str]:
        rows = [f"### {title}", "", "| Agent | w/o skill | w/ skill | Lift |", "|---|---|---|---|"]
        for cli in clis:
            rows.append(f"| {_agent_label(cli)} | {wos_fn(cli)} | {ws_fn(cli)} | {lift_fn(cli)} |")
        return rows

    def _result_cell(ev_id: int, config: str, cli: str) -> str:
        val = per_eval.get(ev_id, {}).get(config, {}).get(cli)
        if val is None or val[1] == 0:
            return "n/a"
        passed, total = val
        return f"{'PASS' if passed == total else 'FAIL'} ({passed}/{total})"

    agents_line = ", ".join(_agent_label(cli) for cli in clis)
    # Built straight from grader_cli/grader_model (not _agent_label/cli_models,
    # which are keyed off the *executor* runs) because the grader CLI is
    # invoked without the --*-model override, so its model can differ from
    # whatever that same CLI used as an eval executor.
    if grader_cli and grader_model:
        grader_line = f"{grader_cli.title()} (`{grader_model}`)"
    elif grader_model:
        grader_line = f"`{grader_model}` (grading agent unknown)"
    else:
        grader_line = "n/a (grading skipped)"
    eval_ids_str = ", ".join(str(ev["id"]) for ev in evals)

    lines: list[str] = [
        "<!--",
        "SPDX-FileCopyrightText: (C) 2026 Intel Corporation",
        "SPDX-License-Identifier: Apache-2.0",
        "-->",
        "",
        f"# Skill Benchmark: {skill_name}",
        "",
        f"**Agents**: {agents_line}",
        f"**Grader**: {grader_line}",
        f"**Date**: {timestamp}",
        f"**Evals**: {eval_ids_str} (1 run per configuration)",
        "",
        "## Summary",
        "",
        "> Skill lift = with skill \u2212 without skill. \u2191 = better, \u2193 = higher cost (expected).",
        "",
    ]
    lines += _mini_table("Evals passed",
                         lambda c: _evals_cell("without_skill", c),
                         lambda c: _evals_cell("with_skill", c),
                         _lift_evals) + [""]
    lines += _mini_table("Pass rate (avg \u00b1 \u03c3 across evals)",
                         lambda c: _pass_rate_cell("without_skill", c),
                         lambda c: _pass_rate_cell("with_skill", c),
                         _lift_pass_rate) + [""]
    lines += _mini_table("Time (total across all evals)",
                         lambda c: _time_cell("without_skill", c),
                         lambda c: _time_cell("with_skill", c),
                         _delta_time) + [""]
    lines += _mini_table("Tokens (total across all evals)",
                         lambda c: _tokens_cell("without_skill", c),
                         lambda c: _tokens_cell("with_skill", c),
                         _delta_tokens) + [""]

    w_hdrs = " | ".join(f"{cli.title()} (w/)" for cli in clis)
    wo_hdrs = " | ".join(f"{cli.title()} (w/o)" for cli in clis)
    # "Eval" + "Prompt" + one column per CLI per config — must match the
    # header cell count exactly, or the table renders with mismatched columns.
    sep_cols = "|".join(["---"] * (2 + len(clis) * 2))
    lines += [
        "## Per-Eval Detail",
        "",
        "> Each cell is PASS/FAIL for that run, with the count of expectations met "
        "in parentheses (e.g. `PASS (5/5)`); `n/a` means no grading.json was found "
        "for that (eval, config, agent) combination.",
        "",
        f"| Eval | Prompt | {w_hdrs} | {wo_hdrs} |",
        f"|{sep_cols}|",
    ]

    footer_prs: dict[str, list[float]] = {f"{cli}_{s}": [] for cli in clis for s in ("w", "wo")}
    for ev in evals:
        ev_id = ev["id"]
        w_cells = " | ".join(_result_cell(ev_id, "with_skill", cli) for cli in clis)
        wo_cells = " | ".join(_result_cell(ev_id, "without_skill", cli) for cli in clis)
        lines.append(f"| {ev_id} | {_prompt_cell(ev)} | {w_cells} | {wo_cells} |")
        for cli in clis:
            for config, suffix in (("with_skill", "w"), ("without_skill", "wo")):
                val = per_eval.get(ev_id, {}).get(config, {}).get(cli)
                if val is not None and val[1] > 0:
                    footer_prs[f"{cli}_{suffix}"].append(val[0] / val[1])

    def _sigma_cell(key: str) -> str:
        prs = footer_prs[key]
        if not prs:
            return "n/a"
        s = calculate_stats(prs)
        return f"**{s['mean']*100:.0f}% \u00b1{s['stddev']*100:.0f}%**"

    w_sigma = " | ".join(_sigma_cell(f"{cli}_w") for cli in clis)
    wo_sigma = " | ".join(_sigma_cell(f"{cli}_wo") for cli in clis)
    lines.append(f"| | **Mean \u00b1\u03c3** | {w_sigma} | {wo_sigma} |")
    return "\n".join(lines)


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
    parser.add_argument("--copilot-bin", default=None, help="Explicit path to the copilot binary (default: auto-detect on PATH)")
    parser.add_argument("--claude-bin", default=None, help="Explicit path to the claude binary (default: auto-detect on PATH)")
    parser.add_argument("--codex-bin", default=None, help="Explicit path to the codex binary (default: auto-detect on PATH / nvm fallback)")
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
    print("Binaries:")
    for cli, binary in binaries.items():
        print(f"  {cli}: {binary}")
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
            status = "OK" if not result.error else "ERROR (details below)"
            print(f"{'DONE':6} {cli:8} eval-{ev['id']:<2} {config:14} {result.duration_seconds:6.1f}s  -> {run_dir}  [{status}]")
            if result.error:
                print(f"       {result.error}")
                print(f"       Diagnostic log: {run_dir / 'outputs' / 'diagnostics.json'}")
            results_summary.append({
                "cli": cli, "eval_id": ev["id"], "config": config,
                "duration_seconds": result.duration_seconds,
                "tokens": result.total_tokens, "error": result.error,
                "model": result.model,
                "exit_code": result.exit_code,
                "diagnostics": str(run_dir / "outputs" / "diagnostics.json"),
            })

    summary_path = workspace / "run_summary.json"
    summary_path.write_text(json.dumps(results_summary, indent=2))
    print(f"\nWrote run summary: {summary_path}")

    # ----------------------------------------------------------------------
    # Grading
    # ----------------------------------------------------------------------
    grader_model: str | None = None
    grader_cli: str | None = None
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
                detected = grade_all_runs(workspace, cli, grader_cli, grader_binary, args.grader_workers, args.grader_timeout)
                if detected and grader_model is None:
                    grader_model = detected

    # Fall back to grading.json's persisted "graded_by" field when nothing was
    # freshly graded this invocation (every run already had a grading.json from
    # an earlier session) — otherwise the report would claim grading was
    # skipped even though real grading data is on disk.
    if grader_model is None:
        recovered_cli, recovered_model = detect_grader_identity(workspace, [c for c in CLI_RUNNERS if (workspace / c).exists()])
        if recovered_model:
            grader_cli, grader_model = recovered_cli, recovered_model

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
                # Per-CLI benchmark.md is exactly skill-creator's own
                # generate_markdown() output — unmodified, so it stays
                # identical to what skill-creator itself would produce.
                (cli_dir / "benchmark.md").write_text(generate_markdown(benchmark))
                summary = benchmark["run_summary"]
                configs_seen = [k for k in summary if k != "delta"]
                parts = [f"{c}={summary[c]['pass_rate']['mean']*100:.0f}%" for c in configs_seen]
                print(f"  [{cli}] {cli_dir / 'benchmark.json'}  ({', '.join(parts)})")

            print("\n=== Consolidated benchmark (all agents) ===")
            if len(binaries) >= 2:
                cross = build_cross_cli_benchmark(workspace, list(binaries.keys()), skill_name, configs=configs)
                (workspace / "benchmark.json").write_text(json.dumps(cross, indent=2))
            (workspace / "benchmark.md").write_text(
                generate_consolidated_benchmark_md(
                    workspace, list(binaries.keys()), skill_name, evals, grader_cli, grader_model
                )
            )
            print(f"  Written: {workspace / 'benchmark.md'}")

    print("\nOptional next step — open a review in your browser:")
    for cli in binaries:
        print(f"  python3 {SKILL_CREATOR_DIR}/eval-viewer/generate_review.py {workspace / cli} "
              f"--skill-name {skill_name} --benchmark {workspace / cli / 'benchmark.json'} "
              f"--static {workspace / cli / 'review.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
