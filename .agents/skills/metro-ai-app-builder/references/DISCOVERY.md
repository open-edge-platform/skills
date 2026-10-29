# Discovering & installing skills at runtime

How the `metro-ai-app-builder` orchestrator confirms the live catalog, checks
what is already installed, and adds a delegate skill on demand. Load this in
Step 2 only when [`SKILL_CATALOG.md`](SKILL_CATALOG.md) looks stale, a mapping is
ambiguous, or a chosen delegate is not installed locally.

## 1. Prefer the curated catalog first

[`SKILL_CATALOG.md`](SKILL_CATALOG.md) is the fast path — it already maps
business objectives to skills. Only fall through to live discovery when it does
not resolve the objective or you need to confirm a skill still exists / its exact
name.

## 2. Check what is already installed in this session

A delegate may already be available (installed skills expose their own
`SKILL.md`). Look before adding:

```bash
# Skills the CLI has installed for the active agent(s)
npx skills@1.5.23 list 2>/dev/null || true

# Repos commonly used in these environments (adjust to your setup)
ls .github/skills 2>/dev/null                 # skills shipped in this component
ls ../metro-vision-ai-app-recipe/.github/skills 2>/dev/null # sibling recipe skill
ls ~/.copilot/skills ~/.claude/skills 2>/dev/null   # agent skill homes
```

`metro-ai-app-recipe` ships in this monorepo at
`../metro-vision-ai-app-recipe/.github/skills/metro-ai-app-recipe/`, so it
needs no external installation when that sibling component is present.

## 3. Refresh the live index (when the catalog may be stale)

The authoritative index of open-edge-platform skills is the repo's
`skills-config.json` plus each configured repository's skill directory.
`skills-config.json` provides the `repo`, `ref`, and `path`; an individual skill
may override `path`. Do not assume a skill is hosted in
`open-edge-platform/skills`.

Verify that configured paths still exist on the configured ref before installing.
The current index's Geti path override (`skills/library`) is stale: on
`open-edge-platform/geti@develop`, the `getitune-*` skill folders are under
`skills/getitune/`.

```bash
# Machine-readable product/skill index
curl -fsSL https://raw.githubusercontent.com/open-edge-platform/skills/main/skills-config.json
```

Read a candidate skill's `description` (its `SKILL.md` frontmatter) from the
configured `repo`/`ref` and skill-specific `path` (falling back to the product
`path`) to confirm it fits the objective before you commit to it in the plan:

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>/<name>/SKILL.md \
  | sed -n '1,25p'
```

Match on the `description` "Use this skill when…" trigger phrases — that is what
each skill author wrote to signal relevance.

## 4. Add a delegate skill on demand (Step 5 only, after confirmation)

Do not install anything during discovery/planning. After the user approves the
plan, add each not-yet-installed delegate:

```bash
# Use the skill's repo/ref/path/name from skills-config.json
npx skills@1.5.23 add https://github.com/<owner>/<repo>/tree/<ref>/<path>/<skill-name>

# For example, DL Streamer's coding agent:
npx skills@1.5.23 add https://github.com/open-edge-platform/dlstreamer/tree/main/.github/skills/dlstreamer-coding-agent
```

Use the configured `repo`, `ref`, and `path` (including a per-skill path
override) to install or inspect the exact skill source. Current delegates are
distributed across repositories such as `open-edge-platform/edge-ai-libraries`,
`open-edge-platform/geti`, `open-edge-platform/physical-ai-studio`,
`openvinotoolkit/physicalai`, `open-edge-platform/scenescape`,
`open-edge-platform/manufacturing-ai-suite`, and
`open-edge-platform/federal-and-aerospace-ai-suite`,
`open-edge-platform/anomalib`.

## 5. Fallbacks

- **`npx` unavailable** → read the skill's `SKILL.md` directly from GitHub (raw
  URL above) and follow it in-context, or ask the user to install Node 20+.
- **Network blocked** → rely on [`SKILL_CATALOG.md`](SKILL_CATALOG.md) and any
  already-installed skills; state the limitation in the plan.
- **No match anywhere** → tell the user plainly; suggest the closest catalog
  entry or a custom-code path. Never fabricate a skill name.

## 6. Keeping the catalog in sync

When the upstream index changes, keep the curated mappings in
[`SKILL_CATALOG.md`](SKILL_CATALOG.md) aligned with current `skills-config.json`
skill names and sources. Keep the mapping **business-objective-first** (what the
user says → skill), not technology-first; the curated catalog need not list
every upstream skill.
