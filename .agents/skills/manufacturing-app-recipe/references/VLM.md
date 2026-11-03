<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# VLM explainability layer (`vllm` mode, and the foundation of `agentic`)

`vllm` mode adds an **on-demand, image-grounded explanation** of fused
verdicts on top of the `multimodal` stack. It mirrors the reference
`industrial-edge-insights-multimodal` `make up_vllm` deployment exactly:

| Service | Image | Role |
|---|---|---|
| `vllm-server` | `intel/vllm` (`${VLLM_IMAGE}`) | serves a vision-language model (VLM) through an OpenAI-compatible `/v1` API, optionally with a LoRA adapter |
| `multimodal-agentic-ui` | built from `{{STACK_DIR}}/ui-service/` (see [`UI_SERVICE.md`](UI_SERVICE.md)) | FastAPI UI. In `vllm` mode it serves only `/insights-ui/`: a paged table of fused verdicts with an **Explain** action |

There is **no** separate explainer service, no OVMS and no `model-download`
in `vllm` mode. Do not author a `vllm-explainer` container. The `ui-service`
makes the VLM call.

## How an explanation is produced (the Explain flow)

1. The user opens the vllm dashboard (`{{DASHBOARD_SLUG}}_vlm.json`). Its
   **VLLM Reasoning** panel is an iframe of `/insights-ui/`, served through
   the same nginx origin as Grafana.
2. `/insights-ui/api/data` lists recent `{{FUSION_MEASUREMENT}}` rows (default
   `fusion_result`), hiding rows whose labels match the vertical's
   non-actionable regex (reference: `No_Weld|No Label`). The user selects
   **one** row and clicks **Explain**.
3. `POST /insights-ui/api/explain` with `{"selected_times": ["<ISO-8601 row
   time>"]}` (exactly one entry) resolves:
   - the stored frame: `vision_timestamp` → the vision measurement row with
     tag `search_time = vision_timestamp` → `img_handle` → `GET
     ${OBJECT_STORE_URL}/buckets/${BUCKET_NAME}/<img_handle>.jpg` (base64
     data URL);
   - the sensor reading: the `{{SENSOR_MEASUREMENT}}-anomaly-data` row whose
     `time == timeseries_timestamp`.
4. It sends `system_prompt.json` + `[image, vertical-specific prompt +
   sensor values]` to `vllm-server` `/v1/chat/completions` with
   `model=${VLLM_ADAPTER_NAME}`, and renders the reply in the panel.

The explanation is supplemental and never changes `fused_decision`. The
data contract this flow depends on (measurement names, the `search_time`
tag, `img_handle`, the S3 key) is listed in
[`UI_SERVICE.md`](UI_SERVICE.md#data-contract). Fusion Analytics and DLSPS
must produce exactly these fields.

## Models (ask, never fabricate)

| Item | Host path | Notes |
|---|---|---|
| VLM base model | `configs/vllm/huggingface/<model-dir>` → `VLLM_MODEL_DIR=huggingface/<model-dir>` | a Hugging Face VLM the user names. Reference: `unsloth/Qwen3.5-2B` |
| LoRA adapter (optional) | `configs/vllm/models/<adapter-dir>` → `VLLM_ADAPTER_DIR=lora-adapters/<adapter-dir>/` | the reference adapter `Intel/qwen3.5-2b-vlm-weld-explainability-lora` was trained on the Intel Robotic Welding dataset. Reuse it only for weld. Other verticals use their own adapter, or **no adapter** |

Download with the reference's documented `hf download` commands into those
two folders (the user must accept the model license first). `check_models`
fails `up_vllm`/`up_agentic` if `configs/vllm/models` or
`configs/vllm/huggingface` is missing or empty.

**No adapter:** remove `--enable-lora` and `--lora-modules ...` from the
`vllm-server` command, keep `configs/vllm/models` as a non-empty
placeholder (or relax `check_models` to check only `huggingface`), and set
`VLLM_ADAPTER_NAME=${VLLM_SERVED_MODEL_NAME}` so the UI calls the base
model.

## Required `.env` keys (copy from the reference, adjust model names)

```
VLLM_IMAGE=intel/vllm:<pinned tag>       # reference: intel/vllm:0.21.0-ubuntu24.04
VLLM_SHM_SIZE=4g
VLLM_WORKER_MULTIPROC_METHOD=spawn
VLLM_MODEL_DIR=huggingface/{{VLM_MODEL_DIR}}
VLLM_SERVED_MODEL_NAME={{VLM_MODEL}}
VLLM_DTYPE=float16
VLLM_PORT=8000
VLLM_BLOCK_SIZE=64
VLLM_GPU_MEMORY_UTILIZATION=0.27         # share of GPU-addressable memory; tune per platform
VLLM_MAX_NUM_BATCHED_TOKENS=8192
VLLM_MAX_MODEL_LEN=8192
VLLM_TENSOR_PARALLEL_SIZE=1
VLLM_QUANTIZATION=fp8
VLLM_CLIENT_TEMPERATURE=1.5
VLLM_CLIENT_TOKEN=2048
VLLM_CLIENT_MIN_P=0.1
VLLM_ADAPTER_NAME={{VLM_ADAPTER_NAME}}   # = VLLM_SERVED_MODEL_NAME when there is no adapter
VLLM_ADAPTER_DIR=lora-adapters/{{VLM_ADAPTER_DIR}}/
VLLM_HOME_DIR=/home/ubuntu
VLLM_CACHE_DIR=.cache
```

Keep the reference `vllm-server` service definition: `HF_HUB_OFFLINE=1` /
`TRANSFORMERS_OFFLINE=1`, read-only root with tmpfs caches, `/dev/dri` plus the
render `group_add`, and `vllm serve ... --served-model-name ...
--enable-lora --lora-modules ${VLLM_ADAPTER_NAME}=...`.

## Hardware gate

- `vllm-server` runs on **Intel GPU only** (XPU, `fp8`). The reference
  validates Intel Core Ultra Series 3 (Panther Lake) iGPU with at least 32 GB RAM.
- Reuse the reference `check_hardware` target. It enforces Panther Lake;
  `PLATFORM_CHECK=false make up_vllm` skips it for CI/validation only. Surface
  this to the user during planning. On other hosts `vllm` mode is
  unsupported, and the stack should stay `multimodal`.
- First start takes about 10 minutes while the model loads. Warn the user;
  this is not a failure.

## Makefile target

`make up_vllm`: `check_hardware` → `check_models` → `check_env_variables` →
`validate_host_ip` → `down`, then:

```
export NGINX_PROFILE=vllm AGENTIC_UI_ENABLED=false MQTT_DISABLED=true
rm -f configs/grafana/provisioning/*.json   # reference Makefile step: clears the whole directory
cp configs/grafana/dashboards_jsons/{{DASHBOARD_SLUG}}_vlm.json configs/grafana/provisioning/{{DASHBOARD_SLUG}}.json
docker compose -f docker-compose.yml -f docker-compose-vllm.yml up -d
make upload_tar_file
```

That `rm -f .../*.json` is the reference Makefile's own, unmodified step —
it deletes any dashboard JSON already provisioned there, including manual
edits. Warn the user before the first `make up_vllm` (see `INSTALL.md` →
*Grafana dashboard swap*). If you ever write this cleanup yourself (rather
than relying on `make up_vllm`), scope it to the exact file you are about
to replace instead of a wildcard, confined to this stack's own generated
`configs/grafana/provisioning/` directory:

```
rm -f configs/grafana/provisioning/{{DASHBOARD_SLUG}}.json
```

## Completion criteria (`vllm` mode, in addition to the base `multimodal` criteria 1–9)

10. `vllm-server` is ready: `GET https://<HOST_IP>:${GRAFANA_PORT}/insights-ui/api/vllm/health`
    returns `{"accessible": true}`. The UI proxies `vllm-server`'s own
    health endpoint.
11. `https://<HOST_IP>:${GRAFANA_PORT}/insights-ui/` returns 200 through
    nginx, and the vllm dashboard's **VLLM Reasoning** iframe renders the
    fused-results table.
12. `POST /insights-ui/api/explain` with the `selected_times` of one
    defective fused row returns VLM text that references the image and the
    sensor values. Quote it verbatim in the final summary.
