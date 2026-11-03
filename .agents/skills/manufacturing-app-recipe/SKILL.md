---
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
name: manufacturing-app-recipe
description: >-
  Stand up a complete, ready-to-run manufacturing analytics stack on Intel
  hardware with one Docker Compose command, across five deployment shapes:
  vision-only inspection, sensor-only (time-series) anomaly detection,
  vision+sensor multimodal, vision+sensor multimodal with VLM narrative explanation,
  and the same with full agentic orchestration — covering any
  manufacturing-quality vertical (weld defects, CNC tool wear, PCB
  inspection, predictive maintenance, wind-turbine/pump/HVAC monitoring)
  with no glue code. See "When to use this skill" and "Deployment modes" for the full
  component list, trigger conditions, and boundaries.
license: Apache-2.0
compatibility: >-
  Docker + Docker Compose v2 on an Intel CPU host (optional GPU/NPU via
  `video`/`render` groups); outbound access to Docker Hub, ghcr.io, and
  Hugging Face for model/dataset downloads. Frees ports 80/443 (or
  `${GRAFANA_PORT}`), the Coturn UDP port (`multimodal`/`vllm`/`agentic`),
  and `${OPCUA_SERVER_PORT_MAPPING}` (`ts`, OPC-UA). Tested against the
  manufacturing-ai-suite Time Series / Multimodal references, v2026.2.0.
allowed-tools: bash, docker, python, curl, read, write, fetch
---

# Manufacturing App Recipe — vision / time-series / multimodal / VLM / agentic stacks on Intel hardware

Build a manufacturing quality/monitoring stack on Intel hardware with Docker
Compose, in one of **five deployment modes** (Question 0 picks the shape):

| Mode | Shape | Components added on top of the previous mode |
|---|---|---|
| `vision` | lightweight single vision pipeline (demo/PoC only — no full stack) | DLSPS or a custom GStreamer pipeline |
| `ts` | sensor-only anomaly detection | Telegraf/InfluxDB + Time Series Analytics Microservice (Kapacitor UDF) + Grafana, as a new `apps/<name>/` folder (or a bare UDF in demo mode) |
| `multimodal` | vision + sensor, one fused verdict | DLSPS + the `ts` stack + Fusion Analytics correlator, as a new flat stack directory |
| `vllm` | `multimodal` + on-demand, image-grounded explanation | `vllm-server` (`intel/vllm`, a vision-language model + optional LoRA, Intel GPU) + `ui-service` (`/insights-ui/` **Explain**) + an Explainability dashboard |
| `agentic` | `vllm` + agent orchestration (additive) | everything in `vllm`, plus `apm-agent` (`agent-quality-handler`), `apm-llm` (OVMS agent LLM), `model-download`, `apm-metrics` + Prometheus, `/agentic-ui/` (**Run Agentic Analysis**) and an Agentic dashboard |

`vllm` and `agentic` **always include the sensor path** — there is no
vision-only or sensor-only VLM/agentic mode; both require the Fusion
Analytics correlator from `multimodal` as their foundation, since the thing being
explained is a **fused** verdict. Follows the open-edge-platform
[Industrial Edge Insights — Time Series](https://github.com/open-edge-platform/manufacturing-ai-suite/tree/main/industrial-edge-insights-time-series)
reference (wind-turbine-anomaly-detection sample, `ts` mode) and
[Industrial Edge Insights — Multimodal](https://github.com/open-edge-platform/manufacturing-ai-suite/tree/main/industrial-edge-insights-multimodal)
reference (weld-defect-detection sample, `multimodal`/`vllm`/`agentic` modes).

## When to use this skill

**Use when** building any manufacturing quality-inspection or sensor-monitoring
pipeline that is one of:

- **`vision`** — a quick local demo/PoC proving a vision model runs on Intel
  hardware, no dashboard/alerting stack.
- **`ts`** — a full deployable sensor-only app (simulator or real OPC-UA/MQTT
  ingest, Kapacitor UDF, MQTT/OPC-UA alerting, Grafana dashboard), or a bare
  UDF prototype against an already-running microservice.
- **`multimodal`** — a camera feed correlated with a sensor stream into **one**
  fused anomaly verdict (AND/OR logic) — weld defect detection, CNC
  tool-wear/vibration correlation, PCB visual + electrical test multimodal.
- **`vllm`** — the `multimodal` stack plus a vision-language model the operator
  asks, per fused result, to explain the stored frame and sensor readings
  (the reference `make up_vllm`).
- **`agentic`** — the `vllm` stack plus agent orchestration (policy →
  analysis → evidence → ticketing) over a chosen time window, started from the agentic
  UI (the reference `make up_agentic`).

**Not for:** vision-only pipelines that need a **full** end-to-end
dashboard/alerting stack (use `metro-ai-app-recipe` instead — `vision` mode
here is demo/PoC only), non-Intel or cloud-only deployments, or
training/exporting models.

## Supported verticals & use-cases

| Vertical | Vision signal | Sensor signal | Typical mode |
|---|---|---|---|
| Welding / joining | weld-seam defect classification | pressure, gas flow, current | `multimodal`/`vllm`/`agentic` |
| Machining / CNC | tool/surface defect detection | vibration, spindle current | `multimodal`/`vllm`/`agentic` |
| Electronics / PCB | solder-joint/component defect detection | in-circuit test current/voltage | `multimodal`/`vllm`/`agentic` |
| Predictive maintenance | thermal/visual anomaly detection | vibration, temperature, RPM | `multimodal`/`vllm`/`agentic` or `ts`-only |
| Renewable energy | — | wind speed, grid active power | `ts` |
| Rotating machinery | — | vibration, RPM, current | `ts` |
| HVAC / facilities | — | temperature, energy draw, airflow | `ts` |
| Process / utilities | — | pressure, flow, level | `ts` |
| Camera-only inspection, quick PoC | any OpenVINO IR / ONNX classifier or detector | — | `vision` |
| Custom | any OpenVINO IR / ONNX classifier or detector | any scikit-learn model or rule via UDF | any mode |

The invoking prompt maps its vertical to concrete `{{OBJECT}}`,
`{{APP_NAME}}`/`{{STACK_DIR}}`, `{{DEFAULT_MODEL}}`, `{{SENSOR_UDF_NAME}}`,
`{{DASHBOARD_SLUG}}`/`{{DASHBOARD_TITLE}}` — nothing else changes.

## How to use this skill — fast path (default for `ts`/`multimodal`/`vllm`/`agentic`)

Copy the reference app with the scaffold script and change only what is
specific to this use case. Never hand-write the Compose files, Makefile,
nginx, Fusion Analytics or UI service. They are about 99% generic, and
rewriting them costs most of the time and tokens.

1. Ask **Question 0 (deployment mode)** first — `vision` \| `ts` \| `multimodal` \|
   `vllm` \| `agentic`. No default; always confirm explicitly.
2. Ask the mode's questions (below) in ONE batched message (defaults in
   brackets); accept `go`/`defaults`/empty. Run parameter validation.
3. Write the spec: copy [`assets/vertical.example.yaml`](assets/vertical.example.yaml)
   and fill in only the user's answers (mode, names, paths, fusion,
   models, OpenMES).
4. `python3 scripts/scaffold_stack.py --spec <spec> --dry-run`, then run it without
   `--dry-run`. It copies the reference, prunes by mode, renames, links models
   and data, applies the known fixes, writes `.env` with generated secrets, and
   wires OpenMES. It then prints the **remaining lines that still mention the old
   vertical**.
   - **If the automated copy cannot run** (permission denied on the reference
     checkout or the target directory, a sandboxed/restricted environment, or
     any other access failure): do not bypass the restriction (no `sudo`,
     no alternate elevated path, no invented workaround) and do not report the
     stack as scaffolded unless the files actually exist on disk. Instead,
     inspect the existing reference folder's structure (`ls -R`/directory
     listing of `reference_dir` or `ts_repo_dir`), recreate the **same**
     layout by hand under `{{STACK_DIR}}`/`apps/{{APP_NAME}}`, and adapt only
     the vertical-specific lines per the copy/leave-behind tables in
     [`references/INSTALL.md`](references/INSTALL.md) — never invent a
     different file layout or architecture.
5. Edit **only** those lines (sensor UDF logic and fields, TICKscript fields,
   label normalisation, dashboard queries, agent/UI prompts). Load the
   reference file for a step only when you need it: `TIMESERIES.md`/
   `ANALYTICS.md` for the UDF, `UI_SERVICE.md` for the UI edits, `AGENTIC.md`
   for the use-case files. Delegate the UDF pattern to `time-series-analytics-user`
   only if no existing UDF can be adapted.
6. Build and start with the mode's Makefile target: `COMPOSE_BAKE=false make build`,
   then `make up` / `up_vllm` / `up_agentic`; for `ts`,
   `make up_<transport>_ingestion app=<app>` in the time-series checkout.
   `make check_env_variables` is step 0 of every `up*` target.
7. If OpenMES with the dummy receiver is enabled, start
   `openmes/start_dummy_openmes_receiver.sh`, wait for `/health`, then start
   `openmes/start_dummy_openmes_publisher.sh` (it waits for `/health` itself
   before running). Use your own tool's attached background/async execution
   for each if you have one (stop both explicitly when done); otherwise run
   each in its own terminal and stop with Ctrl-C. Never `&`/`nohup`/`disown`
   a plain shell job and call it stopped later by searching for its PID —
   that job outlives the shell that started it. Then run
   `python3 scripts/verify_stack.py <stack or app dir>`
   and quote its PASS lines in the final summary. Re-run only the failed checks
   after a fix. Do not poll with fixed sleeps.

`vision` mode stays a demo/PoC handled by the delegate skills (see
[`references/DEMO_POC.md`](references/DEMO_POC.md)). The full reference files
below are for unusual requests and for debugging, not for routine reading.

## Reference files (load on demand)

| File | Load for mode(s) | When authoring |
|---|---|---|
| [`references/DEMO_POC.md`](references/DEMO_POC.md) | `vision`, `ts` (demo sub-path) | lightweight single-component path — no full stack |
| [`references/PIPELINE.md`](references/PIPELINE.md) | `vision`, `multimodal`, `vllm`, `agentic` | DLSPS `config.json` (RTSP source, classification/detection, S3 frame write, WebRTC, MQTT metadata), GPU/NPU variants |
| [`references/INGEST.md`](references/INGEST.md) | `ts` | OPC-UA/MQTT simulator choice, Telegraf wiring, real-device connection |
| [`references/APPS_CONVENTION.md`](references/APPS_CONVENTION.md) | `ts` | the `apps/<name>/` scaffold, Makefile `SAMPLE_APP_LIST` registration |
| [`references/ANALYTICS.md`](references/ANALYTICS.md) | `ts` | Time Series Analytics Microservice `config.json` variants (streaming/batch/OPC-UA-alert) for the standalone `apps/<name>/` shape |
| [`references/TIMESERIES.md`](references/TIMESERIES.md) | `multimodal`, `vllm`, `agentic` | Telegraf MQTT→InfluxDB ingestion + Time Series Analytics Microservice wiring inside the flat multimodal-stack shape (delegates UDF pattern choice to `time-series-analytics-user`) |
| [`references/FUSION.md`](references/FUSION.md) | `multimodal`, `vllm`, `agentic` | Fusion Analytics service (MQTT correlate-by-timestamp, AND/OR logic, InfluxDB write) — **always load for these three modes**, the core differentiator |
| [`references/VLM.md`](references/VLM.md) | `vllm`, `agentic` | `vllm-server` (VLM + optional LoRA), the `/insights-ui/` Explain flow, `VLLM_*` env, hardware gate, `up_vllm` — **always load for these two modes** |
| [`references/AGENTIC.md`](references/AGENTIC.md) | `agentic` only | the additive agent overlay (`apm-agent`, `apm-llm`, `model-download`, `apm-metrics`, Prometheus, optional MCP), the UI Run trigger, the storage-API contract, use-case files, `up_agentic` |
| [`references/UI_SERVICE.md`](references/UI_SERVICE.md) | `vllm`, `agentic` | copying and adapting the reference `ui-service`, its per-vertical edit list, the InfluxDB/S3 data contract, and the `_vlm`/`_agentic` dashboards — **always load for these two modes** |
| [`references/PROXY_UI.md`](references/PROXY_UI.md) | all production modes | `nginx.conf` proxy incl. `NGINX_PROFILE` routes (`/insights-ui/`, `/agentic-ui/`, metrics), the same-origin iframe rule, Grafana dashboard provisioning, Mosquitto, (multimodal+ family) SeaweedFS S3 |
| [`references/INSTALL.md`](references/INSTALL.md) | all production modes | file layout, `.env`, validation rules, `install.sh`/Makefile targets, image tags, copy/leave-behind + renaming rules, and completion criteria per mode |
| [`references/TESTS.md`](references/TESTS.md) | all production modes, only if `{{GENERATE_TESTS}}=yes` | `conftest.py`, per-mode assertion contracts |
| [`references/PARAMETERS.md`](references/PARAMETERS.md) | all | full `{{VAR}}` glossary — purpose, default, and applicable modes |
| [`scripts/scaffold_stack.py`](scripts/scaffold_stack.py), [`scripts/verify_stack.py`](scripts/verify_stack.py), [`assets/vertical.example.yaml`](assets/vertical.example.yaml) | `ts`, `multimodal`, `vllm`, `agentic` | the fast path: spec → copy-and-rename scaffold with known fixes and a leftover report → one-shot verification with compact evidence (run them, don't read them) |
| [`references/OPENMES.md`](references/OPENMES.md) | any mode, only if `{{OPENMES_ENABLED}}=yes` | optional OpenMES integration: API contract, `openmes_publisher.py` script wiring (from [`assets/openmes/`](assets/openmes/)), per-mode input topic, secrets, reliability, verification |

## Parameters (from invoking prompt)

The invoking prompt supplies concrete values for every `{{VAR}}` used below
(e.g. `{{OBJECT}}`, `{{STACK_DIR}}`/`{{APP_NAME}}`, `{{DEFAULT_MODEL}}`,
`{{SENSOR_UDF_NAME}}`, `{{FUSION_MODE}}`, `{{DASHBOARD_SLUG}}`). Full glossary
with purpose/defaults/applicable-modes in
[`references/PARAMETERS.md`](references/PARAMETERS.md) — load it before
asking Question 0 if any `{{VAR}}` meaning below is unclear.

## Questions (single batched prompt, per mode)

**Question 0 — Deployment mode** (no default, ask explicitly): `vision` \|
`ts` \| `multimodal` \| `vllm` \| `agentic` — see the *Deployment modes* table
above. Then ask ONLY the questions for the chosen mode:

### `vision` mode

0b. Demo sub-path: a DL Streamer/GStreamer pipeline (`dlstreamer-coding-agent`)
    or a REST-driven DLSPS instance (`dlsps-user`)? No default — the two
    produce unrelated artifacts.
1. Vision model [`{{DEFAULT_MODEL}}`] (also: `{{OTHER_MODELS}}`)
2. Vision device [CPU] (GPU, NPU, AUTO)
3. Video input [sample video] (or RTSP URL / `/dev/videoN` / local path)

Full guidance in [`references/DEMO_POC.md`](references/DEMO_POC.md) —
*Vision-only* section.

### `ts` mode

0b. Sub-mode [`production`]: `demo` (bare UDF, no scaffold — STOP and
    delegate entirely to `time-series-analytics-user`, skip questions below)
    or `production` (full `apps/<name>/` stack).

Production questions:

1. **Working directory** — the absolute path to an existing
   `industrial-edge-insights-time-series` checkout to add
   `apps/{{APP_NAME}}/` into (must already contain `docker-compose.yml` +
   `Makefile` + `apps/` at its root), or where to clone the reference repo
   fresh if none exists. Never guess a path or default to the current
   working directory.
2. App name [`{{APP_NAME}}`] — new `apps/<name>/` folder to create
3. Sensor pattern [pretrained model] (threshold, rate-of-change, rolling
   z-score, pretrained model — see `time-series-analytics-user`
   `references/patterns.md`) + `{{SENSOR_TAGS}}`
4. Ingestion transport [`opcua`] (or `mqtt`) — drives which simulator/Telegraf
   input plugin is used
5. Real device or simulator? [simulator with a sample CSV] (or a real
   OPC-UA server URL / MQTT broker to connect Telegraf to directly)
6. Alert channel [`mqtt`, `{{ALERT_TOPIC}}`] (or `opcua`) — **enable only one**
7. Dashboard title [`{{DASHBOARD_TITLE}}`]
8. Generate pytest tests in `tests/`? [`{{GENERATE_TESTS}}`, no default —
   ask explicitly] (yes/no) — skip the `tests/` folder entirely if no

### `multimodal` mode (and the shared base for `vllm`/`agentic`)

1. **Working directory** — the absolute parent path to create
   `{{STACK_DIR}}/` in. A **new, flat, standalone** stack directory, not a
   folder inside an existing repo checkout — confirm explicitly.
2. Vision model [`{{DEFAULT_MODEL}}`] (also: `{{OTHER_MODELS}}`) — classifier
   or detector
3. Vision device [CPU] (GPU, NPU, AUTO)
4. Video input [simulator sample video] (or RTSP URL / `/dev/videoN` / local
   path); sets DLSPS source
5. Sensor pattern [pretrained model] (threshold, rate-of-change, rolling
   z-score, pretrained model — see `time-series-analytics-user`
   `references/patterns.md`)
6. Sensor input [simulator sample CSV] (or MQTT/OPC UA live feed); sets
  Telegraf `TELEGRAF_INPUT_PLUGIN`. For the MQTT-publishing simulator or
  another MQTT source, set raw topic [`{{TS_RAW_TOPIC}}`, default
  `{{OBJECT}}/sensor/raw`] for simulator output
  and Telegraf input; set processed UDF output topic
  [`{{TS_PROCESSED_TOPIC}}`, default `{{OBJECT}}/sensor/processed`] for
  Fusion Analytics. These topics must be distinct.
7. Multimodal mode [`{{FUSION_MODE}}`, default `OR`] + `{{TOLERANCE_NS}}`
   [default `50e6`]
8. Alert channels [MQTT `{{SENSOR_ALERT_TOPIC}}` + `{{FUSION_TOPIC}}`]
9. Dashboard slug [`{{DASHBOARD_SLUG}}`]
10. Generate pytest tests in `tests/`? [`{{GENERATE_TESTS}}`, no default —
    ask explicitly] (yes/no) — skip the `tests/` folder entirely if no

### `vllm` mode

Ask the 10 `multimodal`-mode questions above, **plus**:

11. Vision-language model for `vllm-server` [`{{VLM_MODEL}}`, no default —
    a Hugging Face id the user names and downloads into
    `configs/vllm/huggingface/`; reference: `unsloth/Qwen3.5-2B`] + LoRA
    adapter [`{{VLM_ADAPTER_NAME}}`, default `none`; the reference weld
    adapter applies to weld only]. State the hardware gate up front:
    `vllm-server` needs an Intel GPU and is validated on Core Ultra Series 3
    with at least 32 GB RAM (`check_hardware`; `PLATFORM_CHECK=false` is for
    CI only). If the host can't run it, recommend `multimodal` instead.
12. UI title and vertical prompt [`{{UI_TITLE}}`, default
    `{{DASHBOARD_TITLE}}`]: the persona and report sections for the
    `ui-service` system prompt, and which `{{SENSOR_TAGS}}` (with units)
    Explain sends with the frame.

### `agentic` mode

Ask the 12 `vllm`-mode questions above, **plus**:

13. Agent LLM for `apm-llm` [`{{LLM_MODEL_NAME}}`, no default — an
    OpenVINO/HF id or an already-converted folder under
    `configs/agentic/models/llm_model_agentic/`] + `{{LLM_DEVICE}}` [`CPU`]
    + `{{LLM_WEIGHT_FORMAT}}` [`int4`], or `{{LLM_MODE}}=fallback` for
    rule-based agent output. This is a second model, separate from Q11.
14. Agent trigger [`{{AGENT_TRIGGER}}=ui`: the user clicks **Run Agentic
    Analysis** in the Agentic dashboard, as in the reference] or opt-in
    automatic runs (`size` + `{{BATCH_SIZE}}`, or `time` +
    `{{BATCH_INTERVAL_S}}`, both with `{{BATCH_MIN_INTERVAL_S}}`; see
    FUSION.md).
15. Defect taxonomy for the agent [`{{USE_CASE_ID}}`]: actionable vs
    non-actionable classes, priority tiers and thresholds, and the ticketing
    backend [`none`]. These become `agents.yaml`, `prompts/{{USE_CASE_ID}}.txt`
    and `policy_fallback.json`.
16. Include the MCP server overlay? [`{{AGENT_MCP}}=no`]. The metrics
    services (`apm-metrics` + Prometheus) are always included, because the
    agentic UI depends on them.

### All modes — optional OpenMES publishing (same batched message)

Opt-in; the default is **off**. Ask explicitly:

O1. Enable OpenMES defect publishing? [`{{OPENMES_ENABLED}}=no`] (yes/no).
    If `no`, skip O2–O7.
O2. OpenMES base URL [`{{OPENMES_BASE_URL}}`, no default].
O3. Path to the token file [`{{OPENMES_TOKEN_FILE}}`]. Ask for the **path
    only, never the token value in chat**.
O4. Work order ID [`{{OPENMES_WORK_ORDER_ID}}`] and issue type ID
    [`{{OPENMES_ISSUE_TYPE_ID}}`, which must be non-blocking].
O5. Optional batch step ID [`{{OPENMES_BATCH_STEP_ID}}`, default none].
O6. Source identifier [`{{OPENMES_SOURCE_ID}}`, e.g. the station or line
    name].
O7. Defect-reporting policy for this mode:
    - `vision`: the defect labels [`{{OPENMES_DEFECT_LABELS}}`] and the
      minimum confidence [`{{OPENMES_MIN_CONFIDENCE}}=0.8`];
    - `ts`/fused modes: confirm a flag value of `1` means defect.

Do not proceed with fabricated IDs, URLs or credentials. Every value must
come from the user, and the field mapping must be validated against one
real message before declaring success. The only exception: if the user
explicitly asks to test without a real OpenMES, use the dummy receiver
(`assets/openmes/dummy_openmes_receiver.py`) with its documented test IDs
and a locally generated throwaway token, and label the results as dummy.
See [`references/OPENMES.md`](references/OPENMES.md) → *Testing without a
real OpenMES*. Mode notes when enabled (full
details in [`references/OPENMES.md`](references/OPENMES.md)):

- **`vision`**: make sure a metadata stream exists for the publisher to
  consume. This requires the `dlsps-user` sub-path with an MQTT metadata
  destination.
- **`ts`**: requires MQTT alert output (`{{ALERT_CHANNEL}}=mqtt`). OPC-UA
  alerting cannot feed this publisher.
- **`multimodal`/`vllm`/`agentic`**: publish from `{{FUSION_TOPIC}}`
  only, never the per-modality topics, to avoid duplicate reports.
- OpenMES publishing failures must never block the inference, fusion or
  alerting pipelines.

## Parameter validation (enforce BEFORE install/`make up_*` runs)

Confirm the **working directory** (`{{STACK_DIR}}` or `{{TS_REPO_DIR}}`) is
where the user actually wants files created — never fall back to the current
working directory or a temp path. Reuse `make check_env_variables`/
`validate_host_ip` (all production modes) as step 0; reject on any failure.
Full validation rules tables (per mode) are in
[`references/INSTALL.md`](references/INSTALL.md).

## Reference architecture

- **`vision`** — single DLSPS/GStreamer pipeline, no dashboard. See
  [`references/DEMO_POC.md`](references/DEMO_POC.md).
- **`ts`** — sensor/simulator → Telegraf (OPC-UA or MQTT input) → InfluxDB
  (storage) + Time Series Analytics Microservice (Kapacitor UDF) →
  MQTT/OPC-UA alert → Grafana, behind an Nginx TLS proxy. See
  [`references/INGEST.md`](references/INGEST.md) /
  [`references/ANALYTICS.md`](references/ANALYTICS.md).
- **`multimodal`** — two paths meeting in Fusion Analytics: **vision**
  DLSPS→MQTT, and **sensor** simulator/device→MQTT→Telegraf→InfluxDB +
  MQTT→Time Series Analytics Microservice (Kapacitor UDF)→MQTT; Fusion
  Analytics correlates both MQTT streams by timestamp and writes the fused
  verdict to InfluxDB + MQTT. See [`references/FUSION.md`](references/FUSION.md).
- **`vllm`** — `multimodal`, plus `vllm-server` and `ui-service`. The
  Explainability dashboard embeds `/insights-ui/`. **Explain** on a fused
  row sends the stored S3 frame and the matching sensor row to the VLM. See
  [`references/VLM.md`](references/VLM.md) and
  [`references/UI_SERVICE.md`](references/UI_SERVICE.md).
- **`agentic`** — `vllm`, plus `apm-agent` (LangGraph policy/analysis/
  ticketing agents) calling `apm-llm` (OVMS), with `model-download`,
  `apm-metrics` and Prometheus. The Agentic dashboard embeds `/agentic-ui/`.
  **Run Agentic Analysis** publishes `apm/batch-complete` for a time window,
  and the agent reads that window from Fusion Analytics' storage API. All UIs
  are same-origin iframes behind nginx. See
  [`references/AGENTIC.md`](references/AGENTIC.md).

## Images — pin to the latest available tag (never `:latest`)

Resolve each image to the **newest published stable tag on Docker Hub**
(query the repo's `tags` API with `ordering=last_updated`); never pin
`*-weekly` pre-releases. Full per-component image list in
[`references/INSTALL.md`](references/INSTALL.md) → *Image tags*.

## Layout — per mode

- **`vision`** — no fixed layout; whatever `dlstreamer-coding-agent`/
  `dlsps-user` produces for a single pipeline.
- **`ts`** — a new `apps/{{APP_NAME}}/` folder inside the existing generic
  Time Series AI Stack repo (shared `docker-compose.yml`/`Makefile`/`configs/`
  at the repo root): `simulation-data/`, `telegraf-config/`,
  `time-series-analytics-config/{config.json,udfs/,tick_scripts/,models/}`,
  `grafana-dashboard.json`, `training/`. Full annotated tree in
  [`references/APPS_CONVENTION.md`](references/APPS_CONVENTION.md).
- **`multimodal`/`vllm`/`agentic`** — a flat, new `{{STACK_DIR}}/`: `README.md`,
  `docker-compose.yml`, `.env`, `install.sh`, `Makefile`, `configs/`,
  `fusion-analytics/`, a data simulator/adapter, plus (for `vllm`/`agentic`)
  `docker-compose-vllm.yml`, `ui-service/`, `configs/vllm/` and the `_vlm`
  dashboard, plus (for `agentic`) `docker-compose-agentic.yml`,
  `configs/agentic/` and the `_agentic` dashboard — the same files as the
  reference, adapted per vertical — and `tests/` only if
  `{{GENERATE_TESTS}}=yes`. Full
  annotated tree in
  [`references/INSTALL.md`](references/INSTALL.md). Name the data simulator
  directory for **this** vertical (e.g. `{{STACK_DIR}}-simulator/`) — never
  keep the reference's `weld-data-simulator/` name in a stack for a
  different vertical; see `references/INSTALL.md` → *Reference
  implementation* for the full renaming/pruning rule.

## Template variable substitution

Every `{{VAR}}` MUST be substituted with its concrete value BEFORE writing
the file — a literal `{{...}}` left in `nginx.conf`, `config.json`,
`Telegraf.conf`, `fusion.py`, a dashboard JSON, or a test file is a syntax
error.

## Execution guardrails

- Hard timeouts: model dl 300 s; simulator dataset dl 120 s; `compose pull`
  300 s; `compose up -d` 120 s + 180 s healthy; each pytest 60 s (only when
  `{{GENERATE_TESTS}}=yes`). Exceptions: `vllm-server` may take about 10 min
  to load the VLM (allow 15 min); `make download_model` for the agent LLM
  polls for up to 50 min; one CPU agent run takes several minutes.
- **Secrets:** the stack's `.env` holds credentials that `install.sh` generates locally. Keep them out of chat, logs and summaries; refer to them by variable name. Never ask the user for secret values, and never read credential files outside the stack. Rules in [`references/INSTALL.md`](references/INSTALL.md) → *Secrets in `.env`*.
- Max 2 retries per step, then STOP and print last 30 log lines from the
  failing container. Never loop.
- Before `compose up` (`multimodal`/`vllm`/`agentic`): confirm the Nginx TLS port
  and Coturn UDP port are free on the host. (`ts`): confirm `${GRAFANA_PORT}`
  and, if OPC-UA, `${OPCUA_SERVER_PORT_MAPPING}` are free.
- **Always verify TLS when calling the stack.** Never use `-k`/`--insecure`,
  on any host. Trust the stack's own self-signed certificate instead:
  1. `docker cp nginx_proxy:/opt/nginx/certs/cert.pem ./nginx-cert.pem`
     (regenerated on every nginx start, so re-copy after a restart);
  2. call `https://localhost:${GRAFANA_PORT}/...` with
     `--cacert ./nginx-cert.pem --resolve localhost:${GRAFANA_PORT}:${HOST_IP}`.
     The certificate is `CN=localhost` with no SAN, so the URL host must be
     `localhost`; `--resolve` routes it to `${HOST_IP}`.

  Add `--noproxy '*'` to these calls only, because the host's corporate
  proxy can't reach the local stack. Don't unset or change the host's proxy
  settings. For example:
  `curl -s --noproxy '*' --cacert ./nginx-cert.pem --resolve localhost:${GRAFANA_PORT}:${HOST_IP} https://localhost:${GRAFANA_PORT}/ts-api/health`.
- `multimodal`/`vllm`/`agentic`: test multimodal end-to-end via MQTT, not just REST
  200s — confirm `{{VISION_TOPIC}}`, `{{TS_RAW_TOPIC}}` (when the simulator or
  sensor source publishes over MQTT), `{{TS_PROCESSED_TOPIC}}`, and
  `{{FUSION_TOPIC}}` appear on the broker.
- `vllm`/`agentic`: reproduce the reference format. Use the reference
  services, the three dashboards, and `/insights-ui/` + `/agentic-ui/` as
  same-origin iframes behind nginx. Never substitute a hand-written
  explainer, a merged dashboard, a separate host port, or raw-API links
  (for example `/agent-api/...`); Grafana's router turns those into "Page
  not found".
- **Known startup-order caveat** (`multimodal`/`vllm`/`agentic`): Fusion Analytics
  only starts fusing once the vision metadata carries an RTP sender
  timestamp — DLSPS may not emit that for its first ~300 packets, so allow a
  short warm-up delay before asserting fused output in tests.
- `ts`: only one of `ia-opcua-server`/`ia-mqtt-publisher` runs at a time —
  verify the unused simulator is scaled to `0`, not merely stopped.
- `ts`: **enable only one alert channel** — MQTT and OPC-UA alert blocks in
  the same TICKscript is unsupported.
- `ts`: `config.json` (and variants) **MUST stay ≤ 5 KB**.
- `{{GENERATE_TESTS}}=yes` only: pytest venv at `./.venv` inside the
  stack/repo dir (`python -m venv .venv`) — system pip is PEP-668 blocked;
  `/tmp` may be `noexec`.
- **Never fabricate a missing pretrained model** (vision or sensor) — if no
  existing file or resolvable download/training source is available, stop
  and ask the user instead of shipping an empty placeholder path (see
  *Model availability* below).

## Model availability — ask, don't fabricate

`{{DEFAULT_MODEL}}` (vision, all non-`ts` modes) and, if the sensor pattern
is "pretrained model", `{{SENSOR_UDF_NAME}}`'s `.pkl`/`.xml`/`.bin` must be
either already available locally (a real path the invoking prompt names), or
fetchable from a concrete, resolvable URL (OMZ/OpenVINO Model Zoo, Hugging
Face, or a URL the invoking prompt supplied) via `model-download-user`/
`install.sh`. The same rule applies to the VLM (`{{VLM_MODEL}}` and any adapter) in
`vllm`/`agentic`, and to the agent LLM (`{{LLM_MODEL_NAME}}`) in `agentic`. If neither is true, **stop before writing the model-download step and
ask the user to provide the model** — do not invent a plausible-looking
model directory/filename and leave it as an empty placeholder.

## Optional external skills

If available, invoke; otherwise write files from the reference templates.

- `dlsps-user` — DLSPS deploy/config/REST for the vision half ([PIPELINE](references/PIPELINE.md))
- `dlstreamer-coding-agent` — custom GStreamer pipeline authoring (+ `vision`-mode demo/PoC app)
- `time-series-analytics-user` — sensor UDF + TICKscript authoring/deploy
  ([ANALYTICS](references/ANALYTICS.md) for `ts`, [TIMESERIES](references/TIMESERIES.md)
  for `multimodal`/`vllm`/`agentic`) — the primary delegate for `ts` demo mode
- `model-download-user` — OMZ/OpenVINO model IR for the vision model, or the
  agent LLM for `agentic` (the VLM for `vllm-server` is a Hugging Face
  download into `configs/vllm/`; see VLM.md)
- No delegate skill exists yet for the **Fusion Analytics** correlator or the
  **UI service** — author the correlator from
  [`references/FUSION.md`](references/FUSION.md), and copy and adapt the
  reference `ui-service` per [`references/UI_SERVICE.md`](references/UI_SERVICE.md)

## Reference implementation — copied and renamed by the scaffold script

The upstream
[`industrial-edge-insights-time-series/`](https://github.com/open-edge-platform/manufacturing-ai-suite/tree/main/industrial-edge-insights-time-series)
wind-turbine-anomaly-detection sample (`ts` mode) and
[`industrial-edge-insights-multimodal/`](https://github.com/open-edge-platform/manufacturing-ai-suite/tree/main/industrial-edge-insights-multimodal)
weld-defect-detection sample (`multimodal`/`vllm`/`agentic` modes) are copied
by [`scripts/scaffold_stack.py`](scripts/scaffold_stack.py), never with a
manual `cp -r`. The script drops docs, tests, training, Helm and repo
metadata, prunes by mode, renames every vertical-specific path and name, and
applies the known fixes. The renaming rule still applies: **no leftover
`weld`/`wind-turbine` names** in generated files, services, MQTT topics or
measurements. The script's leftover report is a naming checklist only: it
does not detect semantic settings (e.g. the copied agent policy's `mode: OR`
or `ticketing.backend: jira`), so also walk the per-vertical semantic
checklists independently; finish when both are clean and the report lists only
lines that are legitimately generic. The script needs a
reference checkout on disk (`reference_dir` / `ts_repo_dir`); clone the upstream
repo at a pinned tag if none exists. Details:
[`references/INSTALL.md`](references/INSTALL.md) → *Reference implementation*.

## Completion criteria (per mode, all applicable must pass)

Full per-mode checklists (`vision`: 3 criteria; `ts`: 9; `multimodal`: 9;
`vllm`: +3 more; `agentic`: +3 more; any mode with `{{OPENMES_ENABLED}}=yes`:
+4 more) are in
[`references/INSTALL.md`](references/INSTALL.md) → *Completion criteria* —
verify every applicable item before declaring success; no literal `{{...}}`
may remain in any generated file.

## Final summary — surface the proof (don't just name files)

Graders see only your **final message** + tool *names*, not file contents.
An expectation counts as met only if you **state it and quote the one
decisive line** in your closing summary — walk every completion criterion
for the chosen `{{DEPLOYMENT}}` mode plus the proof-point checklist in
[`references/INSTALL.md`](references/INSTALL.md) → *Final-summary proof
points*. A claim with no quoted evidence is treated as unmet.

**OpenMES in the summary.** If OpenMES was enabled, say which OpenMES the
alerts go to. With the **dummy receiver**, always give the user its alerts page
URL, `http://<HOST_IP>:8099/` (printed by `scaffold_stack.py`). Say that it is
a read-only test page with no login and dummy data, show how to stop it
(Ctrl-C in each terminal, or your tool's stop capability — there is no
separate stop script), and give the alert count from
`verify_stack.py`. With a real OpenMES, give the delivered count and where
to look in OpenMES (issues on the configured work order), never the token.

## Design-only / guidance answers — always state these explicit points

When the user asks only for a design, plan or explanation (no build), the
answer is graded on what it *says*, so name each applicable item explicitly
rather than implying it:

- **WebRTC path (vision modes):** MediaMTX terminates WHIP (DLSPS publishes)
  and WHEP (the browser plays); Coturn provides the ICE/TURN relay
  (`WHIP_SERVER_PORT`, the Coturn UDP port, `HOST_IP`/TURN settings in
  `.env`); nginx proxies `/<peer-id>/whip|whep` with upgrade headers. Stored
  frames are reviewed through SeaweedFS (`/image-store`).
- **Fusion Analytics image:** build it from `fusion-analytics/Dockerfile`
  (`COMPOSE_BAKE=false make build`) unless an actual prebuilt registry tag is
  pinned; never assume a prebuilt tag exists.
- **Makefile/install surface:** `install.sh`, `.env`, and the Makefile targets
  `check_env_variables`, `up`/`up_*`, `status` and `down`; the selected Grafana
  dashboard JSON from `dashboards_jsons/` is **copied into
  `configs/grafana/provisioning/` at install/`up` time** (the `up*` target
  clears every file already in that one provisioning directory before
  copying the new ones in — see `INSTALL.md`'s *Grafana dashboard swap* for
  the exact reference-Makefile step). **Warn the user before the first
  `up`/`up_*` run that this deletes every file already in
  `configs/grafana/provisioning/`**, including any manually edited dashboard
  JSON — back up custom edits (or keep them only under `dashboards_jsons/`,
  which is never deleted) before switching modes or re-running `up*`. State
  that no weld/wind-turbine names remain in the generated artifacts.
- **OpenMES:** say `{{OPENMES_ENABLED}}=yes` explicitly, that `openmes/`
  holds `openmes_publisher.py` copied verbatim from `assets/openmes/` plus a
  templated `openmes-publisher.json`, and that only `fused_decision == 1`
  from `{{FUSION_TOPIC}}` is published.
- **`agentic` readiness:** require `model-download` to complete; check the
  **actual host path behind the container `MODEL_PATH`** (the bind mount, e.g.
  `configs/agentic/models/llm_model_agentic/...` exists and is non-empty on
  the host — `MODEL_PATH` itself is a container path); then wait for
  `apm-llm` `GET /v1/config` to return 200 before declaring `apm-agent`
  healthy.
- **`LLM_MODE=fallback`:** `apm-llm` is **stopped/not started** (no OVMS
  container, no agent LLM weights needed); `apm-agent` still completes a full
  run (policy → analysis → ticket) with structured **rule-based** output from
  `policy_fallback.json`. Contrast with `LLM_MODE=llm`, where `apm-llm` must be
  healthy first.
- **Agent taxonomy rewrite (`agentic`):** when the user gave a use case but no
  defect list, do not stop at "I need the taxonomy". Propose a concrete draft
  and mark it for confirmation: set `use_case_id` (e.g. `part-quality-monitoring`
  from the stack name), then show the rewritten `agents.yaml`
  (`defect_classes`, `non_actionable_classes`, `priority_thresholds`,
  `critical_classes`, `fusion_policy.mode`, `ticketing.backend: none`),
  `prompts/<use_case_id>.txt` (`[SYSTEM]`/`[POLICY]`/`[ANALYSIS]`/`[EVIDENCE]`/
  `[TICKETING]` with the part-quality classes, label normalisation and
  severity tiers) and `policy_fallback.json` (per-class `alert_above` and
  `actions`) — e.g. actionable: Crack, Dent, Scratch, Overheat; non-actionable:
  Good Part, No Part, No Label; critical: Crack, Overheat.
