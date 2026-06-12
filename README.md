# Open Edge Platform — Agent Skills Index

This repository is the central hub for **External facing agent skills** to be used by the customers
to build solutions with Open Edge Platform products.

A **skill** is a `SKILL.md` file that gives a coding agent focused, task-specific instructions. When a prompt matches a skill's description, the agent loads that skill's guidance automatically.

---

<!-- BEGIN SKILLS INDEX -->
<!-- Last updated: 2026-06-12 18:25 UTC -->
| Repository | Skill | Description |
|------------|-------|-------------|
| [dlstreamer](https://github.com/open-edge-platform/dlstreamer) | [dlstreamer-coding-agent](https://github.com/open-edge-platform/dlstreamer/blob/main/.github/skills/dlstreamer-coding-agent/SKILL.md) | Build new DL Streamer video-analytics applications (Python, C, C++ or GStreamer command line). Use when: user describes a vision AI pipeline, wants to create a new sample app, combine elements from existing samples, add detection/classification/VLM/tracking/alerts/recording to a video pipeline, or create custom GStreamer elements in Python or C++. Translates natural-language pipeline descriptions into working DL Streamer code using established design patterns. |
<!-- END SKILLS INDEX -->

---

## Contributing a Skill

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

To add a skill to the org index:

1. Create a `SKILL.md` in your repo under `.github/skills/<skill-name>/SKILL.md` (or `.agents/skills/<skill-name>/SKILL.md`)
2. Include a YAML frontmatter block with at minimum `name` and `description`
3. Add an entry to `skills-config.json` in this repo, then open a PR and post merge
   trigger the `update-skills-index` workflow to install it and update this README

### SKILL.md frontmatter format

```yaml
---
name: your-skill-name
description: "One-sentence description of when and why to use this skill"
argument-hint: "Optional hint shown to users about what argument to provide"
---
```

---

<!-- Last updated: 2026-06-12 18:13 UTC -->
*This index is maintained by the [update-skills-index](.github/workflows/update-skills-index.yml) workflow. Run it on demand or let the scheduled job keep it up to date.*
