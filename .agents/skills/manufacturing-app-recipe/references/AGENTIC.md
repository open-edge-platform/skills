<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Agentic layer (`agentic` mode — the `vllm` layer plus agent orchestration)

`agentic` mode mirrors the reference `industrial-edge-insights-multimodal`
`make up_agentic` deployment. It is **additive**: it runs the complete
[`VLM.md`](VLM.md) layer (`vllm-server` + the UI's `/insights-ui/`
Explain flow) **and** the agent services below. Nothing from `vllm` mode is
replaced. Do not author a separate explainer service.

Compose files: `docker-compose.yml` + `docker-compose-vllm.yml` +
`docker-compose-agentic.yml` (+ `docker-compose-mcp.yml` only when
`{{AGENT_MCP}}=yes`). Copy the reference overlays and change only names,
models and use-case files.

## Components added by `docker-compose-agentic.yml`

| Service | Image | Role |
|---|---|---|
| `apm-agent` | `intel/agent-quality-handler` | LangGraph meta-agent running the policy → analysis → ticketing worker agents (plus evidence) for one time window of fused results |
| `apm-llm` | `openvino/model_server:<tag>-gpu` | OVMS serving the **agent LLM** from `MODEL_PATH`: `--model_path ${MODEL_PATH} --model_name ${LLM_MODEL_NAME} --rest_port 8000` (a pre-converted mediapipe graph; no other OVMS flags) |
| `model-download` | `intel/model-download` | fetches and converts the agent LLM into `./configs/agentic/models/llm_model_agentic/...` before `apm-llm` starts |
| `apm-metrics` | `intel/metrics-manager` | system and LLM metrics behind `/api/metrics/*` and `/api/v1/capabilities`. **Always included**, because the agentic UI renders these cards |
| `prometheus` | `prom/prometheus` | scrapes `apm-metrics` and `apm-agent` (`configs/agentic/prometheus/prometheus.yml`) |
| `multimodal-mcp-server` | built from `mcp-server/` | **optional**, only with `{{AGENT_MCP}}=yes` (`make up_agentic MCP=true`, needs `MCP_USERNAME`/`MCP_PASSWORD`). Leave it out otherwise |

The same `multimodal-agentic-ui` container from `docker-compose-vllm.yml`
switches into agentic mode via `AGENTIC_UI_ENABLED=true` and
`MQTT_DISABLED=false`, and additionally serves `/agentic-ui/`.

## Two models — ask for both

| Model | Served by | Device | Where it lives |
|---|---|---|---|
| VLM (+ optional LoRA) | `vllm-server` | Intel GPU only | `configs/vllm/{huggingface,models}` — see [`VLM.md`](VLM.md#models-ask-never-fabricate) |
| Agent LLM `{{LLM_MODEL_NAME}}` | `apm-llm` (OVMS) | `{{LLM_DEVICE}}` = `CPU` (default) or `GPU` | `configs/agentic/models/llm_model_agentic/openvino_models/<device>/<format>/<name>`; fetched by `make download_model`, or reused if already converted there |

`MODEL_PATH` is a **container** path. The Makefile derives it as
`/model/llm_model_agentic/openvino_models/$(LLM_DEVICE_LOWER)/$(LLM_WEIGHT_FORMAT_LOWER)/$(LLM_MODEL_NAME)`,
and `apm-llm` mounts `./configs/agentic/models:/model:ro`. Never create or
check `/model` on the host. Keep the reference `download_model` target,
including its first step: a one-off root container `chown`s
`configs/agentic/models` to the `model-download` image's user before the
non-root service writes into it.

## How a run is triggered (reference format: the UI, not Fusion)

1. The agentic dashboard (`{{DASHBOARD_SLUG}}_agentic.json`) is one
   full-page iframe of `window.location.origin + "/agentic-ui/"`, so it uses
   the same nginx origin and certificate as Grafana.
2. The user picks a **Time Range** (30 s / 1 m / 5 m / 10 m / 30 m) and
   clicks **Run Agentic Analysis**. `POST /agentic-ui/run` publishes to
   `MQTT_BATCH_TOPIC` (`apm/batch-complete`):
   `{"run_id": "<uuid>", "status": "completed", "device": "...", "video_filename": "{{OBJECT}}", "start_id": <now - range, epoch ns>, "end_id": <now, epoch ns>, "pipeline_status": "running"}`.
3. `apm-agent` (subscribed to that topic only) calls Fusion Analytics'
   storage API (`STORAGE_SERVICE_URL=http://ia-fusion-analytics:8080`) for
   `min_id=start_id`, `max_id=end_id`, then calls `apm-llm`.
4. The UI polls `apm-agent` `/agents/runs`, `/agents/status/{id}` and
   `/agents/results/{id}`, and renders the results page
   (`/agentic-ui/results/<run_id>`) plus the detections page.

Fusion Analytics does **not** publish `batch-complete` in the reference
format. Automatic triggering is an opt-in deviation; see
[`FUSION.md`](FUSION.md#batching-for-the-explanation-layer-opt-in).

## Storage API contract the agent depends on

`apm-agent` fails silently, producing empty or collapsed reports, if Fusion
Analytics' API deviates from this contract:

| Endpoint | Must return |
|---|---|
| `GET /detections?min_id&max_id&limit&label&min_confidence` | JSON **array** of rows with at least `frame_id`, `label` (the fused class), `confidence`, `fused_decision`, the modality fields, and `time`. The agent de-duplicates by `(frame_id, label)`, so a missing `frame_id` collapses each class to one row |
| `GET /detections/summary?min_id&max_id` | JSON **object** keyed by label: `{count, avg_confidence, max_confidence, min_confidence, label, fusion_mode}` |
| `GET /detections/max_id`, `GET /health` | watermark and health, as in the reference `api.py` |

`min_id`/`max_id` are epoch-**nanosecond** bounds (`time > min_id AND time
<= max_id`). Copy the reference `fusion-analytics/api.py` and change only
names. Apply the `_SAFE_LABEL_RE.fullmatch` fix from [`FUSION.md`](FUSION.md).

## Use-case files (`configs/agentic/`) — rewrite per vertical

| File | Change for `{{OBJECT}}` |
|---|---|
| `agents.yaml` | `use_case_id: {{USE_CASE_ID}}`; `policy.defect_classes`, `non_actionable_classes`, `priority_thresholds`, `critical_classes`; `policy.fusion_policy.mode: {{FUSION_MODE}}`; `ticketing.backend` (`none` unless the user names Jira/ServiceNow) |
| `prompts/{{USE_CASE_ID}}.txt` | the `[SYSTEM]`, `[POLICY]`, `[ANALYSIS]`, `[EVIDENCE]` and `[TICKETING]` sections with this vertical's taxonomy, label normalisation and severity tiers. The file name must equal `use_case_id` |
| `policy_fallback.json` | per-class `alert_above`/`description` and `actions` used when `LLM_MODE=fallback` |
| `prometheus/prometheus.yml` | unchanged from the reference |

`LLM_MODE` accepts only `llm` or `fallback`. Any other value, including
`server`, makes `apm-agent` refuse to start.

## Makefile target

`make up_agentic`: `check_hardware` → `check_models` → `check_env_variables`
→ `validate_host_ip` → `down`, then:

```
export NGINX_PROFILE=agentic AGENTIC_UI_ENABLED=true MQTT_DISABLED=false   # agentic_mcp when MCP=true
rm -f configs/grafana/provisioning/*.json   # reference Makefile step: clears the whole directory
cp configs/grafana/dashboards_jsons/{{DASHBOARD_SLUG}}_vlm.json     configs/grafana/provisioning/{{DASHBOARD_SLUG}}.json
cp configs/grafana/dashboards_jsons/{{DASHBOARD_SLUG}}_agentic.json configs/grafana/provisioning/{{DASHBOARD_SLUG}}_agentic.json
make download_model
```

That `rm -f .../*.json` is the reference Makefile's own, unmodified step —
it deletes any dashboard JSON already provisioned there, including manual
edits. Warn the user before the first `make up_agentic` (see `INSTALL.md` →
*Grafana dashboard swap*). If you ever write this cleanup yourself (rather
than relying on `make up_agentic`), scope it to the exact files you are
about to replace instead of a wildcard, confined to this stack's own
generated `configs/grafana/provisioning/` directory:

```
rm -f configs/grafana/provisioning/{{DASHBOARD_SLUG}}.json configs/grafana/provisioning/{{DASHBOARD_SLUG}}_agentic.json
```

```
docker compose -f docker-compose.yml -f docker-compose-vllm.yml -f docker-compose-agentic.yml [-f docker-compose-mcp.yml] up -d
make upload_tar_file
```

`check_hardware` and `check_models` gate on the **VLM** (see
[`VLM.md`](VLM.md#hardware-gate)), because `agentic` always includes
`vllm-server`.

## Completion criteria (`agentic` mode, in addition to `VLM.md`'s criteria 10–12)

13. `model-download` completes (or the converted model is already present),
    and `apm-llm` passes its health check (`GET /v1/config` returns 200)
    before `apm-agent` is healthy.
14. In the agentic dashboard, **Run Agentic Analysis** over a window that
    contains confirmed defects reaches `completed` on
    `/agentic-ui/results/<run_id>`. Quote the ticket text verbatim. For
    headless verification, `POST /agentic-ui/run` with
    `time_range=5m` through nginx is equivalent; do not hand-craft MQTT
    unless the UI is down.
15. `GET https://<HOST_IP>:${GRAFANA_PORT}/api/v1/capabilities` returns
    200 through nginx, and the metrics cards render in `/agentic-ui/`.
