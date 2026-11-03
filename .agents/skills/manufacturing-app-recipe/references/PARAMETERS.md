<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Parameters (from invoking prompt)

| Param | Purpose | Modes |
|---|---|---|
| `{{DEPLOYMENT}}` | `vision` \| `ts` \| `multimodal` \| `vllm` \| `agentic` — Question 0's answer | all |
| `{{MODE}}` | `demo` \| `production` (default `production`) — sub-mode within `vision`/`ts`; `multimodal`/`vllm`/`agentic` are production-only | `vision`, `ts` |
| `{{OBJECT}}` | defect/anomaly label in dashboard/alerts (e.g. `weld_defect`, `tool_wear`, `wind_turbine`); any MQTT/Grafana/InfluxDB-safe string | all |
| `{{STACK_DIR}}` | absolute parent path for a new, flat, standalone stack directory (e.g. `weld-defect-stack`) — `multimodal`/`vllm`/`agentic` only; never assumed from the current working directory | `multimodal`, `vllm`, `agentic` |
| `{{STACK_DIR_SLUG}}` | lowercase, hyphenated basename of `{{STACK_DIR}}`: `COMPOSE_PROJECT_NAME` and the prefix of locally built image names (for example `{{STACK_DIR_SLUG}}-ui`) | `multimodal`, `vllm`, `agentic` |
| `{{TS_REPO_DIR}}` | absolute path to an existing `industrial-edge-insights-time-series` checkout to add `apps/{{APP_NAME}}/` into (or where to clone it fresh) — `ts` production only | `ts` |
| `{{APP_NAME}}` | the new `apps/<name>/` folder name, kebab-case (e.g. `wind-turbine-anomaly-detection`) | `ts` |
| `{{DEFAULT_MODEL}}`, `{{OTHER_MODELS}}` | vision classifier/detector options for DLSPS | `vision`, `multimodal`, `vllm`, `agentic` |
| `{{PIPELINE_NAME}}` | canonical DLSPS pipeline `name` (e.g. `weld_defect_classification`); variants `<name>`/`_gpu`/`_npu` | `vision`, `multimodal`, `vllm`, `agentic` |
| `{{VISION_TOPIC}}` | MQTT topic DLSPS publishes classification/detection metadata to | `multimodal`, `vllm`, `agentic` |
| `{{SENSOR_UDF_NAME}}` | Time Series Analytics UDF name; backed by a pretrained model or a threshold/rate-of-change rule (time-series-analytics-user's `references/patterns.md` patterns) | `ts`, `multimodal`, `vllm`, `agentic` |
| `{{SENSOR_MEASUREMENT}}` | InfluxDB measurement where the raw sensor stream lands | `ts`, `multimodal`, `vllm`, `agentic` |
| `{{SENSOR_TAGS}}` | OPC-UA node IDs / MQTT field names to ingest; in `vllm`/`agentic` also the sensor fields (with units) the UI's Explain prompt lists | `ts`, `multimodal`, `vllm`, `agentic` |
| `{{INGEST_TRANSPORT}}` | `opcua` \| `mqtt` (default `opcua` for `ts`) — which simulator/Telegraf input plugin drives ingestion | `ts`, `multimodal`, `vllm`, `agentic` |
| `{{TS_RAW_TOPIC}}` | MQTT topic for raw sensor points published by an MQTT-backed simulator/device and consumed by Telegraf; not used for Fusion input | `multimodal`, `vllm`, `agentic` (MQTT-backed input) |
| `{{TS_PROCESSED_TOPIC}}` | MQTT topic the Time Series Analytics UDF publishes **every processed point** to; Fusion Analytics subscribes here | `multimodal`, `vllm`, `agentic` |
| `{{SENSOR_ALERT_TOPIC}}` | MQTT topic for the sensor-only crit alert | `multimodal`, `vllm`, `agentic` |
| `{{ALERT_CHANNEL}}` | `mqtt` (default) \| `opcua` — **enable only one** | `ts` |
| `{{ALERT_TOPIC}}` | MQTT topic for crit alerts, only when `{{ALERT_CHANNEL}}=mqtt` | `ts` |
| `{{FUSION_TOPIC}}` | MQTT topic Fusion Analytics publishes the fused verdict to | `multimodal`, `vllm`, `agentic` |
| `{{FUSION_MODE}}` | `AND` \| `OR` (default `OR`) — both vs either modality must flag anomaly | `multimodal`, `vllm`, `agentic` |
| `{{TOLERANCE_NS}}` | timestamp-matching tolerance in nanoseconds (default `50e6` = 50 ms) | `multimodal`, `vllm`, `agentic` |
| `{{DASHBOARD_SLUG}}` / `{{DASHBOARD_TITLE}}` | Grafana dashboard identifier; `vllm`/`agentic` also generate `{{DASHBOARD_SLUG}}_vlm.json` ("{{DASHBOARD_TITLE}} Explainability Dashboard") and, for agentic, `{{DASHBOARD_SLUG}}_agentic.json` ("{{DASHBOARD_TITLE}} - Agentic Dashboard") | all production modes |
| `{{INPUT_TYPE}}` | `simulator` (default) \| `rtsp`/`device` (real camera) + `mqtt`/`opcua` (real sensor feed) | `vision`, `multimodal`, `vllm`, `agentic` |
| `{{VLM_MODEL}}`, `{{VLM_MODEL_DIR}}` | vision-language model served by `vllm-server` (Hugging Face id → `VLLM_SERVED_MODEL_NAME`; folder under `configs/vllm/huggingface/` → `VLLM_MODEL_DIR`). No default — the user names it (reference: `unsloth/Qwen3.5-2B`). Intel GPU only | `vllm`, `agentic` |
| `{{VLM_ADAPTER_NAME}}`, `{{VLM_ADAPTER_DIR}}` | optional LoRA adapter (`configs/vllm/models/<dir>`). `none` → `VLLM_ADAPTER_NAME = VLLM_SERVED_MODEL_NAME` and the `--enable-lora` flags removed. The reference weld adapter is valid for weld only | `vllm`, `agentic` |
| `{{LLM_MODEL_NAME}}`, `{{LLM_DEVICE}}`, `{{LLM_WEIGHT_FORMAT}}` | **agent** LLM served by `apm-llm` (OVMS): model id, `CPU` (default) \| `GPU`, `int4` (default). Separate from the VLM | `agentic` |
| `{{LLM_MODE}}` | `llm` (default) \| `fallback` (rule-based, from `policy_fallback.json`) — no other value is accepted | `agentic` |
| `{{AGENT_TRIGGER}}` | `ui` (default, reference format: **Run Agentic Analysis** in `/agentic-ui/`) \| `size` \| `time` (opt-in automatic runs published by Fusion Analytics) | `agentic` |
| `{{BATCH_SIZE}}`, `{{BATCH_INTERVAL_S}}`, `{{BATCH_MIN_INTERVAL_S}}` | only when `{{AGENT_TRIGGER}}` is `size`/`time`: confirmed defects per run (e.g. `10`), seconds between `time` runs (e.g. `300`), cooldown of at least one agent run (CPU: `120`–`300`) | `agentic` |
| `{{AGENT_MCP}}` | `yes` \| `no` (default `no`) — add the reference MCP server overlay (`make up_agentic MCP=true`) | `agentic` |
| `{{USE_CASE_ID}}` | agent use-case id: `agents.yaml` `use_case_id`, the prompt file name `prompts/{{USE_CASE_ID}}.txt`, and the UI's `USE_CASE_ID` | `agentic` |
| `{{UI_TITLE}}` | page title shown by `ui-service` (reference: `Multimodal Weld Defect Detection`) | `vllm`, `agentic` |
| `{{VISION_MEASUREMENT}}` | InfluxDB measurement for raw vision results, tagged `search_time` (reference: `vision-weld-classification-results`); read by the UI's Explain flow | `multimodal`, `vllm`, `agentic` |
| `{{FUSION_MEASUREMENT}}` | InfluxDB measurement for fused verdicts — keep the reference name `fusion_result` (the UI's `FUSION_MEASUREMENT` and the agent's storage API default to it) | `multimodal`, `vllm`, `agentic` |
| `{{HOST_IP}}` | host IP for Nginx/Grafana/WebRTC (default `127.0.0.1`; Coturn's `--external-ip` needs an IP, not `localhost`) | all production modes |
| `{{TURN_USER}}`, `{{TURN_PASS}}` | Coturn / MediaMTX ICE credentials (default `turnuser` / a generated secret) | `multimodal`, `vllm`, `agentic` |
| `{{GENERATE_TESTS}}` | `yes` \| `no` (no default — ask explicitly) — whether to author the `tests/` pytest suite; skip `tests/` entirely and its pytest completion criteria when `no` | `ts`, `multimodal`, `vllm`, `agentic` |
| `{{OPENMES_ENABLED}}` | `yes` \| `no` (default `no`) — optional OpenMES defect publishing ([`OPENMES.md`](OPENMES.md)) | all |
| `{{OPENMES_BASE_URL}}`, `{{OPENMES_TOKEN_FILE}}` | OpenMES base URL (prefer `https://`) and the **path** to a user-created token file — never the token value | all, if `{{OPENMES_ENABLED}}=yes` |
| `{{OPENMES_WORK_ORDER_ID}}`, `{{OPENMES_ISSUE_TYPE_ID}}`, `{{OPENMES_BATCH_STEP_ID}}` | existing OpenMES IDs from the user; the issue type must be non-blocking; batch step optional | all, if `{{OPENMES_ENABLED}}=yes` |
| `{{OPENMES_SOURCE_ID}}`, `{{OPENMES_SOURCE_MODE}}` | station/line identifier; publisher `mode` (`vision` \| `ts` \| `multimodal`, the last also for `vllm`/`agentic`) | all, if `{{OPENMES_ENABLED}}=yes` |
| `{{OPENMES_INPUT_TOPIC}}` | the one topic the publisher reads: `{{FUSION_TOPIC}}` (fused modes), `{{ALERT_TOPIC}}` (`ts`), `{{VISION_TOPIC}}` (`vision`) | all, if `{{OPENMES_ENABLED}}=yes` |
| `{{OPENMES_DEFECT_LABELS}}`, `{{OPENMES_MIN_CONFIDENCE}}` | vision defect labels (never the good/normal class) and minimum confidence (default `0.8`) | `vision`, if `{{OPENMES_ENABLED}}=yes` |
