#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Scaffold a manufacturing sample app by copying a reference app and renaming it.

Instead of hand-writing ~100 KB of Compose/Makefile/service code, copy the
reference implementation and change only what is vertical-specific:

  multimodal | vllm | agentic  ->  copy industrial-edge-insights-multimodal into a new
                                   flat stack directory (out_dir)
  ts                           ->  copy apps/<template_app>/ inside an existing
                                   industrial-edge-insights-time-series checkout

The script:
  1. copies the reference, leaving out docs/tests/training/helm and repo metadata;
  2. prunes files the chosen mode does not use (vllm/agentic overlays, ui-service, MCP);
  3. applies a rename map (paths and file contents) derived from the spec;
  4. places the models and simulation data named in the spec (hard links when possible);
  5. applies known fixes (proxy-safe healthchecks, S3 healthcheck, vision model-proc,
     fused label in the MQTT payload);
  6. writes .env (local image names, stable tags, fusion/LLM settings, generated secrets);
  7. optionally wires OpenMES (a real one, or the dummy receiver for testing);
  8. reports every line that still mentions the old vertical, so the agent edits
     only those lines (UDF logic, labels, prompts, sensor fields).

Usage:
  python scaffold_stack.py --spec vertical.yaml            # or vertical.json
  python scaffold_stack.py --spec vertical.yaml --dry-run  # show the plan only
  python scaffold_stack.py --spec vertical.yaml --force    # replace an existing target
"""

import argparse
import json
import os
import re
import secrets
import shutil
import stat
import string
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
OPENMES_ASSETS = SKILL_DIR / "assets" / "openmes"
OPENMES_OVERRIDE = "docker-compose-openmes.override.yml"
STABLE_DEPS_TAG = "2026.2.0"

COMMON_EXCLUDES = {
    "docs", "training", "helm", ".github", ".cursor", ".git", "__pycache__", ".venv",
    "insights-workbench", "AGENTS.md", "CLAUDE.md", "CHANGELOG.md", "README-dockerhub.md",
    "third-party-programs.txt", "nginx-cert.pem",
}
MODE_PRUNE = {
    "multimodal": ["docker-compose-vllm.yml", "docker-compose-agentic.yml", "docker-compose-mcp.yml",
                   "ui-service", "mcp-server", "configs/agentic", "configs/vllm"],
    "vllm": ["docker-compose-agentic.yml", "docker-compose-mcp.yml", "mcp-server", "configs/agentic"],
    "agentic": [],
}
# Copied/linked separately from the spec, never through the rename pass.
DATA_PATHS = {"weld-data-simulator/simulation-data", "configs/dlstreamer-pipeline-server/models",
              "configs/time-series-analytics-microservice/models", "configs/agentic/models", "configs/vllm"}
TEXT_NAMES = {"Makefile", "Dockerfile", ".env", ".gitignore"}
TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".json", ".conf", ".sh", ".tick", ".txt", ".md", ".html",
                 ".js", ".css", ".template", ".toml", ".ini", ".mdc", ".cfg", ""}


def die(msg):
    sys.exit(f"ERROR: {msg}")


def load_spec(path):
    text = Path(path).read_text()
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml  # noqa: PLC0415
        except ImportError:
            die("PyYAML is not installed: pip install pyyaml, or write the spec as .json")
        return yaml.safe_load(text)
    return json.loads(text)


def need(spec, *keys):
    cur = spec
    for k in keys:
        if not isinstance(cur, dict) or cur.get(k) in (None, ""):
            die(f"spec is missing '{'.'.join(keys)}'")
        cur = cur[k]
    return cur


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


_HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")


def validate_host(host):
    """Reject a host/IP value that is not safe to embed in generated shell
    scripts (start_dummy_openmes_receiver.sh/start_dummy_openmes_publisher.sh,
    README snippets): only hostname/IPv4 characters are accepted, so a spec
    value cannot inject shell metacharacters or be parsed as a command flag
    (e.g. a leading '-')."""
    if not host or not _HOST_RE.match(host):
        die(f"host_ip {host!r} is not a safe hostname/IPv4 address (letters, digits, '.', '-' only)")
    return host


_PATH_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def validate_path_component(name, what):
    """Reject a name that will be joined as a single path segment under
    ``apps/`` (``app_name``/``template_app``) before it is ever used in a
    path. A value containing '/', '\\' or '..', or an absolute path, could
    otherwise escape the ``apps/`` directory entirely -- e.g. ``app_name:
    "../../etc"`` or an absolute ``app_name: "/etc"`` (``Path("apps") /
    "/etc"`` silently discards the "apps" segment and resolves to "/etc").
    Only a plain directory-name-shaped string is accepted."""
    if (not name or "/" in name or "\\" in name or name in (".", "..")
            or not _PATH_COMPONENT_RE.match(name)):
        die(f"{what} {name!r} must be a plain directory name "
            "(letters, digits, '_', '-', '.'; no path separators or '..')")
    return name


def _is_ancestor_or_self(maybe_ancestor, path):
    return path == maybe_ancestor or maybe_ancestor in path.parents


def validate_removal_target(path, *, protect):
    """Guard the one destructive `shutil.rmtree` per mode behind a bounded,
    validated path before `--force` is honoured.

    Refuses to replace a target that is a symlink, or that is the same as,
    or an ancestor of, the filesystem root / the caller's home directory /
    this skill's own directory / the current working directory -- a normal
    scaffold target *inside* one of those (e.g. `~/projects/my-stack`) is
    unaffected, only consuming one of those directories itself is blocked.
    The reference checkout(s) in *protect* get the stricter, symmetric
    'overlap' check: the target must not equal, contain, or be contained by
    a reference directory in either direction, since copying/removing
    through an overlapping path would corrupt the source being copied from.
    Closes the 'no root/home/workspace/reference or ancestors,
    symlink/overlap/escape' gap on `scaffold_stack.py --force`.
    """
    target = Path(path)
    if target.is_symlink():
        die(f"refusing --force on {path}: target is a symlink")
    resolved = target.resolve(strict=False)
    ancestor_only = {Path(resolved.anchor or "/"), Path.home().resolve(),
                     SKILL_DIR.resolve(), Path.cwd().resolve()}
    for root in ancestor_only:
        if _is_ancestor_or_self(resolved, root):
            die(f"refusing --force on {path}: would remove a protected path ({root})")
    for ref in protect:
        if ref is None:
            continue
        ref_resolved = Path(ref).resolve(strict=False)
        if resolved == ref_resolved or _is_ancestor_or_self(resolved, ref_resolved) \
                or _is_ancestor_or_self(ref_resolved, resolved):
            die(f"refusing --force on {path}: overlaps the reference directory ({ref_resolved})")
    return resolved


def is_text(path):
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
        return False
    try:
        path.read_text(encoding="utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def link_or_copy(src, dst):
    """Hard-link files when possible (no extra disk for large models), else copy."""
    src, dst = Path(src), Path(dst)
    if not src.exists():
        die(f"path not found: {src}")
    files = [src] if src.is_file() else [p for p in src.rglob("*") if p.is_file()]
    for f in files:
        d = dst if src.is_file() else dst / f.relative_to(src)
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists():
            d.unlink()
        try:
            os.link(f, d)
        except OSError:
            shutil.copy2(f, d)


def in_data_path(root, path, data_paths):
    rel = path.relative_to(root).as_posix()
    return any(rel == d or rel.startswith(d + "/") for d in data_paths)


def apply_renames(root, rename_map, data_paths):
    """Rewrite text contents and rename paths (deepest first)."""
    pairs = sorted(rename_map.items(), key=lambda kv: -len(kv[0]))
    changed = 0
    for path in sorted(root.rglob("*"), key=lambda p: -len(p.parts)):
        # Data/model files may be hard links to the reference: never rewrite them in place.
        if in_data_path(root, path, data_paths):
            continue
        if path.is_file() and not path.is_symlink() and is_text(path):
            text = path.read_text(encoding="utf-8")
            new = text
            for old, rep in pairs:
                new = new.replace(old, rep)
            if new != text:
                path.write_text(new, encoding="utf-8")
                changed += 1
    for path in sorted(root.rglob("*"), key=lambda p: -len(p.parts)):
        name = path.name
        for old, rep in pairs:
            name = name.replace(old, rep)
        if name != path.name:
            path.rename(path.with_name(name))
    return changed


def patch_text(path, old, new, required=True):
    text = Path(path).read_text()
    if old not in text:
        if required:
            die(f"expected text not found in {path}: {old[:70]!r}")
        return False
    Path(path).write_text(text.replace(old, new, 1))
    return True


def set_env(env_path, values):
    lines = env_path.read_text().splitlines()
    seen = set()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Z0-9_]+)=", line)
        if m and m.group(1) in values:
            lines[i] = f"{m.group(1)}={values[m.group(1)]}"
            seen.add(m.group(1))
    extra = [f"{k}={v}" for k, v in values.items() if k not in seen]
    if extra:
        lines += ["", "# --- added by scaffold_stack.py ---"] + extra
    env_path.write_text("\n".join(lines) + "\n")


def gen_user(word):
    base = re.sub(r"[^a-z]", "", word.lower())
    return (base + "user")[:14] if len(base) >= 1 else "stackuser"


def gen_password():
    return "".join(secrets.choice(string.ascii_letters) for _ in range(10)) + \
        "".join(secrets.choice(string.digits) for _ in range(6))


def fill_secrets(env_path, word):
    """Generate values for empty credential keys. Values are never printed."""
    rules = {
        "INFLUXDB_USERNAME": lambda: gen_user(word + "influx"),
        "VISUALIZER_GRAFANA_USER": lambda: gen_user(word + "admin"),
        "S3_STORAGE_USERNAME": lambda: gen_user(word + "store"),
        "SEAWEEDFS_WEB_AUTH_USER": lambda: gen_user(word + "filer"),
        "MTX_WEBRTCICESERVERS2_0_USERNAME": lambda: gen_user(word + "turn"),
        "INFLUXDB_PASSWORD": gen_password,
        "VISUALIZER_GRAFANA_PASSWORD": gen_password,
        "S3_STORAGE_PASSWORD": lambda: secrets.token_hex(16),
        "SEAWEEDFS_WEB_AUTH_PASSWORD": lambda: secrets.token_hex(16),
        "MTX_WEBRTCICESERVERS2_0_PASSWORD": lambda: secrets.token_hex(16),
    }
    lines = env_path.read_text().splitlines()
    generated = []
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Z0-9_]+)=\s*$", line)
        if m and m.group(1) in rules:
            lines[i] = f"{m.group(1)}={rules[m.group(1)]()}"
            generated.append(m.group(1))
    env_path.write_text("\n".join(lines) + "\n")
    env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return generated


SECRET_KEY_RE = re.compile(r"(_USERNAME|_PASSWORD|_USER|_SECRET|_TOKEN|_API_KEY|_ACCESS_KEY)$")


def blank_env_secrets(env_path):
    """Start from a secret-free .env: the reference checkout may already be configured."""
    lines = env_path.read_text().splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
        if m and SECRET_KEY_RE.search(m.group(1)) and m.group(2).strip() \
                and not re.fullmatch(r"[0-9.]+", m.group(2).strip()):
            lines[i] = f"{m.group(1)}="
    env_path.write_text("\n".join(lines) + "\n")


def normalize_ir_names(model_dir):
    """DLSPS pipelines load <model dir>/model.xml; give a supplied IR pair that name."""
    d = Path(model_dir)
    xmls = sorted(d.glob("*.xml"))
    if not xmls or (d / "model.xml").exists():
        return
    if len(xmls) > 1:
        die(f"{d} contains several .xml files; supply a folder with a single OpenVINO IR pair")
    xml = xmls[0]
    binf = xml.with_suffix(".bin")
    if not binf.exists():
        die(f"{binf.name} not found next to {xml.name} in the supplied vision model folder")
    for src, name in ((xml, "model.xml"), (binf, "model.bin")):
        link_or_copy(src, d / name)
        src.unlink()


def prune_makefile(out, pruned, fallback, skip_download):
    """Drop references to pruned Compose overlays and unneeded LLM download/start steps."""
    mk = out / "Makefile"
    t = mk.read_text()
    for name, var in (("docker-compose-vllm.yml", "VLLM"), ("docker-compose-agentic.yml", "AGENTIC"),
                      ("docker-compose-mcp.yml", "MCP")):
        if name in pruned:
            t = t.replace(f" -f $(DOCKER_COMPOSE_FILE_{var})", "")
            if var == "MCP":
                t = re.sub(r"^MCP_COMPOSE_ARG = .*$", "MCP_COMPOSE_ARG =", t, flags=re.M)
    if fallback or skip_download:
        t = t.replace("\t$(MAKE) download_model || exit 1; \\\n", "")
    if fallback:
        t = t.replace("$(MCP_COMPOSE_ARG) up -d || exit 1;", "$(MCP_COMPOSE_ARG) up -d --scale apm-llm=0 || exit 1;")
    mk.write_text(t)


def make_live(out, rtsp_url):
    """Live camera/sensor input: drop the simulator service and point the pipeline at the camera."""
    dc = out / "docker-compose.yml"
    t = dc.read_text()
    t = re.sub(r"\n  ia-weld-data-simulator:\n.*?(?=\n  nginx:)", "", t, flags=re.S)
    t = re.sub(r"\n      ia-weld-data-simulator:\n        condition: [a-z_]+", "", t)
    dc.write_text(t)
    for name in ("config.json", "pipeline-request-cpu.json", "config_auto_start_off.json"):
        p = out / "configs/dlstreamer-pipeline-server" / name
        if p.exists():
            p.write_text(p.read_text().replace("rtsp://mediamtx:8554/live.stream", rtsp_url))


def write_model_proc(model_dir):
    """Geti-style classifiers need explicit RGB / [0,1] / mean-std preprocessing in DL Streamer."""
    xml = next(Path(model_dir).glob("*.xml"), None)
    if not xml:
        return None
    text = xml.read_text(errors="ignore")
    if 'intensity_mode value="scale_to_unit"' not in text:
        return None
    mean = re.search(r'<mean_values value="([^"]+)"', text)
    scale = re.search(r'<scale_values value="([^"]+)"', text)
    labels = re.search(r'<labels value="([^"]+)"', text)
    names = re.search(r'type="Parameter".*?names="([^",]+)', text, re.S)
    if not (mean and scale and labels):
        return None
    proc = {
        "json_schema_version": "2.2.0",
        "input_preproc": [{
            "format": "image",
            "layer_name": names.group(1) if names else "image",
            "params": {"resize": "no-aspect-ratio", "color_space": "RGB", "range": [0.0, 1.0],
                       "mean": [float(x) for x in mean.group(1).split()],
                       "std": [float(x) for x in scale.group(1).split()]},
        }],
        "output_postproc": [{"converter": "label", "method": "softmax", "labels": labels.group(1).split()}],
    }
    out = Path(model_dir) / "model-proc.json"
    if out.exists():
        out.unlink()  # may be a hard link to the source model folder
    out.write_text(json.dumps(proc, indent=4) + "\n")
    return out


def add_model_proc_to_pipeline(cfg_dir, container_model_dir):
    for name in ("config.json", "pipeline-request-cpu.json", "config_auto_start_off.json"):
        p = Path(cfg_dir) / name
        if not p.exists():
            continue
        data = json.loads(p.read_text())

        def walk(o):
            if isinstance(o, dict):
                props = o.get("classification-properties")
                if isinstance(props, dict) and "model" in props:
                    props["model-proc"] = f"{container_model_dir}/model-proc.json"
                    props["pre-process-backend"] = "opencv"
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(data)
        p.write_text(json.dumps(data, indent=4) + "\n")


def fix_healthchecks(compose_files):
    """Bypass host proxies in localhost healthchecks; accept any HTTP status from the S3 gateway."""
    for f in compose_files:
        if not f.exists():
            continue
        t = f.read_text()
        t = t.replace('["CMD", "curl", "-f", "http://localhost:8333/"]',
                      "[\"CMD-SHELL\", \"curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "
                      "http://localhost:8333/ | grep -qE '^[2-4][0-9][0-9]$$'\"]")
        t = re.sub(r'\["CMD", "curl", "-f", "(http://localhost[^"]*)"\]',
                   r'["CMD", "curl", "-f", "--noproxy", "*", "\1"]', t)
        t = re.sub(r'"CMD-SHELL", "curl (?!-s --noproxy)(?!--noproxy)', "\"CMD-SHELL\", \"curl --noproxy '*' ", t)
        f.write_text(t)


def leftovers(root, patterns, skip_paths):
    pat = re.compile("|".join(patterns), re.I)
    hits = []
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.name == ".env" or in_data_path(root, p, skip_paths) or not is_text(p):
            continue  # .env holds credentials: never echo its lines
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                hits.append((p.relative_to(root).as_posix(), n, line.strip()[:140]))
    return hits


# --------------------------------------------------------------------------- OpenMES
# Both the receiver and the publisher run strictly in the foreground (no
# `&`, no `nohup`/`disown`/`setsid`, no PID files, no kill logic). A shell
# background job (`cmd &`) is reparented to init and keeps running after the
# launching script/shell exits -- it is *not* scoped to that shell's
# lifetime, so claiming otherwise would be false. A genuine foreground
# process has no such problem: it only runs for as long as something is
# actively waiting on it, and is torn down the moment that stops (Ctrl-C,
# the terminal closing, or an agent's own attached background/async tool
# execution being stopped) -- never through this script searching for and
# signalling an arbitrary PID.
#
# Two supported ways to run two foreground processes at once:
#   1. An agent with its own attached background/async tool execution (e.g.
#      a "run in background, attached to this session" bash mode) starts the
#      receiver that way, waits for /health, then starts the publisher the
#      same way, and stops both with that same tool's explicit stop
#      capability when done.
#   2. A human (or an agent with only a single blocking shell) runs the
#      receiver script in one terminal and the publisher script -- which
#      itself waits for /health before exec'ing -- in a second terminal, and
#      stops each with Ctrl-C.
START_DUMMY_RECEIVER = r"""#!/usr/bin/env bash
# Runs the dummy OpenMES receiver in the foreground. Start this first --
# in its own terminal, or via your tool's attached background/async
# execution (never shell `&`/nohup/disown). Alerts page:
# http://{host}:8099/ (no login; read-only; dummy data). Stop with Ctrl-C
# (or your tool's stop capability); there is no separate stop script and no
# PID file to manage.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || {{ python3 -m venv .venv && .venv/bin/pip install -q paho-mqtt requests; }}
exec python3 -u dummy_openmes_receiver.py --host {host} --port 8099 \
  --token-file ./openmes_token --log-file ./dummy_openmes_issues.jsonl
"""

START_DUMMY_PUBLISHER = r"""#!/usr/bin/env bash
# Waits for the dummy OpenMES receiver (start_dummy_openmes_receiver.sh,
# already running in its own terminal or background task) to report
# healthy, then runs the publisher in the foreground. Stop with Ctrl-C (or
# your tool's stop capability); there is no separate stop script and no PID
# file to manage. Fails loudly -- instead of silently backgrounding a dead
# process -- if the receiver never becomes healthy.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || {{ python3 -m venv .venv && .venv/bin/pip install -q paho-mqtt requests; }}
ready=""
for i in $(seq 1 40); do
  if curl -sf --noproxy '*' http://{host}:8099/health >/dev/null; then
    ready=1
    break
  fi
  sleep 0.5
done
if [ -z "$ready" ]; then
  echo "dummy OpenMES receiver at http://{host}:8099/ never reported healthy." >&2
  echo "Start it first with start_dummy_openmes_receiver.sh (in its own terminal/background task)." >&2
  exit 1
fi
exec .venv/bin/python -u openmes_publisher.py --config ./openmes-publisher.json
"""


def wire_openmes(spec, openmes_dir, mode_key, topic, fields):
    om = spec.get("openmes") or {}
    host = spec.get("host_ip", "127.0.0.1")
    openmes_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OPENMES_ASSETS / "openmes_publisher.py", openmes_dir / "openmes_publisher.py")
    dummy = bool(om.get("dummy"))
    if dummy:
        shutil.copy2(OPENMES_ASSETS / "dummy_openmes_receiver.py", openmes_dir / "dummy_openmes_receiver.py")
        token = openmes_dir / "openmes_token"
        if not token.exists():
            token.write_text(secrets.token_hex(24) + "\n")  # throwaway, dummy receiver only
            token.chmod(stat.S_IRUSR)
        base_url, token_file = f"http://{host}:8099", "./openmes_token"
        wo, it = int(om.get("work_order_id", 1001)), int(om.get("issue_type_id", 7))
    else:
        for k in ("base_url", "token_file", "work_order_id", "issue_type_id", "source_id"):
            if om.get(k) in (None, ""):
                die(f"openmes.{k} is required for a real OpenMES "
                    "(set openmes.dummy: true only when the user asked to test without one)")
        base_url, token_file = om["base_url"], om["token_file"]
        wo, it = int(om["work_order_id"]), int(om["issue_type_id"])
    source_id = om.get("source_id") or f"{spec['slug']}-station-01"
    cfg = {
        "mode": mode_key, "source_id": source_id, "timestamp_format": fields["timestamp_format"],
        "defect_equals": 1, "sqlite_db": "openmes_events.db", "use_env_proxy": False,
        "openmes": {"base_url": base_url, "token_file": token_file, "work_order_id": wo,
                    "issue_type_id": it, "batch_step_id": om.get("batch_step_id")},
        "mqtt": {"host": "127.0.0.1", "port": 1883, "topic": topic,
                 "client_id": f"{source_id}-openmes", "tls": False},
        "fields": fields["fields"],
    }
    if fields.get("details"):
        cfg["details"] = fields["details"]
    (openmes_dir / "openmes-publisher.json").write_text(json.dumps(cfg, indent=2) + "\n")
    (openmes_dir / ".gitignore").write_text("openmes_token\nopenmes_events.db*\ndummy_openmes_issues.jsonl\n"
                                            "*.log\n.venv/\n")
    if dummy:
        for name, body in (("start_dummy_openmes_receiver.sh", START_DUMMY_RECEIVER.format(host=host)),
                           ("start_dummy_openmes_publisher.sh", START_DUMMY_PUBLISHER.format(host=host))):
            (openmes_dir / name).write_text(body)
            (openmes_dir / name).chmod(0o755)
    return {"dummy": dummy, "ui_url": f"http://{host}:8099/" if dummy else None,
            "dir": str(openmes_dir), "topic": topic, "base_url": base_url}


def write_readme(out, spec, mode, title):
    """Short stack README (the reference README links to docs that are not copied)."""
    target = {"multimodal": "make up", "vllm": "make up_vllm", "agentic": "make up_agentic"}[mode]
    dash = {"multimodal": "the base dashboard",
            "vllm": "the base and Explainability dashboards (/insights-ui/, Explain per result)",
            "agentic": "the base, Explainability (/insights-ui/) and Agentic (/agentic-ui/, Run Agentic Analysis) dashboards"}[mode]
    om = spec.get("openmes") or {}
    om_txt = ""
    if om.get("enabled"):
        om_txt = ("\n## OpenMES\n\nConfirmed fused defects (fused_decision == 1) are posted to OpenMES by "
                  "`openmes/openmes_publisher.py` (config: `openmes/openmes-publisher.json`).\n")
        if om.get("dummy"):
            om_txt += (f"\nThis stack uses the **dummy OpenMES receiver** for testing. After `{target}`,"
                       " run each in its own terminal (or your tool's attached background/async execution"
                       " -- never shell `&`/`nohup`/`disown`), stopping each with Ctrl-C (or your tool's"
                       " stop capability):\n\n"
                       "```bash\nopenmes/start_dummy_openmes_receiver.sh    # terminal 1; prints the alerts URL\n"
                       "openmes/start_dummy_openmes_publisher.sh   # terminal 2; waits for /health, then runs\n```\n\n"
                       f"Alerts page: http://{spec.get('host_ip', '127.0.0.1')}:8099/ (read-only, no login, dummy data).\n")
        else:
            om_txt += ("\n```bash\ncd openmes && python3 -m venv .venv && .venv/bin/pip install paho-mqtt requests\n"
                       ".venv/bin/python openmes_publisher.py --config ./openmes-publisher.json\n```\n")
    (out / "README.md").write_text(f"""# Multimodal {title}

Generated by the `manufacturing-app-recipe` skill (`{mode}` mode) from the
`industrial-edge-insights-multimodal` reference app. Camera and sensor
verdicts are fused (FUSION_MODE={spec.get('fusion_mode', 'OR')}) into one decision.

## Run

```bash
COMPOSE_BAKE=false make build   # builds the simulator, fusion-analytics{' and UI' if mode != 'multimodal' else ''} images
{target}
make status
make down
```

Open `https://<HOST_IP>:<GRAFANA_PORT>` (credentials: `VISUALIZER_GRAFANA_USER` /
`VISUALIZER_GRAFANA_PASSWORD` in `.env`) for {dash}.
{om_txt}""")


# --------------------------------------------------------------------------- modes
def scaffold_multimodal(spec, args):
    mode, obj, slug = spec["mode"], spec["object"], spec["slug"]
    ref = Path(need(spec, "reference_dir")).resolve()
    # Keep the pre-resolve Path for the --force symlink check: .resolve()
    # follows symlinks, so checking is_symlink() on the *resolved* path can
    # never be true even when out_dir itself is a symlink, silently losing
    # that safety check. out_dir_raw preserves the information resolve()
    # would otherwise discard; out itself stays resolved for every other use.
    out_dir_raw = Path(need(spec, "out_dir"))
    out = out_dir_raw.resolve()
    title = need(spec, "title")
    if not (ref / "docker-compose.yml").exists() or not (ref / "fusion-analytics").exists():
        die(f"{ref} is not an industrial-edge-insights-multimodal checkout")
    reuse = bool(spec.get("reuse_reference_assets"))
    sensor, vision = spec.get("sensor") or {}, spec.get("vision") or {}
    vlm, llm = spec.get("vlm") or {}, spec.get("llm") or {}
    live = spec.get("input_type", "simulator") in ("rtsp", "device", "live")
    rtsp_url = vision.get("rtsp_url")
    if live:
        if not (rtsp_url and re.fullmatch(r"rtsp://[^\s\"\\]+", rtsp_url)):
            die("vision.rtsp_url (rtsp://...) is required when input_type is rtsp/device/live")
    elif not (spec.get("simulation_data_dir") or reuse):
        die("simulation_data_dir is required (paired <name>.avi + <name>.csv), or reuse_reference_assets: true, "
            "or input_type: rtsp with vision.rtsp_url for live sources")
    if not (vision.get("model_dir") or reuse):
        die("vision.model_dir is required (folder with the OpenVINO .xml/.bin), or reuse_reference_assets: true")
    if mode in ("vllm", "agentic") and not vlm.get("model_dir"):
        die("vlm.model_dir is required for vllm/agentic (Hugging Face VLM folder); never invent one")
    fallback = mode == "agentic" and llm.get("mode", "llm") == "fallback"
    if mode == "agentic" and not fallback and \
            not (llm.get("model_name") and (llm.get("converted_dir") or llm.get("download"))):
        die("llm.model_name plus llm.converted_dir (or llm.download: true) is required for agentic "
            "unless llm.mode: fallback")
    if mode == "agentic" and llm.get("converted_dir") and not fallback:
        cd = Path(llm["converted_dir"])
        if not (list(cd.glob("*.xml")) and list(cd.glob("*.bin"))):
            die(f"llm.converted_dir {cd} has no OpenVINO .xml/.bin; remove it and use llm.download: true")

    udf = sensor.get("udf_name") or f"{obj}_anomaly_detector"
    meas = sensor.get("measurement") or f"{slug}-sensor-data"
    vision_model = vision.get("model_name") or ("weld-defect-classification-f16-ViT-Tiny" if reuse
                                                else f"{slug}-classifier")
    obj_upper = re.sub(r"[^A-Z0-9]", "_", obj.upper())
    use_case = spec.get("use_case_id") or f"{slug}-monitoring"
    words = obj.replace("_", " ")
    rename = {
        "ia-weld-data-simulator": f"ia-{slug}-simulator",
        "weld-data-simulator": f"{slug}-simulator",
        "WELD_SIMULATOR_IMAGE": f"{obj_upper}_SIMULATOR_IMAGE",
        "weld_anomaly_detector": udf,
        "vision_weld_defect_classification": f"vision_{obj}_classification",
        "ts_weld_anomaly_detection": f"ts_{obj}_anomaly_detection",
        "alerts/weld_defect_detection": f"alerts/{obj}",
        "weld-sensor-anomaly-data": f"{meas}-anomaly-data",
        "weld-sensor-data": meas,
        "vision-weld-classification-results": f"vision-{slug}-classification-results",
        "weld-defect-classification-f16-ViT-Tiny": vision_model,
        "weld-defect-classification": f"{slug}-classification",
        "weld_defect_classification": f"{obj}_classification",
        "weld_defect_detection": f"{obj}_detection",
        "weld-quality-monitoring": use_case,
        "Multimodal Weld Defect Detection": f"Multimodal {title}",
        "samplestream": f"{slug}-stream",
        '"welding"': f'"{obj}"',
        "weld-data": f"{slug}-data",
        "weld anomaly detection": f"{words} anomaly detection",
        "vision weld classification": f"vision {words} classification",
        "Weld Data Simulator": f"{title} simulator",
        "welding quality monitoring": f"{words} monitoring",
    }
    skip = set(COMMON_EXCLUDES) | ({"tests"} if not spec.get("generate_tests") else set())
    prune = list(MODE_PRUNE[mode]) + (["docker-compose-mcp.yml", "mcp-server"]
                                      if mode == "agentic" and not spec.get("mcp") else [])
    if args.dry_run:
        print(json.dumps({"copy": f"{ref} -> {out}", "mode": mode, "pruned": prune, "renames": rename}, indent=2))
        return
    if out.exists():
        if not args.force:
            die(f"{out} exists (use --force to replace it)")
        validate_removal_target(out_dir_raw, protect=[ref, SKILL_DIR])
        shutil.rmtree(out)

    def ignore(d, names):
        rel = Path(d).relative_to(ref)
        drop = []
        for n in names:
            relp = (rel / n).as_posix()
            if n in skip or relp in prune or relp in DATA_PATHS or n.endswith((".tar", ".pyc")):
                drop.append(n)
        return drop
    shutil.copytree(ref, out, ignore=ignore, symlinks=True)
    if (out / ".env").exists():
        blank_env_secrets(out / ".env")
    prune_makefile(out, prune, fallback, bool(llm.get("converted_dir")))

    # data and models (old names; the rename pass below fixes folder names)
    if live:
        make_live(out, rtsp_url)
    else:
        link_or_copy(spec.get("simulation_data_dir") or ref / "weld-data-simulator/simulation-data",
                     out / "weld-data-simulator/simulation-data")
    dl_models = out / "configs/dlstreamer-pipeline-server/models"
    link_or_copy(vision.get("model_dir") or
                 ref / "configs/dlstreamer-pipeline-server/models/weld-defect-classification-f16-ViT-Tiny",
                 dl_models / "weld-defect-classification-f16-ViT-Tiny")
    normalize_ir_names(dl_models / "weld-defect-classification-f16-ViT-Tiny")
    ts_models = out / "configs/time-series-analytics-microservice/models"
    ts_models.mkdir(parents=True, exist_ok=True)
    if sensor.get("model_files"):
        for f in sensor["model_files"]:
            n = Path(f).name
            n = udf + ("_labels.pkl" if n.endswith("_labels.pkl") else "".join(Path(f).suffixes))
            link_or_copy(f, ts_models / n)
    elif reuse:
        for f in (ref / "configs/time-series-analytics-microservice/models").iterdir():
            link_or_copy(f, ts_models / f.name.replace("weld_anomaly_detector", udf))
    if mode in ("vllm", "agentic"):
        link_or_copy(vlm["model_dir"], out / "configs/vllm/huggingface" / Path(vlm["model_dir"]).name)
        ad = out / "configs/vllm/models"
        if vlm.get("adapter_dir"):
            link_or_copy(vlm["adapter_dir"], ad / Path(vlm["adapter_dir"]).name)
        else:
            ad.mkdir(parents=True, exist_ok=True)
            (ad / "NO_ADAPTER.txt").write_text("No LoRA adapter: vllm-server serves the base model.\n")
    if mode == "agentic" and llm.get("converted_dir") and not fallback:
        dev, fmt = llm.get("device", "CPU").lower(), llm.get("weight_format", "int4").lower()
        link_or_copy(llm["converted_dir"], out / "configs/agentic/models/llm_model_agentic/openvino_models"
                     / dev / fmt / llm["model_name"])

    changed = apply_renames(out, rename, DATA_PATHS)

    # known fixes
    mp = write_model_proc(dl_models / vision_model)
    if mp:
        add_model_proc_to_pipeline(out / "configs/dlstreamer-pipeline-server",
                                   f"/home/pipeline-server/resources/models/{vision_model}")
    fix_healthchecks([out / f for f in ("docker-compose.yml", "docker-compose-vllm.yml",
                                         "docker-compose-agentic.yml", "docker-compose-mcp.yml")])
    patch_text(out / "fusion-analytics/fusion.py",
               '                    json_body[0]["fields"]["time"] = json_body[0]["time"]\n',
               '                    json_body[0]["fields"]["time"] = json_body[0]["time"]\n'
               '                    # fused label in the MQTT payload (InfluxDB keeps it as a tag)\n'
               '                    json_body[0]["fields"]["fusion_classification"] = '
               'json_body[0]["tags"]["fusion_classification"]\n', required=False)
    if mode in ("vllm", "agentic") and not vlm.get("adapter_dir"):
        vc = out / "docker-compose-vllm.yml"
        vc.write_text(re.sub(r"\n\s*- --enable-lora\n\s*- --lora-modules\n\s*- \$\{VLLM_ADAPTER_NAME\}=[^\n]*",
                             "", vc.read_text()))

    # .env
    host = spec.get("host_ip", "127.0.0.1")
    vals = {
        "COMPOSE_PROJECT_NAME": slug, "HOST_IP": host,
        "FUSION_MODE": spec.get("fusion_mode", "OR"), "TOLERANCE_NS": spec.get("tolerance_ns", "50e6"),
        f"{obj_upper}_SIMULATOR_IMAGE": f"{slug}-simulator",
        "FUSION_MODULE_IMAGE": f"{slug}-fusion-analytics",
        "DEPS_IMAGE_SUFFIX": spec.get("deps_image_suffix", STABLE_DEPS_TAG),
        "AGENTIC_IMAGE_SUFFIX": spec.get("agentic_image_suffix", STABLE_DEPS_TAG),
    }
    if mode in ("vllm", "agentic"):
        served = vlm.get("served_name") or Path(vlm["model_dir"]).name
        vals.update({"MULTIMODAL_AGENTIC_UI_IMAGE": f"{slug}-ui",
                     "VLLM_MODEL_DIR": f"huggingface/{Path(vlm['model_dir']).name}",
                     "VLLM_SERVED_MODEL_NAME": served})
        if vlm.get("adapter_dir"):
            vals["VLLM_ADAPTER_DIR"] = f"lora-adapters/{Path(vlm['adapter_dir']).name}/"
            vals["VLLM_ADAPTER_NAME"] = vlm.get("adapter_name") or Path(vlm["adapter_dir"]).name
        else:
            vals["VLLM_ADAPTER_NAME"] = served
            vals["VLLM_ADAPTER_DIR"] = ""
    if mode == "agentic":
        vals.update({"LLM_MODEL_NAME": llm.get("model_name") or "fallback-no-llm", "LLM_DEVICE": llm.get("device", "CPU"),
                     "LLM_WEIGHT_FORMAT": llm.get("weight_format", "int4"), "LLM_MODE": llm.get("mode", "llm")})
    vals.update({k: str(v) for k, v in (spec.get("env") or {}).items()})
    env = out / ".env"
    set_env(env, vals)
    generated = fill_secrets(env, obj)
    gi = out / ".gitignore"
    gi.write_text((gi.read_text() if gi.exists() else "") + "\n.env\nnginx-cert.pem\n")

    write_readme(out, spec, mode, title)

    om = None
    if (spec.get("openmes") or {}).get("enabled"):
        patch_text(out / "docker-compose.yml", "    container_name: ia-mqtt-broker\n",
                   "    container_name: ia-mqtt-broker\n"
                   "    # loopback only, for the host-side OpenMES publisher (anonymous broker; never 0.0.0.0)\n"
                   "    ports:\n    - \"127.0.0.1:1883:1883\"\n")
        om = wire_openmes(spec, out / "openmes", "multimodal", "fusion/anomaly_detection_results", {
            "timestamp_format": "iso8601",
            "fields": {"defect": "/fused_decision", "label": "/fusion_classification", "timestamp": "/time"},
            "details": {"mode": "/mode", "vision_classification": "/vision_classification",
                        "timeseries_classification": "/timeseries_classification",
                        "fusion_confidence": "/fusion_confidence"}})

    write_meta(out, {
        "mode": mode, "slug": slug, "object": obj, "stack_dir": str(out), "host_ip": host,
        "compose_project": slug,
        "topics": {"vision": f"vision_{obj}_classification", "sensor_processed": f"ts_{obj}_anomaly_detection",
                   "sensor_alert": f"alerts/{obj}", "fusion": "fusion/anomaly_detection_results",
                   "sensor_raw": f"{slug}-data"},
        "measurements": {"vision": f"vision-{slug}-classification-results", "sensor": meas,
                         "sensor_anomaly": f"{meas}-anomaly-data", "fusion": "fusion_result"},
        "https_paths": ["/", f"/{slug}-stream/"]
        + (["/insights-ui/", "/insights-ui/api/vllm/health"] if mode in ("vllm", "agentic") else [])
        + (["/agentic-ui/", "/api/v1/capabilities"] if mode == "agentic" else []),
        "openmes": om})
    report(out, spec, changed, generated, mp, om,
           leftovers(out, [r"weld", r"samplestream"],
                     DATA_PATHS | {"openmes", f"{slug}-simulator/simulation-data"}))


def scaffold_ts(spec, args):
    obj, slug = spec["object"], spec["slug"]
    repo = Path(need(spec, "ts_repo_dir")).resolve()
    tmpl = validate_path_component(spec.get("template_app", "wind-turbine-anomaly-detection"), "template_app")
    src = repo / "apps" / tmpl
    app = validate_path_component(spec.get("app_name") or slug, "app_name")
    dst = repo / "apps" / app
    if not (repo / "Makefile").exists() or not src.exists():
        die(f"{repo} is not an industrial-edge-insights-time-series checkout with apps/{tmpl}")
    csv = need(spec, "simulation_csv")
    sensor = spec.get("sensor") or {}
    udf = sensor.get("udf_name") or f"{obj}_anomaly_detector"
    meas = sensor.get("measurement") or f"{slug}-data"
    alert_channel = spec.get("alert_channel", "mqtt")
    if alert_channel not in ("mqtt", "opcua"):
        die("alert_channel must be mqtt or opcua")
    if (spec.get("openmes") or {}).get("enabled") and alert_channel != "mqtt":
        die("OpenMES for ts requires alert_channel: mqtt (OPC-UA alerts cannot feed the publisher)")
    rename = {
        "wind-turbine-anomaly-detection": app,
        "windturbine_anomaly_detector": udf,
        "wind-turbine-anomaly-data": re.sub(r"-data$", "", meas) + "-anomaly-data",
        "wind-turbine-data": meas,
        "wind-simulation-data": f"{app.split('-')[0]}-simulation-data",  # publisher rule: first token of SAMPLE_APP
        "alerts/wind_turbine": f"alerts/{obj}",
    }
    if args.dry_run:
        print(json.dumps({"copy": f"{src} -> {dst}", "renames": rename}, indent=2))
        return
    if dst.exists():
        if not args.force:
            die(f"{dst} exists (use --force to replace it)")
        validate_removal_target(dst, protect=[repo, SKILL_DIR])
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("training", "models", "*.tar", "*.csv",
                                                            "__pycache__", "openmes"))
    shutil.copy2(csv, dst / "simulation-data" / f"{tmpl}.csv")
    if sensor.get("model_files"):
        md = dst / "time-series-analytics-config/models"
        md.mkdir(exist_ok=True)
        for f in sensor["model_files"]:
            n = Path(f).name
            link_or_copy(f, md / (udf + ("_labels.pkl" if n.endswith("_labels.pkl") else "".join(Path(f).suffixes))))
    changed = apply_renames(dst, rename, {"time-series-analytics-config/models", "simulation-data"})
    mk = repo / "Makefile"
    t = mk.read_text()
    m = re.search(r"^SAMPLE_APP_LIST := (.*)$", t, re.M)
    if m and app not in m.group(1).split():
        mk.write_text(t[:m.end()] + f" {app}" + t[m.end():])
    om = None
    if (spec.get("openmes") or {}).get("enabled"):
        # The ts Makefile builds COMPOSE_FILES explicitly, so Compose never auto-loads an override:
        # use a dedicated file and include it in the Makefile's file list.
        (repo / OPENMES_OVERRIDE).write_text(
            "# loopback only, for the host-side OpenMES publisher (anonymous broker; never 0.0.0.0)\n"
            "services:\n  ia-mqtt-broker:\n    ports:\n      - \"127.0.0.1:1883:1883\"\n")
        t = mk.read_text()
        if OPENMES_OVERRIDE not in t:
            anchor = "COMPOSE_FILES = -f $(DOCKER_COMPOSE_FILE)\n"
            if anchor not in t:
                die(f"cannot add {OPENMES_OVERRIDE} to the Makefile COMPOSE_FILES list; add it manually")
            mk.write_text(t.replace(anchor, anchor + f"ifneq ($(wildcard ./{OPENMES_OVERRIDE}),)\n"
                                    f"COMPOSE_FILES += -f ./{OPENMES_OVERRIDE}\nendif\n", 1))
        # The publisher needs JSON alerts with top-level anomaly_status and time.
        for tick in (dst / "time-series-analytics-config/tick_scripts").glob("*.tick"):
            tt = tick.read_text()
            new = re.sub(r"\.message\('[^\n]*'\)",
                         lambda _m: ".message('{\"anomaly_status\": {{ index .Fields \"anomaly_status\" }}, "
                                    "\"time\": \"{{ .Time }}\"}')", tt)
            if new != tt:
                tick.write_text(new)
        om = wire_openmes(spec, dst / "openmes", "ts", f"alerts/{obj}",
                          {"timestamp_format": "kapacitor",
                           "fields": {"defect": "/anomaly_status", "timestamp": "/time"}})
    write_meta(dst, {
        "mode": "ts", "slug": slug, "object": obj, "stack_dir": str(repo), "app": app,
        "host_ip": spec.get("host_ip", "127.0.0.1"), "compose_project": None,
        "topics": {"sensor_alert": f"alerts/{obj}"} if alert_channel == "mqtt" else {},
        "alert_channel": alert_channel,
        "measurements": {"sensor": meas, "sensor_anomaly": re.sub(r"-data$", "", meas) + "-anomaly-data"},
        "https_paths": ["/", "/ts-api/health"], "openmes": om})
    report(dst, spec, changed, [], None, om,
           leftovers(dst, [r"\bwind(?!ows?\b|ow)", r"windturbine", r"turbine", r"grid_active_power"],
                     {"simulation-data", "openmes"}))


def write_meta(root, meta):
    """Names used by verify_stack.py (no secrets)."""
    (root / ".scaffold.json").write_text(json.dumps(meta, indent=2) + "\n")


def report(root, spec, changed, generated, model_proc, om, hits):
    print(f"\nScaffolded {spec['mode']} '{spec['slug']}' at {root}")
    print(f"  files rewritten by the rename map: {changed}")
    if generated:
        print(f"  secrets generated in .env (values not shown): {', '.join(generated)}")
    if model_proc:
        print(f"  vision model-proc written: {model_proc}")
    if om:
        print(f"  OpenMES publisher: {om['dir']}  (topic {om['topic']} -> {om['base_url']})")
        if om["dummy"]:
            print(f"  DUMMY OpenMES alerts page - give this URL to the user: {om['ui_url']}")
            print(f"    after the stack is up, start {om['dir']}/start_dummy_openmes_receiver.sh"
                  " (own terminal/background task), wait for /health, then start"
                  f" {om['dir']}/start_dummy_openmes_publisher.sh; stop each with Ctrl-C"
                  " (or your tool's stop capability)")
    print(f"\nLines still mentioning the old vertical: {len(hits)}"
          " (edit these: UDF logic, labels, prompts, sensor fields, dashboard queries)")
    for f, n, line in hits:
        print(f"  {f}:{n}: {line}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="vertical spec (.yaml or .json)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--force", action="store_true", help="replace an existing target directory")
    args = ap.parse_args()
    spec = load_spec(args.spec)
    spec["mode"] = need(spec, "mode")
    if spec["mode"] not in ("ts", "multimodal", "vllm", "agentic"):
        die("mode must be ts, multimodal, vllm or agentic (vision is demo/PoC only, delegated to other skills)")
    spec["object"] = re.sub(r"[^a-z0-9_]", "_", need(spec, "object").lower())
    spec["slug"] = spec.get("slug") or slugify(spec["object"])
    spec["host_ip"] = validate_host(spec.get("host_ip", "127.0.0.1"))
    (scaffold_ts if spec["mode"] == "ts" else scaffold_multimodal)(spec, args)


if __name__ == "__main__":
    main()
