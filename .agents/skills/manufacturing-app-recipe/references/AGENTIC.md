<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Agent-orchestration overlay (`agentic` mode only — wraps `VLM.md`)

Adds full agent orchestration on top of the bare LLM/VLM call described in
[`VLM.md`](VLM.md): a LangGraph meta-agent + worker agents replace
`vllm-explainer`'s single request/response call, and (optionally) usage/latency
metrics. **Off by default** — only build this when `{{DEPLOYMENT}}=agentic`
is explicitly chosen; `vllm` mode's bare call is sufficient for most
explainability needs.

**Do not re-implement the agent framework by hand** — this layer is an
overlay Compose file (reference: `docker-compose-agentic.yml` +
`docker-compose-vllm.yml`) composing existing microservices, not new code to
write from scratch. It **replaces** `vllm-explainer` from `VLM.md` — do not
run both the bare explainer and `apm-agent` at the same time.

Bring the stack up with `make up_agentic` — not `make up` or `make up_vllm`,
which omit the `docker-compose-agentic.yml` overlay these services are
defined in (see [`INSTALL.md`](INSTALL.md)'s *Makefile targets* section).

## Components (in addition to `apm-llm` + `model-download` from `VLM.md`)

| Service | Image | Role |
|---|---|---|
| `apm-agent` | `intel/agent-quality-handler` | LangGraph meta-agent + worker agents; subscribes to the same batch-complete MQTT event as `vllm-explainer` and orchestrates (possibly multi-step/tool-calling) calls to `apm-llm` to produce a richer explanation |
| (optional, `{{AGENT_METRICS}}=yes`) `metrics-manager` / `prometheus` | `intel/metrics-manager` | LLM-usage/latency metrics — skip for a minimal Agentic add-on |

## Wiring into Fusion Analytics

Identical integration point as `VLM.md`: `apm-agent`'s `STORAGE_SERVICE_URL`
points at Fusion Analytics' health/query API
(`http://ia-fusion-analytics:8080`), and it subscribes to the same
batch-complete MQTT topic (`MQTT_BATCH_TOPIC`, e.g. `apm/batch-complete`) —
Fusion Analytics itself publishes this event per FUSION.md's *Batching for
the explanation layer* section; the agent is detection-agnostic and never
subscribes to `{{FUSION_TOPIC}}` directly, only to this batch-complete
signal.

## Required env (extends `VLM.md`'s env)

```
LLM_MODEL_NAME={{LLM_MODEL_NAME}}
LLM_DEVICE={{LLM_DEVICE}}
LLM_WEIGHT_FORMAT={{LLM_WEIGHT_FORMAT}}
MODEL_PATH=/model/llm_model_agentic/openvino_models/${LLM_DEVICE_LOWER}/${LLM_WEIGHT_FORMAT_LOWER}/${LLM_MODEL_NAME}
MQTT_BATCH_TOPIC=apm/batch-complete
HUGGINGFACEHUB_API_TOKEN=   # required for gated HF models
```

`MODEL_PATH` is a **container** path, not a host path: `/model` is the
`apm-llm` mount of the stack-relative host dir `./configs/agentic/models`
(`- ./configs/agentic/models:/model:ro`), and `model-download` writes into
the same host dir via `- ./configs/agentic/models:/opt/models` with
`download_path=llm_model_agentic`. On the host the model therefore lands in
`{{STACK_DIR}}/configs/agentic/models/llm_model_agentic/openvino_models/...`
— never create or check `/model` at the host root.

`LLM_MODE=fallback` still applies — runs `apm-agent` without a live LLM
(pure rule-based templated explanation).

## GPU/device requirements

Same as `VLM.md` — `apm-llm` is the GPU/memory-heavy service either way;
`apm-agent` itself is lightweight (orchestration only, no inference).

## Completion criteria (`agentic` mode, in addition to `VLM.md`'s criteria 10–12)

13. `model-download` completes and `apm-llm`'s health check passes
    (`GET /v1/config` returns 200) before `apm-agent` is marked healthy.
14. An `apm/batch-complete` MQTT event produces one agent-orchestrated
    explanation output in `apm-agent`'s `OUTPUT_DIR`, quoted verbatim in the
    final summary. In the reference this event is published by `ui-service`
    when the user clicks **Run** (`POST /run`); for headless verification,
    publish the same payload by hand instead of going through the UI:
    `mosquitto_pub -h localhost -p 1883 -t apm/batch-complete -m '{"run_id":"1","status":"completed","device":"CPU","video_filename":"<name>","start_id":<ns>,"end_id":<ns>,"pipeline_status":"running"}'`
    with `start_id`/`end_id` spanning a window that has fused data.
15. If `{{AGENT_METRICS}}=yes`: `metrics-manager`/Prometheus reports at
    least one LLM-latency metric.
