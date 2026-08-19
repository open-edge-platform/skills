# Open Edge Platform — Agent Skills Index

This repository is the central hub for **External facing agent skills** to be used by the customers
to build solutions with Open Edge Platform products.

A **skill** is a `SKILL.md` file that gives a coding agent focused, task-specific instructions. When a prompt matches a skill's description, the agent loads that skill's guidance automatically.

---

<!-- BEGIN SKILLS INDEX -->
<!-- Last updated: 2026-08-19 00:04 UTC -->
| Product | Skill | Skill Description |
|---------|-------|-------------------|
| [Chat Question and Answer](https://github.com/open-edge-platform/edge-ai-libraries) | [chatqna-docker-deploy](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/chatqna-docker-deploy) | Deploy Chat Question-and-Answer Core with Docker Compose (OpenVINO CPU, OpenVINO GPU, or Ollama CPU), including env setup, profile selection, startup verification, health checks, and teardown. Use this skill when the user says "deploy chatqna core", "start chatqna container", "run compose", "openvino gpu deploy", or "ollama deploy". |
| ↳ | [chatqna-helm-deploy](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/chatqna-helm-deploy) | Deploy Chat Question-and-Answer Core to Kubernetes using Helm (OpenVINO CPU, OpenVINO GPU, or Ollama), including values.yaml configuration, helm install/upgrade, deployment verification, uninstall, and translation from Docker Compose setup_env.sh variables into Helm override values. Use this skill  when the user says "deploy chatqna core to kubernetes", "helm install chatqna-core", "configure values.yaml", "convert compose config to helm", or "translate setup_env.sh to chart values". |
| [DL Streamer](https://github.com/open-edge-platform/dlstreamer) | [dlstreamer-coding-agent](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/dlstreamer-coding-agent) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/dlstreamer-coding-agent/example-prompts)) | Build new DL Streamer video-analytics applications (Python, C, C++ or GStreamer command line). Use when: user describes a vision AI pipeline, wants to create a new sample app, combine elements from existing samples, add detection/classification/VLM/tracking/alerts/recording to a video pipeline, or create custom GStreamer elements in Python or C++. Translates natural-language pipeline descriptions into working DL Streamer code using established design patterns. |
| [DL Streamer Pipeline Server](https://github.com/open-edge-platform/edge-ai-libraries) | [dlsps-user](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/dlsps-user) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/dlsps-user/example-prompts)) | Deploy and operate DL Streamer Pipeline Server — a microservice that wraps DL Streamer pipelines behind a REST API for containerized, no-code operation. Use this skill whenever a user wants to: deploy the pipeline server via Docker Compose or Helm; start, stop, or monitor pipeline instances through the REST API; configure pipeline definitions in config.json; publish inference metadata over MQTT, OPC UA, InfluxDB, S3, or ROS2; set up GPU/NPU device access for the container; troubleshoot service-level issues (container startup, REST errors, port conflicts). This skill is NOT for writing new DL Streamer applications or custom GStreamer code — use the dlstreamer-coding-agent skill for that. Trigger on phrases like "pipeline server", "DLSPS", "start pipeline via REST", "deploy video analytics microservice", "config.json pipeline definition". |
| [DataPrep microservice](https://github.com/open-edge-platform/edge-ai-libraries) | [vdms-dataprep-user](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vdms-dataprep-user) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vdms-dataprep-user/example-prompts)) | Deploy and consume the VDMS DataPrep video-ingestion stack (dataprep + VDMS vector DB + MinIO) — bring it up with setup.sh + docker compose (from a repo clone, or by fetching those same files from GitHub when no clone exists) using the prebuilt intel/vdms-dataprep image, then upload/ingest MP4s, add text-summary embeddings, and list/download/delete videos through the REST API at http://localhost:6007/v1/dataprep. Ingestion only: it does not answer search queries. Not for modifying the service's source — that is vdms-dataprep-dev. |
| [Geti](https://github.com/open-edge-platform/geti) | [geti-using-the-pipeline](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/geti-using-the-pipeline) | Use the Geti application end to end through its REST API — the project → dataset → annotate → train → deploy pipeline served by the FastAPI backend in `application/backend/`. Use when a user (not a contributor) wants to create a project, upload media, add annotations, launch a training or quantization job, track job status, configure a source → model → sink inference pipeline, and enable live inference. Covers the `/api/...` endpoints and the async job model, not backend code changes. |
| ↳ | [getitune-discovering-models](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/getitune-discovering-models) | Discover which models, recipes, and tasks the getitune library (the Geti training library) supports before training. Use when a user asks what models are available, how to list recipes, how to filter by task or name pattern, how `list_models(...)` and `getitune find` behave, or how to resolve the "model name matches multiple tasks" error. Covers classification, detection, instance/semantic segmentation, and keypoint detection recipes. |
| ↳ | [getitune-exporting-a-model](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/getitune-exporting-a-model) | Export a trained getitune model (the Geti training library) to a deployable format. Use when a user wants to run `engine.export(...)` or `getitune export`, choose between OpenVINO IR and ONNX, set FP32 vs FP16 precision with `ExportFormat` / `Precision`, or understand where exported artifacts are written and how they load back for inference. Covers the export/load contract between training and OpenVINO/ONNX inference. |
| ↳ | [getitune-optimizing-a-model](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/getitune-optimizing-a-model) | Optimize an exported getitune model (the Geti training library) with post-training quantization. Use when a user wants to run `OVEngine.optimize()` / `engine.optimize()` to produce an INT8 model via NNCF, understands calibration-set requirements, or needs to re-validate and run inference with a quantized model versus the original FP32/FP16 model. Covers OpenVINO NNCF post-training quantization and the accuracy/size trade-off. |
| ↳ | [getitune-preparing-datasets](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/getitune-preparing-datasets) | Prepare and point datasets at the getitune library (the Geti training library) for training, testing, and prediction. Use when a user asks which dataset formats are supported, how the `data=` argument of `create_engine(...)` / `--data_root` works, why format auto-detection fails, how to lay out COCO/YOLO/Pascal VOC/Datumaro-native data, how to use a zip archive, or how to pass an Ultralytics YOLO `data.yaml`. Covers Datumaro-based auto-detection and per-task data expectations. |
| ↳ | [getitune-running-inference](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/getitune-running-inference) | Run inference and evaluation with a getitune model (the Geti training library). Use when a user wants to call `engine.predict()` / `engine.test()` or `getitune predict` / `getitune test`, run inference with a PyTorch checkpoint versus an exported OpenVINO IR (`.xml`) or ONNX (`.onnx`) model, or understand how `OVEngine` loads deployed models via ModelAPI. Covers PyTorch, OpenVINO, and ONNX inference backends. |
| ↳ | [getitune-training-a-model](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/getitune-training-a-model) | Train a computer-vision model with the getitune library (the Geti training library) using its Python API or CLI. Use when a user wants to train, fine-tune, or evaluate a model with `create_engine(...)` and `engine.train()/engine.test()`, run `getitune train`/`getitune test`, pick or override a recipe under `getitune.recipe.<task>`, choose a device (cpu/gpu/xpu/cuda), warm-start from a checkpoint, or debug a training run. Covers classification, detection, instance/semantic segmentation, and keypoint detection. |
| [Metro AI Suite - Prompt Library](https://github.com/open-edge-platform/edge-ai-suites) | [metro-ai-apps-builder](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/metro-ai-apps-builder) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/metro-ai-apps-builder/example-prompts)) | Conversational orchestrator that turns a plain business objective into a working Intel Edge AI application. It OWNS the conversation: it asks only business questions (what outcome you want, your inputs, where it runs, your hardware) — never which framework, model, or device — then DISCOVERS the relevant skills from the open-edge-platform/skills catalog, proposes a plan, and only after you confirm builds the deliverable by DELEGATING to the right skill(s). USE FOR any "I want to <business outcome> on Intel edge" request: detect/count/track objects in camera feeds, spatial multi-camera analytics, video search & summarization, conversational Q&A / RAG over documents, multimodal embeddings, downloading/converting models, training a computer-vision model, or deploying a robot policy — when you do NOT already know which specific skill to run. DO NOT USE when the user already named a concrete skill (invoke that skill directly) or asks a pure code question with no deployable outcome. |
| [Metro AI Suite - Vision AI App Recipe](https://github.com/open-edge-platform/edge-ai-suites) | [metro-ai-apps-recipe](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/metro-ai-apps-recipe) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/metro-ai-apps-recipe/example-prompts)) | Build an end-to-end, vertical-agnostic computer-vision analytics stack on Intel hardware from a single streamlined Docker Compose deployment: DL Streamer Pipeline Server plus MediaMTX/WebRTC, Coturn, Mosquitto, Node-RED, Grafana, and Nginx. It streams live annotated video over WebRTC and flows detection metadata DLSPS->MQTT->Node-RED->Grafana, with an optional SceneScape multi-camera spatial-analysis path. USE FOR standing up an object-detection, classification, counting, or zone-alerting pipeline for any vertical (smart city/ITS, retail, industrial, logistics, healthcare, or a custom OpenVINO/ONNX model) where only the model, class filter, alert rule, and dashboard change. Also USE FOR a lightweight **demo/PoC** single application (no full stack) — a simple DL Streamer pipeline (via the `dlstreamer-coding-agent` skill) or a simple OpenVINO inference app (guided by the OpenVINO 2026 docs) selected via the mode question. DO NOT USE FOR non-Intel or cloud-only deployments, Prometheus/OpenTelemetry metrics stacks, or training and exporting models. |
| [Model Download](https://github.com/open-edge-platform/edge-ai-libraries) | [model-download-user](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/model-download-user) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/model-download-user/example-prompts)) | Download and convert AI models using the Model Download microservice. Use this skill whenever a user wants to: download a model from HuggingFace, Ollama, Ultralytics, Geti, or Pipeline Zoo; convert a model to OpenVINO IR format for OVMS; download healthcare AI models (3D Pose, rPPG, AI-ECG) via the HLS plugin; set up the model download service; submit a download or conversion job via the REST API; or ask "how do I get model X working with OVMS?". Also trigger on phrases like "download model", "download weights", "convert to int4", "OVMS-ready model", "prepare model for inference". |
| [Multimodal Embedding Serving Microservice](https://github.com/open-edge-platform/edge-ai-libraries) | [multimodal-embedding-serving-user](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/multimodal-embedding-serving-user) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/multimodal-embedding-serving-user/example-prompts)) | Deploy and consume the Multimodal Embedding Serving microservice — bring it up with setup.sh + docker compose (from a repo clone, or by fetching those same files from GitHub when no clone exists) using the prebuilt intel/multimodal-embedding-serving image, embed text/images/videos over REST on port 9777, choose among 19 models (CLIP/SigLIP/MobileCLIP/CN-CLIP/Blip2/ QwenText), or integrate in-process via the Python SDK wheel. Use when an app needs embeddings for similarity search or retrieval. Not for modifying the service's source — that is multimodal-embedding-serving-dev. |
| [Physical AI Runtime](https://github.com/openvinotoolkit/physicalai) | [physicalai-runtime-adding-a-camera-backend](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-runtime-adding-a-camera-backend) | Adds or modifies a camera backend under physicalai.capture. Use when implementing a new Camera type, extending create_camera in src/physicalai/capture/factory.py, discovery helpers, optional pip extras for vendor SDKs, SharedCamera transport, or tests under tests/unit/capture with fake devices. |
| ↳ | [physicalai-runtime-adding-a-robot-integration](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-runtime-adding-a-robot-integration) | Adds or modifies robot hardware integrations under physicalai.robot. Use when implementing the Robot protocol, SO101 or Trossen WidowX drivers, robot connect helpers, verify.py checks, optional extras so101 or trossen, or tests in tests/unit/robot. |
| ↳ | [physicalai-runtime-configuring-inference-pipeline](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-runtime-configuring-inference-pipeline) | Configures preprocessors, postprocessors, and runners around InferenceModel via manifest specs and ComponentRegistry. Use when editing physicalai.inference.preprocessors or postprocessors, manifest preprocessor/postprocessor lists, instantiate_component, registered type names, or class_path init_args for inference pipeline components. |
| ↳ | [physicalai-runtime-loading-exported-policies](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-runtime-loading-exported-policies) | Loads and validates policies exported from Physical AI Studio for Runtime deployment. Use when working on InferenceModel, InferenceModel.from_pretrained, manifest.json, adapter auto-detection (onnx, openvino), backend/device kwargs, Hugging Face Hub policy packages, or the Runtime side of the export/load contract that Studio produces with physicalai export. |
| ↳ | [physicalai-runtime-running-policy-on-robot](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-runtime-running-policy-on-robot) | Runs exported policies on hardware with PolicyRuntime, execution modes, and physicalai run. Use when wiring PolicyRuntime, SyncExecution or RTC execution, runtime YAML configs, action queues, runtime callbacks, or docs/how-to/runtime run-policy-on-robot and execution modes. |
| [Physical AI Train](https://github.com/open-edge-platform/physical-ai-studio) | [physicalai-train-adding-a-policy](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-train-adding-a-policy) | Adds or modifies a Physical AI Studio policy under library/src/physicalai/policies. Use when creating a new policy family with the config/model/policy split, registering it in the get_policy factory and package exports, or keeping a policy compatible with Lightning training and export. Covers Pi0.5, Pi0, ACT, GR00T, SmolVLA, and LeRobot-wrapped policies. |
| ↳ | [physicalai-train-benchmarking-a-policy](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-train-benchmarking-a-policy) | Benchmarks a trained Physical AI Studio policy in a simulation gym and reports success metrics. Use when running physicalai benchmark, editing configs under library/configs/benchmark, adding or changing a Benchmark class in physicalai.benchmark, tuning rollout/episode/env settings, recording rollout videos, or interpreting results.json / results.csv. |
| ↳ | [physicalai-train-exporting-and-validating](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-train-exporting-and-validating) | Exports and validates Physical AI Studio policies for Runtime deployment. Use when working on policy.export(...), the physicalai export CLI, the ONNX/OpenVINO/Torch/ExecuTorch backends, export metadata, numerical parity checks, or the Studio side of the export/load contract that Runtime consumes with InferenceModel(...). |
| ↳ | [physicalai-train-training-a-policy](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-train-training-a-policy) | Trains, validates, tests, and runs prediction for Physical AI Studio policies via the library Lightning stack. Use when running physicalai fit/validate/test/predict, calling physicalai.train.Trainer and Policy APIs from Python, writing or editing YAML configs under library/configs, wiring a model + datamodule + trainer, resuming from a checkpoint, or debugging a training run. Covers ACT, Pi0, Pi0.5, GR00T, and SmolVLA. |
| ↳ | [physicalai-train-working-with-datasets](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/physicalai-train-working-with-datasets) | Works with Physical AI Studio datasets and Lightning datamodules built on the LeRobot format. Use when wiring physicalai.data.lerobot.LeRobotDataModule into a training config, choosing a repo_id, converting between the physicalai and lerobot data layouts, defining observation Features/FeatureType, setting normalization, or debugging batch shapes and dataloading. |
| [Scenescape](https://github.com/open-edge-platform/scenescape) | [scenescape-setup](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/scenescape-setup) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/scenescape-setup/example-prompts)) | Deploy a working Intel® SceneScape installation from scratch (outside the repo). Gathers user-provided streams, camera IDs, scene name, and mapping choice, then runs bootstrap through tracking verification via scripts/deploy_scenescape.sh. Also handles re-running or resuming a single phase of an existing deployment on request (e.g. "recalibrate", "redo scene reconstruction", "resume bootstrap only") via the orchestrator's --phase flag. |
| [Video Search and Summarization](https://github.com/open-edge-platform/edge-ai-libraries) | [vss-deploy](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-deploy) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-deploy/example-prompts)) | Deploys and manages VSS through setup.sh and its Docker Compose overlays. Use this skill for local lifecycle tasks such as configuration, startup, mode changes, inspection, shutdown, data cleanup, and health checks. It supports summary, search, dual, and unified modes with GPU and vLLM variants. |
| ↳ | [vss-deploy-helm](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-deploy-helm) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-deploy-helm/example-prompts)) | Use this skill whenever a developer needs to deploy VSS to Kubernetes, helm install VSS, configure values.yaml for VSS, or run VSS on k8s with GPU/vLLM for the video-search-and-summarization sample app. This skill is especially useful when translating Docker Compose/setup.sh modes (--summary, --search, --summary-and-search/--unified, dual UI, ENABLE_VLLM, OVMS GPU/NPU) into the actual Helm chart override files and values keys. Prefer this skill for VSS Helm install/upgrade/troubleshooting even if the user only says “put VSS on k8s” or “make values.yaml for VSS”. |
| ↳ | [vss-search-index](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-search-index) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-search-index/example-prompts)) | Search a video library with natural language via the VSS Pipeline Manager - upload a video (POST /videos), generate its embeddings (POST /videos/search-embeddings/{id}), then run a query (POST /search/query) with optional tag and time filters and read the ranked clip results. Use when the user says "search my videos", "find <thing> in the videos", "when did X happen", or wants to ingest/index a video for search. Requires a search-capable deployment (--search, --dual, or --unified). |
| ↳ | [vss-summarize-video](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-summarize-video) ([Prompts](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-summarize-video/example-prompts)) | Summarize a video through the VSS Pipeline Manager - start a summary pipeline with POST /summary (full required body), poll GET /summary/{stateId} until complete, then return the summary via GET /summary/{stateId}/raw. Use when the user says "summarize this video", "create a summary", "what happens in this video" (on an ingested video), or wants to run/inspect the summarization pipeline. Requires a summary-capable deployment (--summary, --dual, or --unified). |
<!-- END SKILLS INDEX -->

> **Disclaimer:** The skills listed above are sourced from their respective product repositories as configured in [`skills-config.json`](skills-config.json). Each product team is solely responsible for the content, security scanning, licensing compliance, and validation of their own skills.

---

## Using Skills

Skills are installed using the [`skills` CLI](https://github.com/vercel-labs/skills), available via `npx`.

### Prerequisites

`npx` ships with **Node.js**. Install it from [nodejs.org](https://nodejs.org/) (LTS recommended) or via a version manager:

```bash
# macOS / Linux — using nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install --lts

# macOS — using Homebrew
brew install node

# Windows — download the installer from https://nodejs.org/
```

Verify your installation:

```bash
node --version   # v20.x or newer recommended
npm --version
npx --version
```

Once Node.js is installed, `npx skills` works without any extra install step.

There are two installation modes:

| Mode | Flag | Effect |
|------|------|--------|
| **Symlink** *(default)* | *(none)* | Creates symlinks in agent directories pointing to a shared location — updates propagate automatically |
| **Copy** | `--copy` | Copies files directly into each agent directory — self-contained, no shared state |

### Install all skills from this repo

```bash
# Symlink — interactive (recommended for local development)
npx skills add open-edge-platform/skills

# Symlink — non-interactive, all agents
npx skills add open-edge-platform/skills --all

# Copy — non-interactive, all agents (portable, no symlinks)
npx skills add open-edge-platform/skills --all --copy

# Copy — specific agent only (e.g. Claude Code)
npx skills add open-edge-platform/skills --agent claude-code --copy --yes
```

### Install a specific skill

```bash
# Symlink a single skill (interactive agent selection)
npx skills add open-edge-platform/skills --skill dlstreamer-coding-agent

# Copy a single skill to a specific agent
npx skills add open-edge-platform/skills --skill dlstreamer-coding-agent --agent claude-code --copy --yes

# Install directly from the skill's source repo
npx skills add open-edge-platform/dlstreamer --skill dlstreamer-coding-agent --copy --yes

# Install directly from a skill directory when the product repo uses a custom layout
npx skills add https://github.com/openvinotoolkit/physicalai/tree/main/skills/inference/physicalai-runtime-loading-exported-policies \
  --skill physicalai-runtime-loading-exported-policies --copy --yes
```

### List installed skills

```bash
npx skills list           # project-level skills
npx skills list -g        # globally installed skills
npx skills list --json    # machine-readable output
```

### Update skills to the latest version

```bash
npx skills update                          # update all project skills
npx skills update dlstreamer-coding-agent  # update a single skill
npx skills update -g                       # update all global skills
```

### Remove a skill

```bash
npx skills remove dlstreamer-coding-agent                              # interactive
npx skills remove dlstreamer-coding-agent --agent claude-code --yes   # targeted
```

### Restore skills from the lock file

If a repo already has a `skills-lock.json`, restore all pinned skills in one command:

```bash
npx skills experimental_install
```

> **Tip:** Use `--agent universal` to install into `.agents/skills/` only (no symlinks to other agent directories).

---

## Maintaining the Index

The [`update-skills-index`](.github/workflows/update-skills-index.yml) workflow keeps this README and the `.agents/skills/` directory in sync automatically. It:

- Runs on a schedule as configured to pick up upstream skill changes
- Can be triggered **manually** via `workflow_dispatch` for on-demand syncs or dry-run previews
- Reads [`skills-config.json`](skills-config.json) as the single source of truth for which skills to install
- Installs or updates each skill via `npx skills add/update`, then rebuilds the skills table in this README

---

## Contributing a Skill

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

To add a skill to the org index:

1. Create a `SKILL.md` in your repo with all the required artifacts. Supported locations (in order of convention):

   | Scenario | Path |
   |----------|------|
   | Standard (GitHub Copilot / VS Code) | `**/.github/skills/<skill-name>/SKILL.md` |
   | Agent-agnostic | `**/.agents/skills/<skill-name>/SKILL.md` |
   | Skills folder | `**/skills/<skill-name>/SKILL.md` |
   | Repo root, single skill | `SKILL.md` |

   Go through some of the guidelines documented at [SKILLS_GUIDE.md](./SKILLS_GUIDE.md) for defining, creating, validating and
   managing skills.

2. Evaluate and benchmark your skill using `tools/run_multi_cli_eval.py`. This
   runs your skill's `evals/evals.json` across GitHub Copilot CLI, Claude Code
   CLI, and OpenAI Codex CLI in one pass, grades each run with an LLM judge,
   and produces per-CLI and cross-CLI benchmark reports:

   ```bash
   python3 tools/run_multi_cli_eval.py \
     --evals-json /path/to/your-skill/evals/evals.json \
     --skill-path /path/to/your-skill \
     --workspace /tmp/your-skill-eval-run \
     --clis copilot,claude,codex \
     --configs with_skill,without_skill \
     --grader-cli copilot
   ```

   **Prerequisites** — at least one CLI must be installed and authenticated:
   - GitHub Copilot CLI: `npm install -g @github/copilot-cli`
   - Claude Code CLI: see [claude.ai/code](https://claude.ai/code)
   - OpenAI Codex CLI: `npm install -g @openai/codex`

   Also install skill-creator globally (used for grading and aggregation):

   ```bash
   npx skills add anthropics/skills --skill skill-creator \
     -a github-copilot -a claude-code -a codex -g
   ```

   Results are written to the workspace directory you specify:

   | File | What it contains |
   |------|-----------------|
   | `benchmark.md` | Cross-CLI comparison — which agent benefits most from the skill |
   | `<cli>/benchmark.md` | Per-CLI `with_skill` vs. `without_skill` pass rate, time, tokens |
   | `<cli>/eval-*/` | Per-eval transcripts, grading, and timing |

   See [`tools/README.md`](tools/README.md) for the full option reference,
   including how to run a subset of CLIs, pin specific models, skip grading,
   or point at non-default CLI binary paths.

3. Add an entry to `skills-config.json` in this repo and open a PR against `main`.

   **On every PR that touches `skills-config.json`**, the
   [`Check Skills Config`](.github/workflows/check-skills-config.yml) workflow
   runs automatically. It validates the config against its JSON schema and
   verifies that every newly added skill actually exists at the declared path in
   its source repository. **This check is a required status check — the PR
   cannot be merged until it passes.**

   Once the PR is merged, the
   [`Update Skills Index`](.github/workflows/update-skills-index.yml) workflow
   triggers automatically on the push to `main`. It installs or updates each
   skill via `npx skills add/update` and rebuilds the skills table in this
   README. The workflow also runs on a daily schedule to pick up upstream skill
   changes, and can be triggered manually via `workflow_dispatch` for on-demand
   syncs or dry-run previews.