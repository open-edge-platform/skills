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

Each `npx skills add` or `npx skills update` writes a `skills-lock.json` alongside the installed skills. This file records the source repository, branch/ref, and exact skill path for every installed skill, enabling reproducible restores via `npx skills experimental_install`.

## Index Maintenance (CI Workflow)

The [`update-skills-index`](https://github.com/open-edge-platform/skills/blob/release-2026.2.0/.github/workflows/update-skills-index.yml) workflow keeps this repository's README and `.agents/skills/` directory in sync automatically. It:

- Runs on a **daily schedule** to pick up upstream skill changes.
- Can be triggered **manually** via `workflow_dispatch` for on-demand syncs or dry-run previews.
- Reads [`skills-config.json`](../../skills-config.json) as the **single source of truth** for which skills to install.
- Installs or updates each skill via `npx skills add/update`, then rebuilds the skills table in the README between the `<!-- BEGIN SKILLS INDEX -->` / `<!-- END SKILLS INDEX -->` sentinels.

### Reconciliation Logic

On each run the workflow:

1. **Removes** skills that are no longer in `skills-config.json` or whose configured source (repo / ref / path) has changed.
2. **Batches** remaining installs/updates by `(repo, ref)` so each source repository is cloned only once per run, regardless of how many skills it contains.
3. **Verifies** each installed skill appears in `skills-lock.json` at the expected path; falls back to a path-scoped retry if a skill is nested too deeply for the CLI's default scan depth.

## Supporting Resources

- [Get Started](./get-started.md)