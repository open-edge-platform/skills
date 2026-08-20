# Skill Compliance Report

**Generated:** 2026-08-20 03:20:38 UTC &nbsp;|&nbsp; **Run:** [32327722082](https://github.com/open-edge-platform/skills/actions/runs/32327722082)

## Executive Summary

| Total Skills | Evaluation Tests | Skills with Benchmarks |
|:---:|:---:|:---:|
| 31 | 94 | 14 |

## Component Summary

| Component | Number of Skills | Skills |
|---|:---:|---|
| **Chat Question and Answer** | 2 | chatqna-docker-deploy, chatqna-helm-deploy |
| **DL Streamer** | 1 | dlstreamer-coding-agent |
| **DL Streamer Pipeline Server** | 1 | dlsps-user |
| **DataPrep microservice** | 1 | vdms-dataprep-user |
| **Geti** | 7 | geti-using-the-pipeline, getitune-discovering-models, getitune-exporting-a-model, getitune-optimizing-a-model, getitune-preparing-datasets, getitune-running-inference, getitune-training-a-model |
| **Metro AI Suite - Prompt Library** | 1 | metro-ai-apps-builder |
| **Metro AI Suite - Vision AI App Recipe** | 1 | metro-ai-apps-recipe |
| **Model Download** | 1 | model-download-user |
| **Multimodal Embedding Serving Microservice** | 1 | multimodal-embedding-serving-user |
| **Physical AI Runtime** | 5 | physicalai-runtime-adding-a-camera-backend, physicalai-runtime-adding-a-robot-integration, physicalai-runtime-configuring-inference-pipeline, physicalai-runtime-loading-exported-policies, physicalai-runtime-running-policy-on-robot |
| **Physical AI Train** | 5 | physicalai-train-adding-a-policy, physicalai-train-benchmarking-a-policy, physicalai-train-exporting-and-validating, physicalai-train-training-a-policy, physicalai-train-working-with-datasets |
| **Scenescape** | 1 | scenescape-setup |
| **Video Search and Summarization** | 4 | vss-deploy, vss-deploy-helm, vss-search-index, vss-summarize-video |

## Skill Details

| Skill Name | Component | Evals Passed | Skill Uplift | skill-validator metrics | skill-spector vulnerabilities | Example Prompts |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **chatqna-docker-deploy** | Chat Question and Answer | 8/12 | +76pp | ❌ Fail<br>Warnings: 1<br>Total Tokens: 1410 | ✅ No vulnerabilities reported | N/A |
| **chatqna-helm-deploy** | Chat Question and Answer | 10/12 | +77pp | ❌ Fail<br>Warnings: 1<br>Total Tokens: 2554 | ✅ No vulnerabilities reported | N/A |
| **dlsps-user** | DL Streamer Pipeline Server | 1/2 | +62pp | ✅ Pass<br>Total Tokens: 5948 | 🟠 1H | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/dlsps-user/example-prompts) |
| **dlstreamer-coding-agent** | DL Streamer | 2/7 | +30pp | ✅ Pass<br>Total Tokens: 28674 | 🟡 3M | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/dlstreamer-coding-agent/example-prompts) |
| **geti-using-the-pipeline** | Geti | N/A | N/A | ❌ Fail<br>Warnings: 1<br>Total Tokens: 1092 | ✅ No vulnerabilities reported | N/A |
| **getitune-discovering-models** | Geti | N/A | N/A | ❌ Fail<br>Warnings: 1<br>Total Tokens: 634 | ✅ No vulnerabilities reported | N/A |
| **getitune-exporting-a-model** | Geti | N/A | N/A | ❌ Fail<br>Warnings: 1<br>Total Tokens: 764 | ✅ No vulnerabilities reported | N/A |
| **getitune-optimizing-a-model** | Geti | N/A | N/A | ❌ Fail<br>Warnings: 1<br>Total Tokens: 673 | ✅ No vulnerabilities reported | N/A |
| **getitune-preparing-datasets** | Geti | N/A | N/A | ❌ Fail<br>Warnings: 1<br>Total Tokens: 784 | 🟡 1M | N/A |
| **getitune-running-inference** | Geti | N/A | N/A | ❌ Fail<br>Warnings: 1<br>Total Tokens: 619 | ✅ No vulnerabilities reported | N/A |
| **getitune-training-a-model** | Geti | N/A | N/A | ❌ Fail<br>Warnings: 1<br>Total Tokens: 1296 | ✅ No vulnerabilities reported | N/A |
| **metro-ai-apps-builder** | Metro AI Suite - Prompt Library | N/A | N/A | ✅ Pass<br>Total Tokens: 5508 | ✅ No vulnerabilities reported | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/metro-ai-apps-builder/example-prompts) |
| **metro-ai-apps-recipe** | Metro AI Suite - Vision AI App Recipe | N/A | N/A | ❌ Fail<br>Errors: 1<br>Warnings: 1<br>Total Tokens: 18482 | 🟠 21H | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/metro-ai-apps-recipe/example-prompts) |
| **model-download-user** | Model Download | 5/8 | +38pp | ✅ Pass<br>Total Tokens: 8562 | 🟠 2H | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/model-download-user/example-prompts) |
| **multimodal-embedding-serving-user** | Multimodal Embedding Serving Microservice | 5/5 | +67pp | ✅ Pass<br>Total Tokens: 1652 | ✅ No vulnerabilities reported | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/multimodal-embedding-serving-user/example-prompts) |
| **physicalai-runtime-adding-a-camera-backend** | Physical AI Runtime | N/A | N/A | ✅ Pass<br>Total Tokens: 567 | ✅ No vulnerabilities reported | N/A |
| **physicalai-runtime-adding-a-robot-integration** | Physical AI Runtime | N/A | N/A | ✅ Pass<br>Total Tokens: 843 | ✅ No vulnerabilities reported | N/A |
| **physicalai-runtime-configuring-inference-pipeline** | Physical AI Runtime | N/A | N/A | ✅ Pass<br>Total Tokens: 530 | ✅ No vulnerabilities reported | N/A |
| **physicalai-runtime-loading-exported-policies** | Physical AI Runtime | N/A | N/A | ✅ Pass<br>Total Tokens: 1035 | ✅ No vulnerabilities reported | N/A |
| **physicalai-runtime-running-policy-on-robot** | Physical AI Runtime | N/A | N/A | ✅ Pass<br>Total Tokens: 548 | ✅ No vulnerabilities reported | N/A |
| **physicalai-train-adding-a-policy** | Physical AI Train | N/A | N/A | ✅ Pass<br>Total Tokens: 1518 | ✅ No vulnerabilities reported | N/A |
| **physicalai-train-benchmarking-a-policy** | Physical AI Train | N/A | N/A | ✅ Pass<br>Total Tokens: 1012 | ✅ No vulnerabilities reported | N/A |
| **physicalai-train-exporting-and-validating** | Physical AI Train | N/A | N/A | ✅ Pass<br>Total Tokens: 1348 | 🟡 1M | N/A |
| **physicalai-train-training-a-policy** | Physical AI Train | N/A | N/A | ✅ Pass<br>Total Tokens: 1446 | ✅ No vulnerabilities reported | N/A |
| **physicalai-train-working-with-datasets** | Physical AI Train | N/A | N/A | ✅ Pass<br>Total Tokens: 969 | ✅ No vulnerabilities reported | N/A |
| **scenescape-setup** | Scenescape | N/A | N/A | ✅ Pass<br>Total Tokens: 29600 | 🟠 5H, 🟡 23M | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/scenescape-setup/example-prompts) |
| **vdms-dataprep-user** | DataPrep microservice | N/A | N/A | ✅ Pass<br>Total Tokens: 1945 | ✅ No vulnerabilities reported | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vdms-dataprep-user/example-prompts) |
| **vss-deploy** | Video Search and Summarization | 2/6 | +67pp | ✅ Pass<br>Total Tokens: 9889 | 🟠 19H, 🟡 3M | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-deploy/example-prompts) |
| **vss-deploy-helm** | Video Search and Summarization | 1/7 | +54pp | ✅ Pass<br>Total Tokens: 7593 | 🟠 1H | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-deploy-helm/example-prompts) |
| **vss-search-index** | Video Search and Summarization | 5/7 | +69pp | ❌ Fail<br>Errors: 2<br>Total Tokens: 2482 | 🟠 2H, 🟡 1M | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-search-index/example-prompts) |
| **vss-summarize-video** | Video Search and Summarization | 2/7 | +46pp | ❌ Fail<br>Errors: 2<br>Total Tokens: 2156 | 🟠 2H | [View](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/vss-summarize-video/example-prompts) |
