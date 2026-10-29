# Skill catalog — business objective → open-edge-platform skill

Curated routing table for the `metro-ai-app-builder` orchestrator. Map the
user's **business objective** (Step 1 answers) to a **primary** skill and any
**supporting** skills, then plan + delegate. Verify skill names and source
repositories against the upstream `skills-config.json` in
[`DISCOVERY.md`](DISCOVERY.md); the index includes skills in multiple repos,
not only `open-edge-platform/skills`.

> Install external delegate skills from the configured `repo`, `ref`, and
> `path` in `skills-config.json` (for example,
> `npx skills@1.5.23 add https://github.com/<owner>/<repo>/tree/<ref>/<path>/<name>`).
> The Metro recipe is already available in this monorepo as `metro-ai-app-recipe`.

## 1. Computer vision — detect / count / track / alert on camera feeds

| If the user wants… | Primary skill | Supporting |
|---|---|---|
| A full **end-to-end analytics stack** (live annotated video + dashboard + alerts) for detection/classification/counting/zone-alerting on any vertical (smart city, retail, industrial, PPE, parking, healthcare…) | **`metro-ai-app-recipe`** *(same monorepo)* — production mode (`MODE=production`, the default) | `model-download-user` (custom IR), `dlstreamer-coding-agent` (custom pipeline JSON) |
| A **quick demo / simple app** — a single lightweight app (no full stack) that just proves a model runs and emits inference: a simple DL Streamer pipeline or sample app | **`dlstreamer-coding-agent`** | `model-download-user` (model IR) |
| **Multi-camera / spatial** cross-camera tracking & scene fusion (smart-intersection style, whole-scene view) | **`scenescape-setup`** — routed directly for multi-camera spatial analytics | `metro-ai-app-recipe` (optional detection front-end), `model-download-user` |
| A **custom vision pipeline / sample app in code** (Python/C/C++/GStreamer): detection, classification, tracking, VLM, recording, custom elements | **`dlstreamer-coding-agent`** | `model-download-user` |
| **Migrate / convert / port** an existing **NVIDIA DeepStream** (or raw GStreamer) pipeline to an equivalent **Intel DL Streamer** pipeline/app | **`dlstreamer-coding-agent`** | `model-download-user` (equivalent IR model) |
| Deploy or operate the **DL Streamer Pipeline Server** as a REST service, including managing pipeline instances | **`dlsps-user`** | `model-download-user` (if a model must be prepared) |

Deliverable shape: *end-to-end solution* (Compose stack) for
`metro-ai-app-recipe` (production mode); *quick single app / PoC* for
`dlstreamer-coding-agent`; *multi-camera solution* for the `scenescape-setup`
path. Map the Step 1 **packaging** answer (Q4) to the route: `demo`/`function`/
`port` (quick single app) → `dlstreamer-coding-agent`; `microservice` (full
end-to-end stack) → `metro-ai-app-recipe`; and the Step 1 **camera-coverage**
answer to Scenescape: a multi-camera whole-scene view → `scenescape-setup`.

Use `dlsps-user` for operating the standalone pipeline-server service; use
`metro-ai-app-recipe` for the integrated analytics stack, and
`dlstreamer-coding-agent` when authoring or migrating pipeline code.

### 1a. API recipe → delegate routing (Step 1, Q8)

The **API-recipe** answer selects the media/analytics delegate and **takes
precedence** for these use cases (full detail in [`API_RECIPES.md`](API_RECIPES.md)):

| API recipe | Primary | Supporting |
|---|---|---|
| **DL Streamer (DLS)** — a DL Streamer pipeline / app | **`dlstreamer-coding-agent`** (the DLS skill) — **not** `metro-ai-app-recipe` | `model-download-user` (IR) |
| **OpenVINO + OpenCV** — minimal custom inference app | OpenVINO custom-code path (per OpenVINO docs; no dedicated skill) | `model-download-user` (IR) |
| **OVMS + FFmpeg** — model served by OVMS, FFmpeg media I/O | OVMS model-serving path (no dedicated skill) | `model-download-user` (OVMS-ready IR) |

> **DLS vs the recipe stack:** picking the **DL Streamer** API recipe routes to
> `dlstreamer-coding-agent`. The full end-to-end **stack**
> (`metro-ai-app-recipe`) is selected by the **packaging** axis
> (`microservice`), not by the DLS API-recipe answer — even though the recipe
> uses DL Streamer internally.

## 2. Conversational AI — chatbot / Q&A / RAG over documents

| If the user wants… | Primary skill | Notes |
|---|---|---|
| A **chatbot / RAG** over their documents on a single host (Docker Compose) with OpenVINO CPU/GPU or Ollama | **`chatqna-docker-deploy`** | Profile selection, env setup, health checks |
| The same **on Kubernetes** (Helm) | **`chatqna-helm-deploy`** | Translates Compose `setup_env.sh` → `values.yaml` |

## 3. Video understanding — search & summarize a video library

| If the user wants… | Primary skill | Supporting |
|---|---|---|
| Deploy the **Video Search & Summarization** app (summary / search / dual / unified) on Docker | **`vss-deploy`** | `multimodal-dataprep-user` (media ingest), `multimodal-embedding-serving-user` (embeddings) |
| The same **on Kubernetes** (Helm) | **`vss-deploy-helm`** | — |
| **Search** an indexed library with natural language ("find X", "when did Y happen") | **`vss-search-index`** | requires a search-capable VSS deploy |
| **Summarize** an ingested video | **`vss-summarize-video`** | requires a summary-capable VSS deploy |
| **Prepare / ingest** videos and images for retrieval (VDMS or Milvus; MinIO or local media storage) | **`multimodal-dataprep-user`** | feeds VSS / retrieval |
| **Embed** text/images/videos for similarity search (CLIP/SigLIP/… 19 models) | **`multimodal-embedding-serving-user`** | building block for retrieval apps |

Typical pipeline: `multimodal-dataprep-user` (prepare media) → `vss-deploy` (bring up) →
`vss-search-index` / `vss-summarize-video` (use).

## 4. Model preparation

| If the user wants… | Primary skill |
|---|---|
| **Download / convert** a model (HuggingFace, Ollama, Ultralytics, Geti, Pipeline Zoo; INT4/INT8; OVMS-ready IR; healthcare HLS models) | **`model-download-user`** |

Usually a **supporting** step for a deploy/build skill above.

## 5. Model training (computer vision)

| If the user wants… | Primary skill |
|---|---|
| **Discover** available models/recipes/tasks before training | **`getitune-discovering-models`** |
| **Prepare / point datasets** (COCO/YOLO/VOC/Datumaro) | **`getitune-preparing-datasets`** |
| **Train / fine-tune** a classifier/detector/segmentation/keypoint model | **`getitune-training-a-model`** |
| **Export** to OpenVINO IR / ONNX (FP32/FP16) | **`getitune-exporting-a-model`** |
| **Optimize / quantize** to INT8 (NNCF PTQ) | **`getitune-optimizing-a-model`** |
| **Run inference / evaluate** (PyTorch / OpenVINO / ONNX) | **`getitune-running-inference`** |
| Use the **Geti application** end-to-end via REST (project→annotate→train→deploy) | **`geti-using-the-pipeline`** |
| **Train / evaluate an anomaly-detection model** from image or video data | **`anomalib-training`** (optionally `anomalib-benchmarking` to compare model/dataset combinations) |

Typical training pipeline: `getitune-discovering-models` →
`getitune-preparing-datasets` → `getitune-training-a-model` →
`getitune-exporting-a-model` → `getitune-optimizing-a-model` →
`getitune-running-inference`. The exported/quantized IR can then feed
`metro-ai-app-recipe` or `dlstreamer-coding-agent` via `model-download-user`.

## 6. Robotics / Physical AI

| If the user wants… | Primary skill | Supporting |
|---|---|---|
| **Train / validate / test / predict** with Physical AI Studio policies | **`pai-train-policy`** | `pai-work-with-datasets` (LeRobot datasets) |
| **Benchmark** a trained policy in simulation | **`pai-benchmark-policy`** | — |
| **Export / validate** a trained policy for runtime | **`pai-export-policy`** | — |
| **Load / validate** an exported policy for runtime | **`pai-load-policy`** | — |
| **Run** an exported policy on a robot | **`pai-run-policy`** | `pai-configure-inference` (pre/post-processing) |

Typical robot pipeline: `pai-train-policy` (with `pai-work-with-datasets`) →
`pai-export-policy` → `pai-load-policy` → `pai-run-policy`. These current
skills cover policy training, export, and runtime; do not route implementation
of a new policy family or robot integration to a nonexistent skill.

## 7. Manufacturing / industrial applications

| If the user wants… | Primary skill | Supporting |
|---|---|---|
| A guided manufacturing-quality application from a business objective | **`manufacturing-ai-app-builder`** | It delegates to `manufacturing-app-recipe` for the manufacturing stack |
| An explicitly requested manufacturing analytics stack / recipe | **`manufacturing-app-recipe`** | — |

For manufacturing-specific objectives, hand off to the manufacturing builder
rather than treating the Metro vision recipe as a universal industrial route.

## 8. Edge platform install and operations

| If the user wants… | Primary skill |
|---|---|
| Install, start, stop, or remove OEP modules/profiles on an edge system | **`openedge-cli`** |
| Build a time-series analytics use case on the Time Series Analytics microservice | **`time-series-analytics-user`** |

## 9. UAV mission compute

| If the user wants… | Primary skill |
|---|---|
| Set up, operate, or troubleshoot the UAV Mission Compute SDK (PX4 telemetry, camera streaming, missions, or edge-AI demos) | **`uav-mission-compute-sdk`** |

## Routing heuristics

- **Verb + object** in the objective is the strongest signal:
  *detect/count/track + camera* → §1; *ask/answer + documents* → §2;
  *search/summarize + video* → §3; *download/convert + model* → §4;
  *train/fine-tune + dataset* → §5; *run/deploy + robot policy* → §6;
  manufacturing-quality app → §7; OEP module lifecycle / time-series analytics
  → §8; UAV Mission Compute SDK → §9.
- **Deployment target** picks the Docker vs Helm variant (chatqna, vss). For
  vision, the **packaging** answer (Q4) picks the route: a *demo / function /
  port* single app → **`dlstreamer-coding-agent`** (a single DL Streamer pipeline
  or sample app); a *microservice / full end-to-end* stack →
  **`metro-ai-app-recipe`** (production mode). The **API-recipe** answer (Q8)
  overrides for media/analytics — see §1a (DLS → `dlstreamer-coding-agent`;
  OV+OpenCV / OVMS+FFmpeg → custom-code paths).
- **Multi-camera / spatial** whole-scene tracking (a subject followed *across*
  cameras covering one physical space, smart-intersection style) → route
  **directly** to **`scenescape-setup`**; add `metro-ai-app-recipe` only if a
  per-camera detection front-end is also wanted.
- **"Custom model"** almost always adds `model-download-user` as a supporting
  step before a deploy/build skill.
- **Video retrieval preparation** uses `multimodal-dataprep-user`; do not use
  the retired VDMS-specific DataPrep skill name.
- **Anomaly detection** training routes to `anomalib-training`; use
  `getitune-*` for the general computer-vision training workflow.
- **Migrate / convert / port** verbs against **NVIDIA DeepStream** (or raw
  GStreamer) → **`dlstreamer-coding-agent`**: the user has an existing DeepStream
  pipeline and wants the equivalent **Intel DL Streamer** code. Add
  `model-download-user` when the NVIDIA model needs an OpenVINO IR equivalent.
- When two domains appear (e.g. *train then deploy*), sequence the skills and
  confirm the **whole pipeline** once in the plan.
- If no row matches, do **not** invent a skill — say so and offer the closest
  entry or a custom-code path.
