# Release Notes: Skills

## Version 2026.2

**Release Date**: September 9, 2026

The first release of the Skills repository introduces a catalog of user-facing agentic skills for deploying, operating, and extending Open Edge Platform components.

**New**:

* **DL Streamer:** The `dlstreamer-coding-agent` skill guides creation of video analytics applications using Python, C, C++, or GStreamer.
* **Chat Question and Answer:** The `chatqna-docker-deploy` and `chatqna-helm-deploy` skills guide deployment and operation of ChatQnA Core with Docker Compose and Kubernetes.
* **Video Search and Summarization:** The `vss-deploy`, `vss-deploy-helm`, `vss-search-index`, and `vss-summarize-video` skills cover deployment, video indexing, semantic search, and video summarization workflows.
* **Multimodal Embedding Serving Microservice:** The `multimodal-embedding-serving-user` skill covers service deployment and embedding text, images, and videos through its REST API or Python SDK.
* **Multimodal DataPrep Microservice:** The `multimodal-dataprep-user` skill covers deployment, storage configuration, and ingestion and management of multimedia retrieval data.
* **Model Download:** The `model-download-user` skill guides downloading and converting models from supported sources into deployment-ready formats.
* **DL Streamer Pipeline Server:** The `dlsps-user` skill covers deploying the pipeline server and operating configured video analytics pipelines through its REST API.
* **Time Series Analytics Microservice:** The `time-series-analytics-user` skill guides deployment and creation of streaming and batch analytics use cases, including alerts and model inference.
* **Physical AI Train:** The `physicalai-train-adding-a-policy`, `physicalai-train-benchmarking-a-policy`, `physicalai-train-exporting-and-validating`, `physicalai-train-training-a-policy`, and `physicalai-train-working-with-datasets` skills cover the policy development lifecycle from datasets and training through benchmarking and export.
* **Physical AI Runtime:** The `physicalai-runtime-adding-a-camera-backend`, `physicalai-runtime-adding-a-robot-integration`, `physicalai-runtime-configuring-inference-pipeline`, `physicalai-runtime-loading-exported-policies`, and `physicalai-runtime-running-policy-on-robot` skills cover camera and robot integration, inference configuration, policy loading, and hardware execution.
* **Geti:** The `geti-using-the-pipeline` skill covers the project-to-deployment workflow, while the six `getitune-*` skills cover model discovery, dataset preparation, training, inference, export, and optimization.
* **SceneScape:** The `scenescape-setup` skill guides end-to-end installation, configuration, calibration, and verification of a SceneScape deployment.
* **Metro AI Suite Prompt Library:** The `metro-ai-apps-builder` skill translates a business objective into a complete Intel Edge AI application plan and delegates implementation to relevant skills.
* **Metro AI Suite Vision AI App Recipe:** The `metro-ai-apps-recipe` skill deploys a computer-vision analytics stack with live video, dashboards, and alerts from a video source and model.

**Improved**:

* **Index Maintenance:** The workflow now batches installs by `(repo, ref)` to avoid redundant clones and retries skill discovery by path for skills nested beyond the CLI's default scan depth.
* **Stale Skill Detection:** `update_skills_index.py` now detects stale skills from disk independently of `skills-lock.json`.
