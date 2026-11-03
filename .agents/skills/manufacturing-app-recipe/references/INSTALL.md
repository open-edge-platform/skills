<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# File layout, `.env`, validation, install/Makefile steps (per mode)

## Layout — `multimodal`/`vllm`/`agentic` modes (flat `{{STACK_DIR}}/`)

```
{{STACK_DIR}}/
├── README.md
├── docker-compose.yml
├── docker-compose-vllm.yml        # {{DEPLOYMENT}}=vllm or agentic: vllm-server + multimodal-agentic-ui (VLM.md)
├── docker-compose-agentic.yml     # {{DEPLOYMENT}}=agentic only: apm-agent, apm-llm, model-download, apm-metrics, prometheus (AGENTIC.md)
├── docker-compose-mcp.yml         # agentic + {{AGENT_MCP}}=yes only
├── .env                         # this stack's own config; secrets generated locally by install.sh (see *Secrets in `.env`*)
├── install.sh                   # preflight, .env bootstrap (HOST_IP/TURN/GIDs), model/data preparation
├── Makefile                     # required production entry points: check_env_variables, up_*, status, down
├── configs/
│   ├── dlstreamer-pipeline-server/
│   │   ├── config.json          # PIPELINE.md
│   │   ├── pipeline-request-cpu.json
│   │   └── models/              # vision model IR, downloaded by install.sh
│   ├── time-series-analytics-microservice/
│   │   ├── config.json          # TIMESERIES.md
│   │   ├── udfs/<name>.py
│   │   ├── tick_scripts/<name>.tick
│   │   └── models/<name>.pkl
│   ├── telegraf/
│   │   ├── entrypoint.sh
│   │   └── config/Telegraf.conf
│   ├── influxdb/{config,init-influxdb.sh}
│   ├── mqtt-broker/mosquitto.conf
│   ├── grafana/
│   │   ├── dashboards_jsons/{{DASHBOARD_SLUG}}.json           # multimodal (classic schema)
│   │   ├── dashboards_jsons/{{DASHBOARD_SLUG}}_vlm.json       # vllm/agentic (v2 schema) — UI_SERVICE.md
│   │   ├── dashboards_jsons/{{DASHBOARD_SLUG}}_agentic.json   # agentic (v2 schema)
│   │   └── provisioning/{dashboards.yml,datasources.yml}
│   ├── nginx/{nginx.conf.template,nginx-cert-gen.sh}           # NGINX_PROFILE base|vllm|agentic — PROXY_UI.md
│   ├── seaweedfs-s3/{seaweedfs_s3_config.json.template,s3-init-buckets.sh}
│   ├── vllm/                    # vllm/agentic: VLM weights, user-downloaded (VLM.md)
│   │   ├── huggingface/<vlm-model-dir>/
│   │   └── models/<lora-adapter-dir>/   # optional adapter
│   └── agentic/                 # agentic only (AGENTIC.md)
│       ├── agents.yaml          # use_case_id: {{USE_CASE_ID}}
│       ├── policy_fallback.json
│       ├── prompts/{{USE_CASE_ID}}.txt
│       ├── prometheus/prometheus.yml
│       └── models/llm_model_agentic/...   # agent LLM, written by make download_model
├── fusion-analytics/
│   ├── Dockerfile
│   ├── fusion.py                # FUSION.md
│   ├── api.py
│   └── requirements.txt
├── <data-simulator-or-adapter>/  # name it for THIS vertical, e.g. {{STACK_DIR}}-simulator/
│   │                             # — never keep the reference's weld-data-simulator/ name;
│   │                             #   swap for real camera+sensor in production
│   ├── Dockerfile
│   ├── publisher.py
│   └── simulation-data/*.avi + *.csv pairs
├── ui-service/                    # vllm/agentic: copied from the reference and adapted — UI_SERVICE.md
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/{app.py,insights.py,system_prompt.json,templates/,static/}
└── tests/                        # only if {{GENERATE_TESTS}}=yes — TESTS.md
    ├── conftest.py
    └── test_fusion_pipeline.py  # TESTS.md
```

Keep Compose overlays at the stack root beside `docker-compose.yml`: the
Makefile targets pass `docker-compose-vllm.yml` and
`docker-compose-agentic.yml` as root-relative filenames. `vllm` mode includes
the vLLM overlay; `agentic` mode includes both overlays. The agentic overlay
is additive: `vllm-server` and the UI keep running, and the agent services
are added on top.

`vllm`/`agentic` follow the reference format exactly: the same services,
three dashboards, `/insights-ui/` (Explain) and `/agentic-ui/` (Run Agentic
Analysis). Do **not** substitute a hand-written explainer service, a single
merged dashboard, or raw-API links for the UI.

This is a curated layout, not a mirror of the reference repo — omit
`docker-compose-vllm.yml`/`docker-compose-agentic.yml`/`configs/agentic/`/
`configs/vllm/`/`ui-service/` (unless `{{DEPLOYMENT}}` is `vllm`/`agentic`),
`docker-compose-mcp.yml`/`mcp-server/` (unless `{{AGENT_MCP}}=yes`),
`insights-workbench/`, `training/`, `helm/`, vertical-specific `docs/`,
`README-dockerhub.md`, `CHANGELOG.md`, and `third-party-programs.txt` from
the reference — see *Reference implementation* below for the full
copy/leave-behind table and renaming rule.

## Layout — `ts` mode

See [`APPS_CONVENTION.md`](APPS_CONVENTION.md) for the full `apps/{{APP_NAME}}/`
tree (`simulation-data/`, `telegraf-config/`, `time-series-analytics-config/`,
`grafana-dashboard.json`, `training/`) — this mode adds one folder to an
existing shared repo, it does not generate a new Compose topology.

## OpenMES publisher (optional, any mode — only if `{{OPENMES_ENABLED}}=yes`)

Full guide: [`OPENMES.md`](OPENMES.md).

- **Location:** `{{STACK_DIR}}/openmes/` (fused modes) or
  `apps/{{APP_NAME}}/openmes/` (`ts`). The folder contains:
  - `openmes_publisher.py`, copied verbatim from the skill's
    `assets/openmes/`;
  - `openmes-publisher.json`, templated per mode and holding no secrets;
  - the user-provided `openmes_token`.
- **Config:** set `mode`, `source_id`, the OpenMES IDs, the input topic
  and the per-mode `fields`/`timestamp_format` from `OPENMES.md` →
  *Per-mode input*. Validate the mapping against one real captured message
  before running.
- **Secret handling:**
  - Ask the user for the token file **path** only. The file is created by
    the user, set to `chmod 0400`, and kept out of the generated summary.
  - Never generate a token file with a real secret.
  - Add `openmes_token` and `openmes_events.db` to `.gitignore`.
- **Broker reachability:** the publisher runs on the host, so publish
  `ia-mqtt-broker` on `127.0.0.1:1883`:
  - fused modes: a `ports:` entry in the generated `docker-compose.yml`;
  - `ts`: a repo-root `docker-compose.override.yml`, picked up
    automatically by plain `make up_*_ingestion`.

  Never bind the anonymous broker to `0.0.0.0`.
- **Startup:** after `make up`/`make up_*` reports healthy, run
  `python -m venv .venv && . .venv/bin/activate && pip install paho-mqtt requests && python openmes_publisher.py --config ./openmes-publisher.json`.
  Document these steps in the generated `README.md`.

## `.env` — `multimodal`/`vllm`/`agentic` modes

```
COMPOSE_PROJECT_NAME={{STACK_DIR_SLUG}}
HOST_IP=localhost
GRAFANA_PORT=3000

INFLUXDB_USERNAME=            # alphabets only, >=5 chars, not "admin"
INFLUXDB_PASSWORD=            # >=10 alphanumeric, at least 1 digit, no shell-special chars
VISUALIZER_GRAFANA_USER=      # alphabets only, >=5 chars
VISUALIZER_GRAFANA_PASSWORD=  # same rule as INFLUXDB_PASSWORD
S3_STORAGE_USERNAME=
S3_STORAGE_PASSWORD=
# HTTP Basic Auth for the SeaweedFS filer UI at /image-store; both are required.
SEAWEEDFS_WEB_AUTH_USER=
SEAWEEDFS_WEB_AUTH_PASSWORD=
MTX_WEBRTCICESERVERS2_0_USERNAME={{TURN_USER}}
MTX_WEBRTCICESERVERS2_0_PASSWORD=   # generated: openssl rand -hex 16

CONTINUOUS_SIMULATOR_INGESTION=true   # false = ingest once, no loop
SIMULATION_REPLAY_COUNT=3
SIMULATION_TARGET_FPS=10
TS_RAW_TOPIC={{TS_RAW_TOPIC}}         # raw MQTT input from MQTT-publishing simulator/device; Telegraf mqtt_consumer subscribes here (e.g. weld-data)
TS_PROCESSED_TOPIC={{TS_PROCESSED_TOPIC}} # every UDF-processed point; Fusion Analytics consumes here (e.g. ts_weld_anomaly_detection)

FUSION_MODE={{FUSION_MODE}}           # AND | OR
TOLERANCE_NS={{TOLERANCE_NS}}         # e.g. 50e6

INFLUXDB_RETENTION_DURATION=1h0m0s
S3_BUCKET_TTL=30m
LOG_LEVEL=INFO

# vllm/agentic modes only — VLM served by vllm-server (full key list in VLM.md):
VLLM_IMAGE=intel/vllm:<pinned tag>
VLLM_MODEL_DIR=huggingface/{{VLM_MODEL_DIR}}
VLLM_SERVED_MODEL_NAME={{VLM_MODEL}}
VLLM_ADAPTER_NAME={{VLM_ADAPTER_NAME}}      # = VLLM_SERVED_MODEL_NAME when there is no adapter
VLLM_ADAPTER_DIR=lora-adapters/{{VLM_ADAPTER_DIR}}/
VLLM_GPU_MEMORY_UTILIZATION=0.27
MULTIMODAL_AGENTIC_UI_IMAGE={{STACK_DIR_SLUG}}-ui    # built from ./ui-service (UI_SERVICE.md)
NGINX_PROFILE=base                          # overridden by make up_vllm / up_agentic

# agentic mode only — agent LLM served by apm-llm (OVMS):
LLM_MODE=llm                                # llm | fallback (nothing else is accepted)
LLM_MODEL_NAME={{LLM_MODEL_NAME}}
LLM_DEVICE={{LLM_DEVICE}}                   # CPU (default) | GPU
LLM_WEIGHT_FORMAT={{LLM_WEIGHT_FORMAT}}
LLM_PORT=8010
MQTT_BATCH_TOPIC=apm/batch-complete
AGENTIC_QUALITY_HANDLER_IMAGE=intel/agent-quality-handler
MODEL_DOWLOADER_IMAGE=intel/model-download   # (sic) reference spelling, keep it
METRICS_MANAGER_IMAGE=intel/metrics-manager
HUGGINGFACEHUB_API_TOKEN=
# agentic + {{AGENT_MCP}}=yes only:
MCP_USERNAME=
MCP_PASSWORD=
```

### Secrets in `.env`

`.env` is the generated stack's own configuration file, which Docker Compose
and the Makefile load. The skill never reads credential files outside the
stack directory (SSH keys, cloud credentials, other projects' `.env`).

- Ship `.env` with every secret empty. `install.sh` fills the empty ones
  with random values on the host (`openssl rand -hex 16` or an alphanumeric
  generator that meets the validation rules). The user may set their own.
  Never ask for these values in chat.
- After generation, `chmod 600 .env`, and add `.env` to the stack's
  `.gitignore`.
- Never print, quote or echo secret values (passwords, tokens, keys) in
  chat, logs or the final summary. Name the variable instead (for example
  "log in with `VISUALIZER_GRAFANA_USER`/`VISUALIZER_GRAFANA_PASSWORD` from
  `.env`"). When reading `.env` from a script, read only the keys needed,
  never `cat` the whole file.

### Sensor topic wiring — `multimodal`/`vllm`/`agentic`

Keep the raw input and processed output topics distinct. In
`docker-compose.yml`, map the simulator's service-local `TS_TOPIC` to
`${TS_RAW_TOPIC}`, configure Telegraf's `mqtt_consumer` to subscribe to
`${TS_RAW_TOPIC}`, and map Fusion Analytics' service-local `TS_TOPIC` to
`${TS_PROCESSED_TOPIC}`. The TICKscript publishes every UDF-processed point
to `{{TS_PROCESSED_TOPIC}}`; Fusion must never subscribe to the raw input
topic.

### Healthchecks and host proxies

Docker injects the host's `http(s)_proxy` into every container. Write every
`localhost` healthcheck with `curl --noproxy '*'` (BusyBox `wget` ignores
`no_proxy`), and treat any HTTP status as healthy for the SeaweedFS S3
gateway (it answers anonymous requests with 403). Otherwise
`depends_on: condition: service_healthy` chains never start on proxied hosts.

### Env validation rules (`make check_env_variables`/`validate_host_ip`)

| Var | Rule |
|---|---|
| `{{DEPLOYMENT}}` | `vision` \| `ts` \| `multimodal` \| `vllm` \| `agentic` |
| `MODE` | `demo` \| `production` (`vision`/`ts` only) |
| `HOST_IP` | non-empty; reject `127.0.0.1` when validating for remote/WebRTC access |
| `FUSION_MODE` | exactly `AND` or `OR` — reject anything else |
| `TOLERANCE_NS` | numeric (accepts scientific notation e.g. `50e6`), `> 0` |
| `INFLUXDB_USERNAME`/`PASSWORD`, `VISUALIZER_GRAFANA_USER`/`PASSWORD` | non-empty, satisfy the length/charset rules from `.env` comments — reject weak/empty creds before `docker compose up` |
| `SEAWEEDFS_WEB_AUTH_USER`/`SEAWEEDFS_WEB_AUTH_PASSWORD` | non-empty; protect the SeaweedFS filer UI at `/image-store`; Nginx fails to start if either is unset |
| `PIPELINE_NAME` | matches the DLSPS `config.json` pipeline name exactly |
| `{{VISION_TOPIC}}`, `{{TS_RAW_TOPIC}}` (when the simulator/sensor source publishes over MQTT), `{{TS_PROCESSED_TOPIC}}`, `{{SENSOR_ALERT_TOPIC}}`, `{{FUSION_TOPIC}}` | required where applicable and distinct from each other (a collision silently merges data streams); `TS_RAW_TOPIC` feeds Telegraf, while `TS_PROCESSED_TOPIC` feeds Fusion Analytics |
| `MTX_WEBRTCICESERVERS2_0_USERNAME`/`PASSWORD` | non-empty (Coturn auth) |
| `INPUT_TYPE` | `simulator` \| `rtsp` \| `device` \| `opcua` |
| `vllm`/`agentic` only | `configs/vllm/huggingface` and `configs/vllm/models` exist and are non-empty (`check_models`); `VLLM_ADAPTER_NAME` set |
| `agentic` only | `LLM_MODEL_NAME` set; `LLM_MODE` is `llm` or `fallback`; `MODEL_PATH` resolvable on the host mount after `download_model`; `MCP_USERNAME`/`MCP_PASSWORD` valid when `MCP=true` |
| Vision model file (`configs/dlstreamer-pipeline-server/models/{{DEFAULT_MODEL}}/…`), sensor `.pkl`/`.xml`/`.bin` if the pattern is pretrained | must exist on disk before `up`. This check existing is not a substitute for asking the user up front when the model has no known source — see SKILL.md's *Model availability* rule |

Implement as `check_env_variables`/`validate_host_ip` Makefile targets (no
standalone `validate_env.sh` script — the reference repo doesn't have one),
exiting non-zero with a clear message on first failure; chain both as a
dependency of the `up`/`up_vllm`/`up_agentic` targets, same convention as
`ts` mode's `make check_env_variables`.

### `install.sh` — steps (`multimodal`/`vllm`/`agentic`)

1. **Preflight**: `make check_env_variables` (also `validate_host_ip` when
   validating for remote/WebRTC access).
2. **`.env` population**: `HOST_IP`, generated TURN creds
   (`openssl rand -hex 16`), video/render GIDs for GPU/NPU via
   `getent group video|render` (so DLSPS/UDF containers get `/dev/dri`
   access).
3. **Vision model download**: use `model-download-user` for OMZ/OpenVINO
   models, or fetch the vertical's specific classifier IR from its published
   location. Land it under
   `configs/dlstreamer-pipeline-server/models/{{DEFAULT_MODEL}}/` — a name
   that matches this vertical, never the reference's model directory name.
   **If no local file and no resolvable download URL exist, stop here and
   ask the user for the model instead of writing this step against a path
   that will never be populated.**
4. **Sensor UDF/model**: if the pattern is "pretrained model"
   (`time-series-analytics-user`'s taxonomy), fetch/package the `.pkl` (or
   `.xml`/`.bin`) into `configs/time-series-analytics-microservice/models/`
   under `{{SENSOR_UDF_NAME}}.*`, not the reference's filename; for
   rule-based patterns (threshold/rate-of-change) there is nothing to
   download. Same stop-and-ask rule as step 3 if a pretrained model has no
   known source.
5. **Simulator dataset** (if `{{INPUT_TYPE}}=simulator`): the paired
   `.avi`+`.csv` sample set for this vertical must come from the invoking
   prompt or the user — **do not silently download the reference's
   Intel_Robotic_Welding_Multimodal_Dataset** (that's the weld-defect
   sample's own dataset, not a generic stand-in for every vertical). If no
   local file and no resolvable URL exist, stop here and ask the user for
   one instead of fetching an unrelated dataset, per SKILL.md's *Model
   availability* rule. Once provided, land it under
   `<simulator>/simulation-data/`.
6. **Grafana dashboard swap** (done by each `up*` target, not by
   `install.sh`): the reference Makefile's own `up*` step first clears every
   file already under `configs/grafana/provisioning/` unconditionally, then
   copies the mode's dashboards from `dashboards_jsons/`:
   `{{DASHBOARD_SLUG}}.json` for `up`; `{{DASHBOARD_SLUG}}_vlm.json` (as
   `{{DASHBOARD_SLUG}}.json`) for `up_vllm`; that file plus
   `{{DASHBOARD_SLUG}}_agentic.json` for `up_agentic`. This mirrors the
   reference `Makefile` — any dashboard JSON edited in place there (rather
   than in `dashboards_jsons/`, which the swap only ever reads from) is lost
   on the next `up*`. Tell the user this before the first `up*` run. If you
   ever write this cleanup step yourself instead of relying on `make up*`,
   scope it to the exact filenames about to be replaced rather than a
   wildcard, confined to this stack's own generated provisioning directory.
7. **TLS cert**: generated by Nginx's own entrypoint script
   (`nginx-cert-gen.sh`) on first container start — `install.sh` does not
   need to pre-generate it, just ensure the tmpfs cert volume exists.
8. **Locally built images**: Fusion Analytics, the simulator and (for
   `vllm`/`agentic`) `ui-service` are built from this stack's sources (`make
   build`). If `docker compose build` (bake) hangs on the host, build each one
   with plain `docker build -t <image>:<tag> ./<dir>`.
9. **`vllm`/`agentic` only — VLM weights**: confirm `configs/vllm/huggingface/`
   (and `configs/vllm/models/` when an adapter is used) are populated with
   the user-named model (see [`VLM.md`](VLM.md#models-ask-never-fabricate)).
   Never download a substitute.
10. **`agentic` only — agent LLM weights**: `make download_model` (reference
   target, including its root `chown` of `configs/agentic/models`) runs
   `model-download` before `apm-llm` starts. It is skipped when the converted
   model already exists at the host path. `MODEL_PATH` is a container path
   under `/model`; check the stack-relative host mount
   (`./configs/agentic/models/llm_model_agentic/...`), never `/model` on the host.

### Required `Makefile` targets — `multimodal`/`vllm`/`agentic`

- `up`: `check_env_variables` → `validate_host_ip` → `down` → dashboard swap →
  `docker compose up -d` — plain `multimodal` mode, no LLM/VLM overlay.
- `up_vllm`: `check_hardware` → `check_models` → the same preflight chain,
  then `NGINX_PROFILE=vllm AGENTIC_UI_ENABLED=false MQTT_DISABLED=true`,
  the `_vlm` dashboard swap, and `docker compose -f docker-compose.yml -f
  docker-compose-vllm.yml up -d` — use this one, not `up`, when
  `{{DEPLOYMENT}}=vllm`. Exact recipe in [`VLM.md`](VLM.md#makefile-target).
- `up_agentic`: `check_hardware` → `check_models` → the same preflight
  chain, then `NGINX_PROFILE=agentic` (`agentic_mcp` with `MCP=true`),
  `AGENTIC_UI_ENABLED=true MQTT_DISABLED=false`, both `_vlm` and `_agentic`
  dashboards, `make download_model`, and all three Compose files — use this
  one when `{{DEPLOYMENT}}=agentic`. Exact recipe in
  [`AGENTIC.md`](AGENTIC.md#makefile-target).
- `check_hardware` / `check_models` / `download_model` / `build`: copy the
  reference targets. `check_hardware` enforces Panther Lake and honours
  `PLATFORM_CHECK=false` (CI/validation only). `check_models` checks
  `configs/vllm/{models,huggingface}`. Never bring up `vllm`/`agentic` mode by manually
  passing `-f docker-compose-vllm.yml`/`-f docker-compose-agentic.yml` to a
  bare `docker compose up` — these three targets are the actual entry
  points, one per `{{DEPLOYMENT}}` value, not a single conditional `up`.
- `down`: `docker compose down -v --remove-orphans`.
- `status`: `docker ps` table filtered to this stack's network, then tail the
  last 5 log lines of every container and flag any containing `error`
  (case-insensitive) — do not fail the whole command on a false-positive
  first-login Grafana token warning, just surface it.

### Final-summary proof points — `multimodal`/`vllm`/`agentic`

Quote in the closing summary: the `docker compose up -d` output showing all
containers `healthy`/`running`; the core MQTT topic subscriptions
(`{{VISION_TOPIC}}`, `{{TS_RAW_TOPIC}}` when the simulator/sensor source
publishes over MQTT,
`{{TS_PROCESSED_TOPIC}}`, `{{FUSION_TOPIC}}`) each with one captured message;
the `FUSION_MODE` value and one example fused-decision JSON
that matches its semantics; the InfluxDB `select * from` output for the
multimodal measurement; the Grafana dashboard URL + confirmation the WebRTC
iframe/panel is present; and:

- `vllm`/`agentic`: the dashboard names provisioned (`... Explainability
  Dashboard`, plus `... - Agentic Dashboard` for agentic), `/insights-ui/api/vllm/health`
  → `{"accessible": true}`, and the VLM text returned by **Explain** for one
  defective row;
- `agentic`: the `run_id` and ticket text of one **Run Agentic Analysis**
  run that reached `completed`, and `/api/v1/capabilities` → 200.

## `.env` — `ts` mode (required fields, shared across all apps — do not fork per app)

```
COMPOSE_PROJECT_NAME=timeseriessoftware
TIMESERIES_UID=2999
KAPACITOR_PORT=9092
GRAFANA_PORT=3000
LOG_LEVEL=INFO

CONTINUOUS_SIMULATOR_INGESTION=true   # false = ingest once, no loop

INFLUXDB_USERNAME=            # alphabets only, >=5 chars, not "admin"
INFLUXDB_PASSWORD=            # >=10 alphanumeric, at least 1 digit, no shell-special chars
VISUALIZER_GRAFANA_USER=      # alphabets only, >=5 chars
VISUALIZER_GRAFANA_PASSWORD=  # same rule as INFLUXDB_PASSWORD
VISUALIZER_GRAFANA_INACTIVE_TIMEOUT=1h

INFLUXDB_RETENTION_DURATION=1h0m0s
OPCUA_SERVER_PORT_MAPPING=30003
```

No per-vertical topic/mode vars belong in `.env` — those live inside
`apps/{{APP_NAME}}/` (Telegraf input blocks, `config.json`'s `alerts`
section) per [`APPS_CONVENTION.md`](APPS_CONVENTION.md).

### Validation — reuse the Makefile's own target, don't reimplement (`ts`)

```bash
make check_env_variables
```

This already validates `INFLUXDB_USERNAME`/`PASSWORD` and
`VISUALIZER_GRAFANA_USER`/`PASSWORD` against the exact charset/length rules
documented above, and is a hard dependency of both `up_mqtt_ingestion` and
`up_opcua_ingestion` — you never need to call it manually before `make up_*`,
but do call it manually when just scaffolding files (before the first
`make up_*`) to fail fast on a bad `.env`.

Additional rules **this skill** enforces before generating files (not
covered by the Makefile target):

| Var | Rule |
|---|---|
| `{{APP_NAME}}` | kebab-case, not already present in `SAMPLE_APP_LIST` |
| `{{INGEST_TRANSPORT}}` | exactly `opcua` or `mqtt` |
| `{{ALERT_CHANNEL}}` | exactly `mqtt` or `opcua` — never both enabled in the same TICKscript |
| `config.json`/variants | ≤ 5 KB each (microservice hard limit) |
| `{{SENSOR_UDF_NAME}}` | matches the UDF's internal filename inside the packaged `.tar` exactly |

### `Makefile` targets (reference — do not duplicate, just call) — `ts`

- `make up_opcua_ingestion app={{APP_NAME}}` — OPC-UA simulator path;
  MQTT publisher scaled to `0`.
- `make up_mqtt_ingestion app={{APP_NAME}}` — MQTT publisher path; OPC-UA
  simulator scaled to `0`.
- `make status` — table of running containers filtered to this stack +
  a best-effort scan of the last 5 log lines per container for the word
  "error" (informational, not a hard gate — a stale first-login Grafana
  warning is expected noise).
- `make down` — `docker compose down -v --remove-orphans`.

### Final-summary proof points — `ts`

Quote in the closing summary: `{{APP_NAME}}` appearing in the Makefile's
`SAMPLE_APP_LIST` diff; the `make check_env_variables` pass/fail output; the
`make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}}` container-healthy
output confirming the unused simulator is scaled to `0`; the InfluxDB
`select * from` output for the raw sensor measurement; the flagged-anomaly
log line + the captured MQTT/OPC-UA alert; and the Grafana dashboard URL
with confirmation `apps/{{APP_NAME}}/grafana-dashboard.json` is what's
rendering (not a stale previous app's dashboard).

## Image tags — pin to the latest available tag (never `:latest`)

Resolve each image to the **newest published stable tag on Docker Hub**
(query the repo's `tags` API with `ordering=last_updated`), pin it, and
ignore `*-weekly` pre-releases.

- `intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24` (vision — `vision`,
  `multimodal`, `vllm`, `agentic`)
- `intel/ia-time-series-analytics-microservice:<latest>` (Kapacitor + UDF —
  `ts`, `multimodal`, `vllm`, `agentic`)
- `intel/ia-multimodal-fusion-analytics:<latest>` (multimodal correlator, built
  from `fusion-analytics/Dockerfile` if no prebuilt tag is pinned yet —
  `multimodal`, `vllm`, `agentic`)
- `telegraf:1.39.3-alpine`, `influxdb:1.12.4` (all production modes)
- `eclipse-mosquitto:2.0.22`, `grafana/grafana-oss:13.0.2`, `nginx:1.31.4`
  (all production modes)
- `bluenviron/mediamtx:1.20.1` (WebRTC WHIP/WHEP), `coturn/coturn:4.17.2-alpine`
  (ICE/TURN), `chrislusf/seaweedfs:4.42` (S3) — `multimodal`, `vllm`, `agentic` only
- `intel/ia-opcua-server:<latest>` / `intel/ia-mqtt-publisher:<latest>`
  (simulators) — `ts` only, whichever matches `{{INGEST_TRANSPORT}}`
- `intel/vllm:<pinned>` (`vllm-server`, the VLM; reference
  `0.21.0-ubuntu24.04`) — `vllm`, `agentic`
- `multimodal-agentic-ui` — **built locally** from `{{STACK_DIR}}/ui-service/`
  as `{{STACK_DIR_SLUG}}-ui:<tag>`. Reuse the prebuilt `intel/multimodal-agentic-ui`
  only under the exception in [`UI_SERVICE.md`](UI_SERVICE.md) — `vllm`, `agentic`
- `openvino/model_server:<tag>-gpu` (OVMS, serves the **agent** LLM as
  `apm-llm`; reference `2026.4.1-gpu`) — `agentic` only
- `intel/agent-quality-handler`, `intel/model-download`,
  `intel/metrics-manager`, `prom/prometheus:v2.53.4` — `agentic` only; all
  four are always included (the agentic UI needs `apm-metrics`)
- `multimodal-mcp-server` (built from `mcp-server/`) — `agentic` with
  `{{AGENT_MCP}}=yes` only

## Reference implementation — copied and renamed by `scripts/scaffold_stack.py`

The upstream
[`industrial-edge-insights-time-series/`](https://github.com/open-edge-platform/manufacturing-ai-suite/tree/main/industrial-edge-insights-time-series)
wind-turbine-anomaly-detection sample (`ts` mode) and
[`industrial-edge-insights-multimodal/`](https://github.com/open-edge-platform/manufacturing-ai-suite/tree/main/industrial-edge-insights-multimodal)
weld-defect-detection sample (`multimodal`/`vllm`/`agentic` modes) are the
**source**. [`scripts/scaffold_stack.py`](../scripts/scaffold_stack.py) copies
them and renames every vertical-specific path and name, so the generated
stack keeps the reference's format exactly. Do **not** hand-copy with
`cp -r`, and do **not** hand-write the generic files. A manual copy leaves
vertical-specific leftovers (unused `weld_anomaly_detector.*` files, a
`weld-data-simulator/` folder, weld docs), and hand-writing re-introduces bugs
the reference already solved. The tables below describe what the script
keeps, renames and drops. The agent edits the lines in the script's
leftover report (naming only) **and** independently applies the per-vertical
semantic checklists (agent policy `mode`, ticketing backend, thresholds,
prompts), which the report cannot detect.

**If `scripts/scaffold_stack.py` cannot be run** (permission/sandbox
restriction, no filesystem access to the reference checkout, or similar):
do not work around the restriction, and do not report the stack as
scaffolded unless the files genuinely exist on disk. Instead, list the
reference checkout's actual directory structure, reproduce the identical
layout by hand under the new stack directory, and apply only the
vertical-specific adaptations from the copy/leave-behind tables below —
never substitute a different file layout or invent files the reference
does not have.

### What to copy vs. what to leave behind (`multimodal`/`vllm`/`agentic`)

| Copy (adapt names/content to `{{OBJECT}}`/`{{SENSOR_UDF_NAME}}`/`{{STACK_DIR}}`) | Leave out unless the mode/question explicitly requests it |
|---|---|
| `docker-compose.yml` topology, `.env` keys, and the required `Makefile` targets | `docker-compose-vllm.yml`/`docker-compose-agentic.yml`/`configs/agentic/` — `vllm`/`agentic` modes only |
| `configs/{dlstreamer-pipeline-server,time-series-analytics-microservice,telegraf,influxdb,mqtt-broker,grafana,nginx,seaweedfs-s3}/` structure | `insights-workbench/` — superseded by `ui-service/`'s `/insights-ui/` |
| `vllm`/`agentic`: `ui-service/`, adapted per [`UI_SERVICE.md`](UI_SERVICE.md)'s edit list and built locally; `configs/agentic/` with rewritten use-case files ([`AGENTIC.md`](AGENTIC.md)) | `ui-service/` and `configs/agentic/` in `multimodal` mode; the reference weld LoRA adapter for a non-weld vertical |
| `fusion-analytics/{Dockerfile,fusion.py,api.py,requirements.txt}` (generalize label lists — see [FUSION.md](FUSION.md)) | `training/` (weld classifier/VLM training scripts) — the new vertical's model is supplied by the user or fetched via `model-download-user`, not trained here |
| the data simulator's `Dockerfile`/`publisher.py` control flow (paired video+CSV replay) | `docs/user-guide/weld-defect-detection/`, `README-dockerhub.md`, `CHANGELOG.md`, `third-party-programs.txt` — reference-repo metadata |
| one dashboard JSON as a layout template; for `vllm`/`agentic` also the reference `*_vlm.json` (and `*_agentic.json` for agentic), renamed `{{DASHBOARD_SLUG}}_vlm.json` / `_agentic.json`, with the edits in [`UI_SERVICE.md`](UI_SERVICE.md) | the `*_vlm.json`/`*_agentic.json` variants in `multimodal` mode; a hand-built single dashboard replacing them in `vllm`/`agentic` |
| `tests/` structure/pattern from [TESTS.md](TESTS.md) — only if `{{GENERATE_TESTS}}=yes` | the reference's actual weld-assertion test bodies — write new assertions against `{{VISION_TOPIC}}`/`{{TS_RAW_TOPIC}}`/`{{TS_PROCESSED_TOPIC}}`/`{{FUSION_TOPIC}}`; the whole `tests/` folder if `{{GENERATE_TESTS}}=no` |
| `helm/` | always — Helm/Kubernetes deployment is out of scope for this skill; Docker Compose only |

### What to copy vs. what to leave behind (`ts`)

| Copy | Leave out |
|---|---|
| `simulation-data/`, `telegraf-config/`, `time-series-analytics-config/` shape, `grafana-dashboard.json` | another app's `training/` scripts — write new ones only if this vertical trains a model |
| the chosen simulator's control flow (OPC-UA server or MQTT publisher) | the unused simulator (OPC-UA vs MQTT) entirely |
| `Makefile` `SAMPLE_APP_LIST` registration pattern | `DEFAULT_SAMPLE_APP` change, unless explicitly requested |

### Renaming rule — no leftover vertical-specific names

Every file, directory, service name, container name, image env var, MQTT
topic, InfluxDB measurement, WebRTC peer-id, and dashboard filename that is
vertical-specific in a reference (contains `weld`/`Weld`, `wind-turbine`, or
any other old vertical's name) MUST be renamed to match this stack's own
`{{OBJECT}}`/`{{SENSOR_UDF_NAME}}`/`{{STACK_DIR}}`/`{{APP_NAME}}` — never
leave the reference's naming in a generated stack for a different vertical
(data simulator directory + Compose service, its image env var, UDF
file/class + tick script — **delete** the reference's original files
entirely rather than leaving them unused alongside the new ones, pretrained
model files, vision model directory, WebRTC `peer-id`/S3 `folder_prefix`,
MQTT topics, InfluxDB measurements, dashboard JSON filename).

## Completion criteria (per mode, all applicable must pass)

**`vision`** (demo/PoC — see [`DEMO_POC.md`](DEMO_POC.md)):
1. The chosen delegate skill's container(s) start successfully.
2. One inference call round-trips end-to-end with evidence quoted verbatim.
3. No literal `{{...}}` remains.

**`ts`** (demo — same bar as `time-series-analytics-user`; production — all
of these):
1. `apps/{{APP_NAME}}/` exists with all required subpaths; registered in
   `SAMPLE_APP_LIST`.
2. `make check_env_variables` exits 0 with a valid `.env`.
3. `make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}}` → all
   containers `running`/`healthy`; unused simulator scaled to `0`.
4. `curl -s --noproxy '*' --cacert ./nginx-cert.pem --resolve localhost:${GRAFANA_PORT}:${HOST_IP} https://localhost:${GRAFANA_PORT}/ts-api/kapacitor/v1/ping` returns 204/200 (certificate copied from `nginx_proxy` per SKILL.md's *Execution guardrails*).
5. InfluxDB measurement for the raw sensor stream populated within 30 s.
6. `config.json`'s `udfs.models` key consistent with the chosen UDF pattern.
7. The UDF-flagged measurement populates; the alert channel captures one
   crit alert.
8. Grafana shows `apps/{{APP_NAME}}/grafana-dashboard.json` rendering live
   data.
9. If `{{GENERATE_TESTS}}=yes`: `pytest -q tests/` passes, ≥ 6 tests
   collected.

**`multimodal`** (all of these; **`vllm`/`agentic` add their own criteria below**):
1. `./install.sh` succeeds; no leftover reference-vertical artifacts.
2. `make check_env_variables` exits 0; an invalid `FUSION_MODE` exits non-zero.
3. `docker compose up -d` → all containers `running`/`healthy` (incl.
   `mediamtx`, `coturn`, `seaweedfs-*`).
4. The MQTT topics (`{{VISION_TOPIC}}`, `{{TS_RAW_TOPIC}}` when the
   simulator/sensor source publishes over MQTT, `{{TS_PROCESSED_TOPIC}}`, and
   `{{FUSION_TOPIC}}`) carry data.
5. A fused message appears only per `{{FUSION_MODE}}` semantics, within
   `{{TOLERANCE_NS}}`.
6. InfluxDB has both the raw vision measurement and the multimodal measurement
   populated.
7. Grafana renders the WebRTC panel + sensor trend + multimodal verdict table.
8. If `{{GENERATE_TESTS}}=yes`: `pytest -q tests/` passes, ≥ 9 tests
   collected.
9. No literal `{{...}}` remains anywhere.

**`vllm`** (criteria 1–9 above, plus — full wording in [`VLM.md`](VLM.md#completion-criteria-vllm-mode-in-addition-to-the-base-multimodal-criteria-19)):
10. `/insights-ui/api/vllm/health` (through nginx) returns `{"accessible": true}`.
11. `/insights-ui/` returns 200 through nginx, and the `... Explainability
    Dashboard` renders it in its **VLLM Reasoning** iframe.
12. **Explain** on one defective fused row returns VLM text grounded in the
    stored frame and the sensor values, quoted verbatim.

**`agentic`** (criteria 1–12 above, plus — full wording in [`AGENTIC.md`](AGENTIC.md#completion-criteria-agentic-mode-in-addition-to-vlmmds-criteria-1012)):
13. `model-download` completes (or the converted model is already present),
    and `apm-llm`'s health check passes (`GET /v1/config` returns 200) before
    `apm-agent` is marked healthy.
14. **Run Agentic Analysis** in the `... - Agentic Dashboard` (or `POST
    /agentic-ui/run` through nginx) reaches `completed` on
    `/agentic-ui/results/<run_id>`. Quote the ticket text verbatim.
15. `/api/v1/capabilities` returns 200 through nginx, and the metrics cards
    render in `/agentic-ui/`.

**`{{OPENMES_ENABLED}}=yes`** (any mode, on top of that mode's criteria;
see [`OPENMES.md`](OPENMES.md) → *Manual verification*):
O1. The publisher logs `Subscribed topic=<{{OPENMES_INPUT_TOPIC}}>`. One
     injected defect logs `Delivered event=<id> issue_id=<n>`, and that
     Issue is visible in OpenMES with a populated `description`.
O2. Replaying the identical payload logs `Duplicate event ignored`, and no
     new Issue appears.
O3. One injected non-defect creates no Issue.
O4. An invalid token file logs `Auth failure (401)`, and the event is
     stored as `blocked`.
O5. Dummy receiver only: `verify_stack.py` reports `dummy OpenMES receiver`
     PASS, and the final summary gives the user the alerts page URL
     `http://<HOST_IP>:8099/` and how to stop it (Ctrl-C in each terminal,
     or your tool's stop capability — there is no separate stop script).

Never quote the token.
