<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# UI service, dashboards and data contract (`vllm` and `agentic` modes)

Load this for `vllm` or `agentic`. It tells you how to carry the reference
`industrial-edge-insights-multimodal/ui-service/` and its two dashboards
over to a new vertical, so the generated stack looks and works like the
reference: the same three dashboards, the same **Explain** and **Run
Agentic Analysis** pages, and the same URLs.

## Copy, then adapt — build from source

- Copy `ui-service/{Dockerfile,requirements.txt,src/}` into
  `{{STACK_DIR}}/ui-service/`. Keep the `multimodal-agentic-ui` Compose
  service definition from the reference `docker-compose-vllm.yml`
  (port 5003, `REST_API_ROOT_PATH=/agentic-ui`, read-only root, tmpfs `/tmp`,
  healthcheck on `/health`).
- Build it locally with a stack-specific image name (for example
  `image: {{STACK_DIR_SLUG}}-ui:${STACK_IMAGE_TAG}` with a `build:` block).
  Do **not** reuse the prebuilt `intel/multimodal-agentic-ui` image. Its
  measurement names, sensor fields, prompts and titles are hard-coded for
  weld. The only exception is a weld stack that keeps **every** name in the
  data contract below identical to the reference, and the user explicitly
  wants the prebuilt image.
- Never expose the UI on its own host port. It is reached only through
  nginx (`/insights-ui/`, `/agentic-ui/`) and embedded in Grafana as an
  iframe from the same origin. This is why the reference's Run button works
  with no extra certificate prompt. See [`PROXY_UI.md`](PROXY_UI.md).

## Per-vertical edit list

Every item below contains weld-specific text or names in the reference.
Change each one for `{{OBJECT}}`; leave everything else as copied.

| File | What to change |
|---|---|
| `src/insights.py` → `api_explain` | `"vision-weld-classification-results"` → `{{VISION_MEASUREMENT}}`; `"weld-sensor-anomaly-data"` → `{{SENSOR_MEASUREMENT}}-anomaly-data`; the `sensor_text` bullet list → this vertical's `{{SENSOR_TAGS}}` with units; the user prompt ("Given this weld image ...") → this vertical's report request; the `"Weld image unavailable"` messages |
| `src/insights.py` → `fetch_rows` | `no_result_re` → this vertical's non-actionable labels (reference: `No_Weld\|No Weld\|No_Label\|No Label`) |
| `src/insights.py` → `get_seaweed_public_image_base_path` and `api_explain` | default `BUCKET_NAME` → `dlstreamer-pipeline-results/{{OBJECT}}` (must equal the DLSPS `s3_write` `bucket/folder_prefix`) |
| `src/system_prompt.json` | the expert persona and report sections for this vertical |
| `src/app.py` → `trigger_run` | `"video_filename": "welding"` → `"{{OBJECT}}"`; module docstring |
| `src/templates/{index,results,insights,detections}.html` | page `<title>`, `<h1>`, `<nav aria-label>`, footer: `"Multimodal Weld Defect Detection"` → `{{UI_TITLE}}` |
| `src/static/js/insights.js` | image `alt` text (`"Weld inspection at ..."`) |
| `Dockerfile` | `org.opencontainers.image.title` / `description` labels |
| `docker-compose-vllm.yml` → `multimodal-agentic-ui.environment` | `BUCKET_NAME`, `FUSION_MEASUREMENT` (if renamed), `VLLM_ADAPTER_NAME`; add `USE_CASE_ID: {{USE_CASE_ID}}` |

After editing, check that `grep -rni weld ui-service/` returns nothing
(unless the vertical *is* welding), then build the image.

## Data contract

The Explain flow (`/insights-ui/api/explain`) and the agent read these
exact names. Fusion Analytics, DLSPS and the TICKscript must produce them.

| Producer | Measurement / object | Required names |
|---|---|---|
| Fusion Analytics | `{{FUSION_MEASUREMENT}}` (default `fusion_result`) | tag `fusion_classification`; fields `fused_decision`, `fusion_confidence`, `mode`, `vision_classification`, `vision_confidence`, `vision_anomaly`, `vision_timestamp` (epoch ns), `timeseries_classification`, `timeseries_confidence`, `timeseries_anomaly`, `timeseries_timestamp` (epoch ns), `vision_rtsp_ts_diff_ms`, `frame_id` |
| Fusion Analytics | `{{VISION_MEASUREMENT}}` (reference `vision-weld-classification-results`) | **tag `search_time` = the RTP sender timestamp (ns) as a string**; fields `frame_id`, `img_handle` (plus label/confidence) |
| TICKscript `influxDBOut` | `{{SENSOR_MEASUREMENT}}-anomaly-data` | point `time` equal to the `timeseries_timestamp` Fusion stored; the `{{SENSOR_TAGS}}` fields the prompt lists |
| DLSPS `s3_write` | `buckets/dlstreamer-pipeline-results/{{OBJECT}}/<img_handle>.jpg` | `folder_prefix` = `{{OBJECT}}` = the UI's `BUCKET_NAME` suffix |

If any name differs, Explain returns `"... image unavailable"` (502) or
`"No sensor data found"` (404), and the agent produces empty reports.

## Dashboards — three files, same as the reference

| File (`configs/grafana/dashboards_jsons/`) | Schema | Used by | Content |
|---|---|---|---|
| `{{DASHBOARD_SLUG}}.json` | classic | `make up` | WebRTC iframe, sensor trend, fused-verdict table |
| `{{DASHBOARD_SLUG}}_vlm.json` | Grafana **v2** (`apiVersion: dashboard.grafana.app/v2`, `kind: Dashboard`, `spec.elements` + `GridLayout`) | `make up_vllm`, `make up_agentic` | WebRTC iframe, **VLLM Reasoning** iframe `src="/insights-ui/"`, sensor trend |
| `{{DASHBOARD_SLUG}}_agentic.json` | Grafana v2 | `make up_agentic` | one full-height iframe built from `window.location.origin + "/agentic-ui/"` |

Copy the reference's `weld_defect_detection_vlm.json` and
`weld_defect_detection_agentic.json`, then change only:

- `spec.title` (for example `{{DASHBOARD_TITLE}} Explainability Dashboard` / `{{DASHBOARD_TITLE}} - Agentic Dashboard`);
- `metadata.name` and, if present, `metadata.uid`, to new unique values;
  remove the reference's `metadata.resourceVersion`, `generation`,
  `labels` and `annotations` (they belong to the reference's Grafana instance);
- the camera iframe path `/samplestream/` → `/{{STACK_DIR}}-stream/` (the DLSPS WebRTC `peer-id`);
- the sensor panel's measurement and field (`weld-sensor-anomaly-data` /
  `"Primary Weld Current"`) → `{{SENSOR_MEASUREMENT}}-anomaly-data` / the primary `{{SENSOR_TAGS}}` field.

Keep the iframe paths `/insights-ui/` and `/agentic-ui/` unchanged.
Never replace an iframe with a relative `<a href="/...">` link inside a
Grafana text panel. Grafana's client-side router intercepts it and shows
"Page not found".
