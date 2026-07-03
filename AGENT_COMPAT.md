# Agent Compatibility Reference

In-depth, agent-specific guidance for deploying skills across different coding
agents. Companion material to [SKILLS_GUIDE.md](SKILLS_GUIDE.md) — consult this
when you need configuration details beyond the summary table in Section 12.

## Contents

- [Companion Config Files and Token Budget](#companion-config-files-and-token-budget)
- [Monorepo Layout](#monorepo-layout)
- [Claude Code](#claude-code)
- [GitHub Copilot](#github-copilot)
- [Cursor](#cursor)
- [Codex](#codex)

---

## Companion Config Files and Token Budget

Every major agent has a config file that loads **on every session**, regardless
of which skills are active. That always-on cost reduces the context budget
available to your skill body and reference files.

| Config file | Agent | Loads when |
| --- | --- | --- |
| `CLAUDE.md` (repo + all parent dirs + `~/.claude/`) | Claude Code | Every session — all found files merged top-down |
| `.github/copilot-instructions.md` | GitHub Copilot | Every Copilot session in that repo |
| `.github/instructions/*.md` (`applyTo` glob) | GitHub Copilot | Only when matched files are in editor context |
| `.cursor/rules/*.mdc` (`alwaysApply: true`) | Cursor | Every Cursor session in that project |
| `.cursor/rules/*.mdc` (glob-matched) | Cursor | Only when matched files are in the edit context |
| `.cursor/rules/*.mdc` (manual) | Cursor | Only when the user explicitly @-mentions the rule |

### Four rules to live by

| Rule | Why it matters |
| --- | --- |
| **Keep companion configs focused** | Both the config and the active skill body are in context simultaneously. Stale rules waste budget on every request. |
| **Never duplicate across a config and a skill** | Duplication wastes tokens and creates contradictions. Configs → project conventions. Skills → reusable domain expertise. |
| **Put domain knowledge in a skill, not a config** | Companion configs always pay their token cost; skills only load when matched. Misplaced workflow instructions tax every session. |
| **Design skills to be authoritative for their domain** | When a companion config and an active skill conflict, the more specific instruction wins — skill guidance for its domain typically takes precedence. |

---

## Monorepo Layout

Place all repo-wide skills under a single root-level skills tree. Scope a skill
to a specific package through its `description` and `compatibility` fields, not
by nesting skill directories inside package folders.

```
monorepo/
├── .github/
│   ├── skills/
│   │   ├── api-skill/          ← description: "targets packages/api/**"
│   │   └── frontend-skill/     ← description: "targets packages/frontend/**"
│   ├── copilot-instructions.md ← Copilot: repo-wide, always loaded
│   └── instructions/
│       ├── api.md              ← Copilot: applyTo: "packages/api/**"
│       └── frontend.md         ← Copilot: applyTo: "packages/frontend/**"
├── CLAUDE.md                   ← Claude Code: repo-wide, always loaded
├── packages/
│   ├── api/
│   │   └── CLAUDE.md           ← Claude Code: loaded when cwd is in packages/api/
│   └── frontend/
│       └── CLAUDE.md           ← Claude Code: loaded when cwd is in packages/frontend/
└── .cursor/
    └── rules/
        ├── global.mdc          ← alwaysApply: true — repo-wide Cursor rules
        ├── api.mdc             ← globs: "packages/api/**"
        └── frontend.mdc        ← globs: "packages/frontend/**"
```

| Agent | Multi-level support | Mechanism |
| --- | --- | --- |
| Claude Code | Native (hierarchical) | All `CLAUDE.md` files from cwd up to root merged automatically |
| GitHub Copilot | Via `applyTo` globs | Root `copilot-instructions.md`; per-package scoping via `.github/instructions/*.md` |
| Cursor | Via `globs:` patterns | Per-package scoping via `globs:` in each `.cursor/rules/*.mdc` file |

**Scoping a skill to a package** — be explicit in the `compatibility` field:

```yaml
compatibility: Applies to packages/api/ — requires Node 22 and the internal @corp/api-sdk package.
```

This surfaces in `skills list` output and marketplace listings, so users know the target package before installing.

---

## Claude Code

| Setting | Guidance |
| --- | --- |
| `allowed-tools` | Declare tools the skill needs (e.g. `Bash(python:*) Read Write`) so Claude does not prompt for approval on each invocation. |
| Context window | 200K tokens — reference files are cheap. Prefer complete references over summaries; only trim if `skill-validator score evaluate` flags Token Efficiency. |
| `CLAUDE.md` | All `CLAUDE.md` files from cwd up to `~/.claude/` are merged before any skill activates. Their token cost is always paid — see [Companion Config Files and Token Budget](#companion-config-files-and-token-budget) for the content split. |
| Scripts | Claude Code invokes `scripts/` files directly via its bash tool. Bundle helpers the skill would otherwise generate on the fly — saves tokens and ensures consistent behaviour. |
| Instruction style | Claude handles multi-step reasoning well. Use numbered sub-steps with rationale; this outperforms flat directive lists for complex workflows. |

---

## GitHub Copilot

| Setting | Guidance |
| --- | --- |
| `allowed-tools` | Not supported. Omit the field — it has no effect and may confuse reviewers. |
| Description precision | Description-matching is the sole activation path. Use the most specific domain keywords users would type in a Copilot chat prompt. Vague descriptions mean the skill never loads. |
| `copilot-instructions.md` | Loaded every session before any skill activates. Its token cost is always paid — see [Companion Config Files and Token Budget](#companion-config-files-and-token-budget). |
| `instructions/*.md` with `applyTo` | A lightweight alternative to skills for file-type-specific guidance. Loads only when matching files are in editor context; no budget cost for unrelated tasks. |
| `SKILL.md` body size | Target under 300 lines. Copilot's context budget in inline chat is smaller than in agent mode; oversized skill bodies crowd out conversation history. |
| Surface testing | A skill that loads in VS Code agent mode may not trigger in GitHub.com chat due to surface-specific description matching. Run Stage 8 trigger evals against each target surface. |

---

## Cursor

| Setting | Guidance |
| --- | --- |
| Rule loading modes | `.cursor/rules/*.mdc` supports three modes: `alwaysApply: true` (always-on, budget cost every session), `globs:` pattern (loads when matched files are in context), manual (loads only on explicit @-mention). Prefer glob-matched or manual to minimise always-on cost. |
| `.cursorrules` | The legacy root-level file is still honoured but is being replaced by `.cursor/rules/*.mdc`. The two can coexist; migrate when practical. |
| `allowed-tools` | Not supported. Omit from frontmatter. |
| `SKILL.md` body size | Target under 350 lines. Cursor's context window varies by model backend. |

---

## Codex

| Setting | Guidance |
| --- | --- |
| Instruction style | Codex excels at code generation. Prefer concrete code examples in `assets/` and explicit output format specs over abstract principles — show the pattern, don't just describe it. |
| Scripts | Add `#!/usr/bin/env python3` shebangs and inline dependency comments (`# requires: requests`) so Codex can invoke scripts without reading additional context. |
| `SKILL.md` body size | Target under 400 lines. Codex performs best with dense, specific instructions rather than explanatory prose. |
