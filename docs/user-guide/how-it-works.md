# How It Works

## Summary

This guide explains how agent skills are discovered, loaded, and kept up to date. For installation steps, refer to [Get Started](./get-started.md).

## Skill Loading

A **skill** is a `SKILL.md` file that contains YAML frontmatter and task-specific instructions. Coding agents (GitHub Copilot, Claude Code, OpenAI Codex) discover installed skills in their supported skill directories. Discovery rules vary by agent and version; recursive discovery of nested source directories is not universally guaranteed. When a user prompt matches a skill's `description` field, the agent can load that skill's instructions into its context automatically.

The `SKILL.md` frontmatter format:

```yaml
---
name: my-skill-name
description: >
  One or more sentences that describe when to trigger this skill.
  Agents use this text for semantic matching against user prompts.
---
```

## Skills Directory Layout

### Source catalog

This repository groups skills by product:

```text
.agents/skills/<product-slug>/<skill-name>/SKILL.md
```

The product slug comes from the `slug` field in `skills-config.json`. A product
directory is only a container; each skill keeps its existing directory name
and frontmatter `name`. The configuration's upstream `path` and `ref` still
identify the original source location and revision, not the local product group.

### Installed agent layout

Install the catalog into a **separate consumer project**, rather than relying on
an agent to discover nested skills directly in this checkout. `npx skills`
discovers the source catalog and installs skills using their unchanged names,
without the product-directory level.

Project-level skills installed by `npx skills` use the flat layout
`.agents/skills/<skill-name>/SKILL.md`, with agent-specific links or copies as
appropriate. The `--agent universal` flag restricts installation to
`.agents/skills/` only, avoiding agent-specific directories.

```
.agents/
└── skills/
    ├── dlstreamer-coding-agent/
    │   └── SKILL.md
    ├── vss-deploy/
    │   └── SKILL.md
    └── ...
```

## skills-lock.json

Each `npx skills add` or `npx skills update` writes a `skills-lock.json` alongside the installed skills. This file records the source repository, branch/ref, and exact skill path for every installed skill.

## Supporting Resources

- [Get Started](./get-started.md)
