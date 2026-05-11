# Open Edge Platform — Agent Skills Index

This repository is the central hub for **External facing agent skills** to be used by the customers.

A **skill** is a `SKILL.md` file that gives a coding agent focused, task-specific instructions. When a prompt matches a skill's description, the agent loads that skill's guidance automatically.

---

## Customer-Facing Skills

Skills designed for end-users building solutions with Open Edge Platform products.

### [dlstreamer](https://github.com/open-edge-platform/dlstreamer) — Deep Learning Streamer

Skills live in `.github/skills/` within the repo.

| Skill | Description |
|-------|-------------|
| [dlstreamer-coding-agent](https://github.com/open-edge-platform/dlstreamer/blob/main/.github/skills/dlstreamer-coding-agent/SKILL.md) | Build new DL Streamer video-analytics applications (Python or GStreamer command line). Use when the user describes a vision AI pipeline, wants to create a new sample app, combine elements from existing samples, add detection/classification/VLM/tracking/alerts/recording to a video pipeline, or create custom GStreamer elements in Python |

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
