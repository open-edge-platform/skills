---
name: update-skills-index
description: "Scan the open-edge-platform GitHub org for all SKILL.md files and regenerate the README.md skills index in this repository. Use when: a new skill has been added to any org repo, an existing skill description has changed, or the README index is suspected to be stale."
argument-hint: "Optional: a specific repo name to re-scan (e.g. 'anomalib'). Leave blank to scan the entire org."
---

# Update Skills Index

Regenerate the `README.md` in `open-edge-platform/skills` by discovering all `SKILL.md` files across the org and rebuilding the index table.

## When to Use

- A new skill has been added to any repository under `open-edge-platform`
- An existing skill's `name` or `description` frontmatter has been updated
- The README index is suspected to be out of date
- A repository has been added to or removed from the org

## Procedure

### Step 1 — Discover all SKILL.md files in the org

Use the GitHub code search API to find every `SKILL.md` in the org:

```bash
gh api search/code \
  --method GET \
  -f q='org:open-edge-platform filename:SKILL.md' \
  --jq '.items[] | {repo: .repository.full_name, path: .path}'
```

Group results by repository (`repo` field). For each unique repo, note:
- The repository full name (e.g. `open-edge-platform/anomalib`)
- The skills directory prefix (e.g. `.agents/skills/` or `.github/skills/`)
- The list of skill folder names

### Step 2 — Fetch frontmatter for each skill

For each discovered `SKILL.md`, fetch its content and parse the YAML frontmatter block (between the `---` delimiters) to extract:
- `name` — skill identifier
- `description` — one-sentence description

```bash
gh api repos/<owner>/<repo>/contents/<path-to-SKILL.md> \
  --jq '.content' | base64 -d
```

Parse with a simple approach: extract lines between the first `---` and second `---`, then read `name:` and `description:` values.

### Step 3 — Determine the default branch for each repo

```bash
gh api repos/open-edge-platform/<repo> --jq '.default_branch'
```

Use this branch name when constructing GitHub URLs for skill links.

### Step 4 — Also discover reusable skills in this repo

The `open-edge-platform/skills` repository itself contains reusable skills under `.github/skills/`. These go in the **Reusable Skills** section of README.md, separate from per-repo skills.

```bash
gh api repos/open-edge-platform/skills/contents/.github/skills \
  --jq '.[].name'
```

### Step 5 — Rebuild README.md

Regenerate `/home/vinod/repos/skills/README.md` (or clone the repo if running outside the local checkout) using this exact structure:

```markdown
# Open Edge Platform — Agent Skills Index

<intro paragraph>

---

## Reusable Skills (this repo)

<table of skills from open-edge-platform/skills itself>

---

## Skills by Repository

### [<repo-name>](<repo-url>) — <repo description>

Skills live in `<skills-path>` within the repo.

| Skill | Description |
|-------|-------------|
| [<name>](<full GitHub URL to SKILL.md>) | <description> |

---

<repeat for each repo that has skills, sorted alphabetically>

## Contributing a Skill

<keep the existing Contributing section unchanged>

---

*This index is maintained by the [update-skills-index](.github/skills/update-skills-index/SKILL.md) skill. Run it on demand to sync with the latest skills across the org.*
```

**Sorting rules:**
- Repos are sorted alphabetically by name
- Skills within a repo are listed in the order returned by the search API (effectively alphabetical by folder name)
- The `open-edge-platform/skills` reusable section always appears first, before per-repo sections

**Link format:**
- Skill name links to the raw `SKILL.md` on GitHub: `https://github.com/<owner>/<repo>/blob/<default_branch>/<path>`
- Repo header links to the repository root: `https://github.com/<owner>/<repo>`

**Repo description:**
- Use the GitHub API `description` field for the repo subtitle: `gh api repos/open-edge-platform/<repo> --jq '.description'`
- Truncate to ~80 chars if too long; omit if empty

### Step 6 — Commit the updated README

After writing the new README.md:

```bash
cd /path/to/skills-repo
git add README.md
git commit -m "chore: auto-update skills index

Scanned open-edge-platform org and refreshed all skill entries.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

If running as part of a PR workflow, create a branch and open a PR instead of pushing directly to the default branch.

## Output

A fully regenerated `README.md` committed to `open-edge-platform/skills` with:
- All current skills across the org indexed with correct links and descriptions
- The reusable skills section up to date
- The Contributing section preserved unchanged

## Notes

- The GitHub code search API may have a short lag (a few minutes) after new files are pushed before they appear in results. If a newly-added skill is missing, wait and retry.
- Skills in private repositories will not appear in search results unless the token has access to those repos.
- If a repo uses a non-standard path for skills (not `.github/skills/` or `.agents/skills/`), it will still be found via the `filename:SKILL.md` search.
