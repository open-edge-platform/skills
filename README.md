# Open Edge Platform — Agent Skills Index

This repository is the central hub for **External facing agent skills** to be used by the customers
to build solutions with Open Edge Platform products.

A **skill** is a `SKILL.md` file that gives a coding agent focused, task-specific instructions. When a prompt matches a skill's description, the agent loads that skill's guidance automatically.

---

<!-- BEGIN SKILLS INDEX -->
<!-- Last updated: 2026-07-15 00:16 UTC -->
| Product | Skill | Skill Description |
|---------|-------|-------------------|
| [DL Streamer](https://github.com/open-edge-platform/dlstreamer) | [dlstreamer-coding-agent](https://github.com/open-edge-platform/dlstreamer/blob/main/.github/skills/dlstreamer-coding-agent/SKILL.md) ([Prompts](https://github.com/open-edge-platform/dlstreamer/blob/main/skills/dlstreamer-coding-agent/examples)) | Build new DL Streamer video-analytics applications (Python, C, C++ or GStreamer command line). Use when: user describes a vision AI pipeline, wants to create a new sample app, combine elements from existing samples, add detection/classification/VLM/tracking/alerts/recording to a video pipeline, or create custom GStreamer elements in Python or C++. Translates natural-language pipeline descriptions into working DL Streamer code using established design patterns. |
| [Model Download](https://github.com/open-edge-platform/edge-ai-libraries) | [model-download-user](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/.github/skills/model-download-user/SKILL.md) | Download and convert AI models using the Model Download microservice. Use this skill whenever a user wants to: download a model from HuggingFace, Ollama, Ultralytics, Geti, or Pipeline Zoo; convert a model to OpenVINO IR format for OVMS; download healthcare AI models (3D Pose, rPPG, AI-ECG) via the HLS plugin; set up the model download service; submit a download or conversion job via the REST API; or ask "how do I get model X working with OVMS?". Also trigger on phrases like "pull model", "download weights", "convert to int4", "OVMS-ready model", "prepare model for inference". |
| [Physical AI Runtime](https://github.com/openvinotoolkit/physicalai) | [physicalai-runtime-adding-a-camera-backend](https://github.com/openvinotoolkit/physicalai/blob/main/skills/capture/physicalai-runtime-adding-a-camera-backend/SKILL.md) | Adds or modifies a camera backend under physicalai.capture. Use when implementing a new Camera type, extending create_camera in src/physicalai/capture/factory.py, discovery helpers, optional pip extras for vendor SDKs, SharedCamera transport, or tests under tests/unit/capture with fake devices. |
| ↳ | [physicalai-runtime-adding-a-robot-integration](https://github.com/openvinotoolkit/physicalai/blob/main/skills/runtime/physicalai-runtime-adding-a-robot-integration/SKILL.md) | Adds or modifies robot hardware integrations under physicalai.robot. Use when implementing the Robot protocol, SO101 or Trossen WidowX drivers, robot connect helpers, verify.py checks, optional extras so101 or trossen, or tests in tests/unit/robot. |
| ↳ | [physicalai-runtime-configuring-inference-pipeline](https://github.com/openvinotoolkit/physicalai/blob/main/skills/inference/physicalai-runtime-configuring-inference-pipeline/SKILL.md) | Configures preprocessors, postprocessors, and runners around InferenceModel via manifest specs and ComponentRegistry. Use when editing physicalai.inference.preprocessors or postprocessors, manifest preprocessor/postprocessor lists, instantiate_component, registered type names, or class_path init_args for inference pipeline components. |
| ↳ | [physicalai-runtime-loading-exported-policies](https://github.com/openvinotoolkit/physicalai/blob/main/skills/inference/physicalai-runtime-loading-exported-policies/SKILL.md) | Loads and validates policies exported from Physical AI Studio for Runtime deployment. Use when working on InferenceModel, InferenceModel.from_pretrained, manifest.json, adapter auto-detection (onnx, openvino), backend/device kwargs, Hugging Face Hub policy packages, or the Runtime side of the export/load contract that Studio produces with physicalai export. |
| ↳ | [physicalai-runtime-running-policy-on-robot](https://github.com/openvinotoolkit/physicalai/blob/main/skills/runtime/physicalai-runtime-running-policy-on-robot/SKILL.md) | Runs exported policies on hardware with PolicyRuntime, execution modes, and physicalai run. Use when wiring PolicyRuntime, SyncExecution or RTC execution, runtime YAML configs, action queues, runtime callbacks, or docs/how-to/runtime run-policy-on-robot and execution modes. |
| [Physical AI Train](https://github.com/open-edge-platform/physical-ai-studio) | [physicalai-train-adding-a-policy](https://github.com/open-edge-platform/physical-ai-studio/blob/main/skills/library/physicalai-train-adding-a-policy/SKILL.md) | Adds or modifies a Physical AI Studio policy under library/src/physicalai/policies. Use when creating a new policy family with the config/model/policy split, registering it in the get_policy factory and package exports, or keeping a policy compatible with Lightning training and export. Covers Pi0.5, Pi0, ACT, GR00T, SmolVLA, and LeRobot-wrapped policies. |
| ↳ | [physicalai-train-benchmarking-a-policy](https://github.com/open-edge-platform/physical-ai-studio/blob/main/skills/library/physicalai-train-benchmarking-a-policy/SKILL.md) | Benchmarks a trained Physical AI Studio policy in a simulation gym and reports success metrics. Use when running physicalai benchmark, editing configs under library/configs/benchmark, adding or changing a Benchmark class in physicalai.benchmark, tuning rollout/episode/env settings, recording rollout videos, or interpreting results.json / results.csv. |
| ↳ | [physicalai-train-exporting-and-validating](https://github.com/open-edge-platform/physical-ai-studio/blob/main/skills/library/physicalai-train-exporting-and-validating/SKILL.md) | Exports and validates Physical AI Studio policies for Runtime deployment. Use when working on policy.export(...), the physicalai export CLI, the ONNX/OpenVINO/Torch/ExecuTorch backends, export metadata, numerical parity checks, or the Studio side of the export/load contract that Runtime consumes with InferenceModel(...). |
| ↳ | [physicalai-train-training-a-policy](https://github.com/open-edge-platform/physical-ai-studio/blob/main/skills/library/physicalai-train-training-a-policy/SKILL.md) | Trains, validates, tests, and runs prediction for Physical AI Studio policies via the library Lightning stack. Use when running physicalai fit/validate/test/predict, calling physicalai.train.Trainer and Policy APIs from Python, writing or editing YAML configs under library/configs, wiring a model + datamodule + trainer, resuming from a checkpoint, or debugging a training run. Covers ACT, Pi0, Pi0.5, GR00T, and SmolVLA. |
| ↳ | [physicalai-train-working-with-datasets](https://github.com/open-edge-platform/physical-ai-studio/blob/main/skills/library/physicalai-train-working-with-datasets/SKILL.md) | Works with Physical AI Studio datasets and Lightning datamodules built on the LeRobot format. Use when wiring physicalai.data.lerobot.LeRobotDataModule into a training config, choosing a repo_id, converting between the physicalai and lerobot data layouts, defining observation Features/FeatureType, setting normalization, or debugging batch shapes and dataloading. |
| [Scenescape](https://github.com/open-edge-platform/scenescape) | [scenescape-setup](https://github.com/open-edge-platform/scenescape/blob/feature/sscape-app-skill/.github/skills/scenescape-setup/SKILL.md) | Deploy a working Intel® SceneScape installation from scratch (outside the repo). Gathers user-provided streams, camera IDs, and scene name, then runs bootstrap through tracking verification via scripts/deploy_scenescape.sh. |
| [Video Search and Summarization](https://github.com/open-edge-platform/edge-ai-libraries) | [vss-search](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/video-search-and-summarization/.github/skills/vss-search/SKILL.md) | Search a video library with natural language via the VSS Pipeline Manager — upload a video (POST /videos), generate its embeddings (POST /videos/search-embeddings/{id}), then run a query (POST /search/query) with optional tag and time filters and read the ranked clip results. Use when the user says "search my videos", "find <thing> in the videos", "when did X happen", or wants to ingest/index a video for search. Requires a search-capable deployment (--search, --dual, or --unified). |
| ↳ | [vss-summarize](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/video-search-and-summarization/.github/skills/vss-summarize/SKILL.md) | Summarize a video through the VSS Pipeline Manager — start a summary pipeline with POST /summary (full required body), poll GET /summary/{stateId} until complete, then return the summary via GET /summary/{stateId}/raw. Use when the user says "summarize this video", "create a summary", "what happens in this video" (on an ingested video), or wants to run/inspect the summarization pipeline. Requires a summary-capable deployment (--summary, --dual, or --unified). |
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

1. Create a `SKILL.md` in your repo. Supported locations (in order of convention):

   | Scenario | Path |
   |----------|------|
   | Standard (GitHub Copilot / VS Code) | `.github/skills/<skill-name>/SKILL.md` |
   | Agent-agnostic | `.agents/skills/<skill-name>/SKILL.md` |
   | Mono-repo — product subfolder | `<product-folder>/.github/skills/<skill-name>/SKILL.md` |
   | Mono-repo — product subfolder (agent-agnostic) | `<product-folder>/.agents/skills/<skill-name>/SKILL.md` |
   | Mono-repo — repo root, named skill folder | `skills/<skill-name>/SKILL.md` |
   | Repo root, single skill | `SKILL.md` |

   Go through some of the guidelines documented at [SKILLS_GUIDE.md](./SKILLS_GUIDE.md) for defining, creating, validating and
   managing skills.
2. Include a YAML frontmatter block with at minimum `name` and `description`
3. Add an entry to `skills-config.json` in this repo, open a PR, and after it is merged, trigger the
   `update-skills-index` workflow to install it and update this README

### SKILL.md frontmatter format

```yaml
---
name: your-skill-name
description: "One-sentence description of when and why to use this skill"
argument-hint: "Optional hint shown to users about what argument to provide"
---
```
