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

## Skills Catalog

[`skills-config.yaml`](../../skills-config.yaml) is the single source of truth for
which upstream skills this repository synchronizes. It is separate from the YAML
frontmatter in each `SKILL.md`, which describes the skill to an agent.

Each product specifies `product`, `repo`, `ref`, `skills`, and an optional `path`.
Each skill specifies `name` and optionally its own `path`, which overrides the
product path. Paths identify the directory containing skill directories, not the
`SKILL.md` file itself. Skill names must be unique across the whole catalog.

### Authoring rules

- Preserve the existing list structure and use spaces, not tabs, for indentation.
- Comments are allowed; the first comment associates the catalog with
  [`skills-config.schema.json`](../../skills-config.schema.json) for compatible editors.
- Use a single document. Duplicate keys, anchors, aliases, merge keys, explicit
  YAML tags, and unknown fields are rejected.
- All names, refs, and paths must be strings. Quote numeric-looking refs,
  date-like values, and YAML boolean/null words such as `"on"`, `"yes"`, or `"null"`.
- Empty catalogs and malformed entries fail validation before any skills are
  removed or installed. Repository names, refs, and paths also undergo safety checks.
- Do not store credentials in the catalog.

### Local validation

From a checkout at `/home/runner/work/skills/skills`:

```bash
python3 -m pip install -r /home/runner/work/skills/skills/requirements.txt
python3 /home/runner/work/skills/skills/scripts/skills_config.py
python3 -m unittest discover -s /home/runner/work/skills/skills/tests -v
python3 /home/runner/work/skills/skills/scripts/update_skills_index.py --dry-run
```

Adjust the checkout prefix for your machine. The shared validator enforces both
the JSON Schema and the stricter catalog rules. The existing `check-jsonschema`
command also accepts this YAML file, but does not replace the shared validator.
Index sync and compliance reporting use the same loader and pinned dependencies.
Dry runs do not install or write files; README preview requires an existing
`skills-lock.json`, otherwise table generation is skipped.

### Catalog format and schema

Catalog readers accept only `.yaml` and `.yml` paths, including the index updater's
`--config` and `--base-config` options. Downstream automation should consume the
YAML catalog directly.

The schema remains [`skills-config.schema.json`](../../skills-config.schema.json).
JSON Schema describes the parsed data structure, not the catalog's file syntax,
so it validates YAML mappings and lists without a separate YAML schema. Both the
shared loader and `check-jsonschema` use this same schema.

CI compares the current catalog with the base commit's YAML catalog when present.
If the base commit predates the YAML catalog, CI checks **all** configured upstream
skills instead of using a baseline. Invalid base commits or malformed existing
base catalogs still fail validation.

## skills-lock.json

Each `npx skills add` or `npx skills update` writes a `skills-lock.json` alongside the installed skills. This file records the source repository, branch/ref, and exact skill path for every installed skill.

This machine-managed file stays JSON and remains ignored by Git. Evaluation and
validator JSON artifacts are also unchanged by the catalog migration.

## Supporting Resources

- [Get Started](./get-started.md)
