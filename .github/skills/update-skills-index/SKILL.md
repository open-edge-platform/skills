---
name: update-skills-index
description: "Scan the open-edge-platform GitHub org for all SKILL.md files and regenerate the README.md skills index in this repository. Use when: a new skill has been added to any org repo, an existing skill description has changed, or the README index is suspected to be stale."
argument-hint: "Optional: a specific repo name to re-scan (e.g. 'anomalib'). Leave blank to scan the entire org."
---

# Update Skills Index

Regenerate the `README.md` in `open-edge-platform/skills` by discovering all `SKILL.md` files across the org — including this repo — and rebuilding the customer-facing index.

## When to Use

- A new skill has been added to any repository under `open-edge-platform`
- An existing skill's `name` or `description` frontmatter has been updated
- The README index is suspected to be out of date
- A repository has been added to or removed from the org

## Procedure

### Step 1 — Discover all SKILL.md files in the org

Use the GitHub code search API to find every `SKILL.md` in the org, **including `open-edge-platform/skills` itself**:

```bash
gh api --paginate search/code \
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

### Step 2b — Filter to customer-facing skills only

Present the full list of discovered skills to the user (across all repos, including `open-edge-platform/skills`) and ask them to confirm which are **customer-facing** (i.e., used by end-users building with Open Edge Platform products). Only the selected skills will appear in the README index.

Display the list in this format:

```
Discovered skills:

  1. [<repo-name>] <skill-name> — <description>
  2. [<repo-name>] <skill-name> — <description>
  ...

Which of these are customer-facing skills that should appear in the README?
(Enter numbers separated by commas, or "all" / "none")
```

Wait for the user's response before proceeding. Use their selection as the definitive set of skills to include in the README.

### Step 3 — Determine the default branch for each selected repo

```bash
gh api repos/open-edge-platform/<repo> --jq '.default_branch'
```

Use this branch name when constructing GitHub URLs for skill links.

### Step 4 — Rebuild README.md

Regenerate the repo-root `README.md` using this exact structure:

````markdown
# Open Edge Platform — Agent Skills Index

This repository is the central hub for **External facing agent skills** to be used by the customers.

A **skill** is a `SKILL.md` file that gives a coding agent focused, task-specific instructions. When a prompt matches a skill's description, the agent loads that skill's guidance automatically.

---

## Customer-Facing Skills

Skills designed for end-users building solutions with Open Edge Platform products.

### [<repo-name>](<repo-url>) — <repo description>

Skills live in `<skills-path>` within the repo.

| Skill | Description |
|-------|-------------|
| [<name>](<full GitHub URL to SKILL.md>) | <description> |

---

<repeat for each repo that has customer-facing skills, sorted alphabetically>

## Contributing a Skill

<keep the existing Contributing section unchanged>

---

*This index is maintained by the [update-skills-index](.github/skills/update-skills-index/SKILL.md) skill. Run it on demand to sync with the latest skills across the org.*
````

**Sorting rules:**
- Repos are sorted alphabetically by name
- Skills within a repo are listed in the order returned by the search API (effectively alphabetical by folder name)

**Link format:**
- Skill name links to the `SKILL.md` on GitHub: `https://github.com/open-edge-platform/<repo>/blob/<default_branch>/<path>`
- Repo header links to the repository root: `https://github.com/open-edge-platform/<repo>`

**Repo description:**
- Use the GitHub API `description` field for the repo subtitle: `gh api repos/open-edge-platform/<repo> --jq '.description'`
- Truncate to ~80 chars if too long; omit if empty

### Step 5 — Commit the updated README

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
- **Customer-Facing Skills** section listing only the skills confirmed by the user as end-user-facing, drawn from all repos in the org including `open-edge-platform/skills` itself
- The Contributing section preserved unchanged

## Notes

- The GitHub code search API may have a short lag (a few minutes) after new files are pushed before they appear in results. If a newly-added skill is missing, wait and retry.
- Skills in private repositories will not appear in search results unless the token has access to those repos.
- If a repo uses a non-standard path for skills (not `.github/skills/` or `.agents/skills/`), it will still be found via the `filename:SKILL.md` search.
