# Open Edge Platform — Agent Skills Index

This repository is the central hub for **reusable GitHub Copilot agent skills** across the [Open Edge Platform](https://github.com/open-edge-platform) organization.

A **skill** is a `SKILL.md` file that gives a Copilot coding agent focused, task-specific instructions. When a prompt matches a skill's description, the agent loads that skill's guidance automatically.

---

## Reusable Skills (this repo)

These skills are general-purpose and can be referenced from any repository in the org.

| Skill | Description |
|-------|-------------|
| [update-skills-index](.github/skills/update-skills-index/SKILL.md) | Scan the open-edge-platform org for all SKILL.md files and regenerate this README index on demand |

---

## Skills by Repository

### [anomalib](https://github.com/open-edge-platform/anomalib) — Anomaly Detection Library

Skills live in `.agents/skills/` within the repo.

| Skill | Description |
|-------|-------------|
| [testing](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/testing/SKILL.md) | Review/generate unit, integration, and regression test expectations |
| [models-data](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/models-data/SKILL.md) | Reviews anomalib model, data, callback, metric, and CLI integration conventions |
| [pr-workflow](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/pr-workflow/SKILL.md) | Reviews anomalib contributor workflow, PR title, branch naming, and quality gate expectations |
| [python-style](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/python-style/SKILL.md) | Reviews anomalib Python style, typing, imports, and public API conventions |
| [model-doc-sync](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/model-doc-sync/SKILL.md) | Keep anomalib model READMEs, docs pages, image assets, and benchmark/result references in sync |
| [docs-changelog](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/docs-changelog/SKILL.md) | Reviews anomalib docstrings, documentation updates, and changelog expectations |
| [third-party-code](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/third-party-code/SKILL.md) | Review/generate third-party code attribution, licensing, and notice requirements |
| [python-docstrings](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/python-docstrings/SKILL.md) | Enforces Google-style Python docstrings for Python code |
| [fastapi-rest-api-design](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/fastapi-rest-api-design/SKILL.md) | Designs and reviews REST APIs for FastAPI services using consistent resource naming, HTTP semantics, validation, security, and error handling patterns |
| [model-sample-image-export](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/model-sample-image-export/SKILL.md) | Export, validate, and publish model sample-result images into docs and reference them from README/docs pages |
| [benchmark-and-docs-refresh](https://github.com/open-edge-platform/anomalib/blob/main/.agents/skills/benchmark-and-docs-refresh/SKILL.md) | Run or continue model benchmarks, collect measured results, and refresh README/docs benchmark sections from generated artifacts |

---

### [dlstreamer](https://github.com/open-edge-platform/dlstreamer) — Deep Learning Streamer

Skills live in `.github/skills/` within the repo.

| Skill | Description |
|-------|-------------|
| [dlstreamer-coding-agent](https://github.com/open-edge-platform/dlstreamer/blob/master/.github/skills/dlstreamer-coding-agent/SKILL.md) | Build new DL Streamer video-analytics applications (Python or GStreamer command line). Use when the user describes a vision AI pipeline, wants to create a new sample app, combine elements from existing samples, add detection/classification/VLM/tracking/alerts/recording to a video pipeline, or create custom GStreamer elements in Python |

---

### [scenescape](https://github.com/open-edge-platform/scenescape) — Multimodal Object Tracking & Scene Analytics

Skills live in `.github/skills/` within the repo.

| Skill | Description |
|-------|-------------|
| [shell](https://github.com/open-edge-platform/scenescape/blob/main/.github/skills/shell/SKILL.md) | Shell scripting standards for SceneScape — shebang, style, and Bash guidelines |
| [python](https://github.com/open-edge-platform/scenescape/blob/main/.github/skills/python/SKILL.md) | Python coding standards for SceneScape — imports, indentation, patterns, and conventions |
| [makefile](https://github.com/open-edge-platform/scenescape/blob/main/.github/skills/makefile/SKILL.md) | Makefile standards for SceneScape — build targets, conventions, and patterns |
| [security](https://github.com/open-edge-platform/scenescape/blob/main/.github/skills/security/SKILL.md) | On-demand security review skill for SceneScape — code and configuration security guidance |
| [javascript](https://github.com/open-edge-platform/scenescape/blob/main/.github/skills/javascript/SKILL.md) | JavaScript coding standards for SceneScape — code style, conventions, and frontend patterns |
| [documentation-how](https://github.com/open-edge-platform/scenescape/blob/main/.github/skills/documentation-how/SKILL.md) | Procedures for updating SceneScape documentation — where to make changes and what to update for each type of modification |
| [testing](https://github.com/open-edge-platform/scenescape/blob/main/.github/skills/testing/SKILL.md) | Guide for creating SceneScape test cases — unit, functional, integration, UI, and smoke tests with positive and negative cases |
| [test-verification-gate](https://github.com/open-edge-platform/scenescape/blob/main/.github/skills/test-verification-gate/SKILL.md) | Runtime test verification gate for SceneScape — image freshness checks, rebuild-before-test requirements, and retry policy |

---

## Contributing a Skill

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

To add a skill to the org index:

1. Create a `SKILL.md` in your repo under `.github/skills/<skill-name>/SKILL.md` (or `.agents/skills/<skill-name>/SKILL.md`)
2. Include a YAML frontmatter block with at minimum `name` and `description`
3. Open a PR in this repo or run the `update-skills-index` skill to regenerate this README automatically

### SKILL.md frontmatter format

```yaml
---
name: your-skill-name
description: "One-sentence description of when and why to use this skill"
argument-hint: "Optional hint shown to users about what argument to provide"
---
```

---

*This index is maintained by the [update-skills-index](.github/skills/update-skills-index/SKILL.md) skill. Run it on demand to sync with the latest skills across the org.*
