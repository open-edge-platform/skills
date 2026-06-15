# Open Edge Platform — Agent Skills Index

This repository is the central hub for **External facing agent skills** to be used by the customers
to build solutions with Open Edge Platform products.

A **skill** is a `SKILL.md` file that gives a coding agent focused, task-specific instructions. When a prompt matches a skill's description, the agent loads that skill's guidance automatically.

---

<!-- BEGIN SKILLS INDEX -->
<!-- Last updated: 2026-06-15 15:01 UTC -->
| Repository | Prompts | Skill | Description |
|------------|---------|-------|-------------|
| [dlstreamer](https://github.com/open-edge-platform/dlstreamer) | [Prompts](https://github.com/open-edge-platform/dlstreamer/blob/main/skills/dlstreamer-coding-agent/examples) | [dlstreamer-coding-agent](https://github.com/open-edge-platform/dlstreamer/blob/HEAD/.github/skills/dlstreamer-coding-agent/SKILL.md) | Build new DL Streamer video-analytics applications (Python, C, C++ or GStreamer command line). Use when: user describes a vision AI pipeline, wants to create a new sample app, combine elements from existing samples, add detection/classification/VLM/tracking/alerts/recording to a video pipeline, or create custom GStreamer elements in Python or C++. Translates natural-language pipeline descriptions into working DL Streamer code using established design patterns. |
<!-- END SKILLS INDEX -->

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

## Contributing a Skill

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

To add a skill to the org index:

1. Create a `SKILL.md` in your repo under `.github/skills/<skill-name>/SKILL.md` (or `.agents/skills/<skill-name>/SKILL.md`)
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