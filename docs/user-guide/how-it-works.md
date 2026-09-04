# How It Works

## Summary

This guide explains how agent skills are discovered, loaded, and kept up to date. For installation steps, refer to [Get Started](./get-started.md).

## Skill Loading

A **skill** is a `SKILL.md` file that contains YAML frontmatter and task-specific instructions. Coding agents (GitHub Copilot, Claude Code, OpenAI Codex) scan their configured skill directories on startup and index every installed `SKILL.md`. When a user prompt matches a skill's `description` field, the agent injects that skill's instructions into its context automatically — no explicit invocation needed.

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

Skills installed by `npx skills` land in `.agents/skills/<skill-name>/SKILL.md` relative to the project or global config root. The `--agent universal` flag restricts installation to `.agents/skills/` only, avoiding agent-specific subdirectories.

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
