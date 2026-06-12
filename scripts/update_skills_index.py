#!/usr/bin/env python3
"""
Scan selected open-edge-platform repositories for SKILL.md files and
regenerate README.md with a customer-facing skills index.

Usage:
    python scripts/update_skills_index.py [--repos repo1,repo2,...] [--dry-run]

Environment variables:
    GITHUB_TOKEN  Personal access token with repo read scope (required)
    REPOS         Comma-separated list of repo names to scan (overrides --repos)
                  Use "all" to search the entire open-edge-platform org.
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime

ORG = "open-edge-platform"

# Default set of customer-facing repos to scan.
# Override at runtime with the REPOS env var or --repos flag.
DEFAULT_REPOS = [
    "anomalib",
    "dlstreamer",
    "edge-ai-libraries",
    "scenescape",
    "skills",
]

CONTRIBUTING_SECTION = """## Contributing a Skill

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

To add a skill to the org index:

1. Create a `SKILL.md` in your repo under `.github/skills/<skill-name>/SKILL.md` (or `.agents/skills/<skill-name>/SKILL.md`)
2. Include a YAML frontmatter block with at minimum `name` and `description`
3. Open a PR in this repo or run the `update-skills-index` skill to regenerate this README automatically

### SKILL.md frontmatter format

```yaml
---
name: your-skill-name
description: "One-sentence description of when and why to use this skill"
argument-hint: "Optional hint shown to users about what argument to provide"
---
```"""

README_FOOTER = (
    "*This index is maintained by the "
    "[update-skills-index](.agents/skills/update-skills-index/SKILL.md) skill. "
    "Run it on demand or let the scheduled workflow keep it up to date.*"
)


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def _gh(path: str, token: str) -> dict | list:
    """Make a GET request to the GitHub REST API and return parsed JSON."""
    url = f"https://api.github.com/{path.lstrip('/')}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"  [warn] HTTP {exc.code} for {url}", file=sys.stderr)
        return {}


def search_skill_files(token: str, repos: list[str] | None) -> list[dict]:
    """Return a list of {repo, path} dicts for every SKILL.md found."""
    if repos:
        qualifiers = " ".join(f"repo:{ORG}/{r}" for r in repos)
        q = f"filename:SKILL.md {qualifiers}"
    else:
        q = f"org:{ORG} filename:SKILL.md"

    items = []
    page = 1
    while True:
        encoded_q = urllib.parse.quote(q)
        data = _gh(
            f"search/code?q={encoded_q}&per_page=100&page={page}", token
        )
        batch = data.get("items", [])
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    return [{"repo": i["repository"]["full_name"], "path": i["path"]} for i in items]


def fetch_frontmatter(token: str, repo: str, path: str) -> dict:
    """Fetch a SKILL.md and return its parsed YAML frontmatter fields."""
    data = _gh(f"repos/{repo}/contents/{path}", token)
    if not data or "content" not in data:
        return {}
    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return parse_frontmatter(content)


def get_repo_meta(token: str, repo: str) -> dict:
    """Return {description, default_branch} for a repo."""
    data = _gh(f"repos/{repo}", token)
    return {
        "description": (data.get("description") or "")[:80],
        "default_branch": data.get("default_branch", "main"),
    }


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> dict:
    """Extract name and description from YAML frontmatter."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
    if end is None:
        return {}
    fm: dict = {}
    for line in lines[1:end]:
        m = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            fm[key] = val
    return fm


# ---------------------------------------------------------------------------
# README builder
# ---------------------------------------------------------------------------

def build_readme(skills_by_repo: dict[str, list[dict]], repo_meta: dict) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Open Edge Platform — Agent Skills Index",
        "",
        "This repository is the central hub for **External facing agent skills** to be used by the customers.",
        "",
        "A **skill** is a `SKILL.md` file that gives a coding agent focused, task-specific instructions. "
        "When a prompt matches a skill's description, the agent loads that skill's guidance automatically.",
        "",
        "---",
        "",
        "## Customer-Facing Skills",
        "",
        "Skills designed for end-users building solutions with Open Edge Platform products.",
        "",
    ]

    for repo_full in sorted(skills_by_repo):
        skills = skills_by_repo[repo_full]
        repo_name = repo_full.split("/")[-1]
        meta = repo_meta.get(repo_full, {})
        branch = meta.get("default_branch", "main")
        desc = meta.get("description", "")
        repo_url = f"https://github.com/{repo_full}"

        header = f"### [{repo_name}]({repo_url})"
        if desc:
            header += f" — {desc}"
        lines.append(header)
        lines.append("")

        # Determine skills path prefix (common prefix of all skill paths)
        paths = [s["path"] for s in skills]
        # Use the directory two levels up from SKILL.md as the skills root
        skill_roots = {"/".join(p.split("/")[:-2]) for p in paths}
        if len(skill_roots) == 1:
            lines.append(f"Skills live in `{skill_roots.pop()}/` within the repo.")
        else:
            lines.append("Skills live across multiple paths within the repo.")
        lines.append("")
        lines.append("| Skill | Description |")
        lines.append("|-------|-------------|")

        for skill in sorted(skills, key=lambda s: s.get("name", "")):
            name = skill.get("name", skill["path"].split("/")[-2])
            description = skill.get("description", "")
            skill_url = f"https://github.com/{repo_full}/blob/{branch}/{skill['path']}"
            lines.append(f"| [{name}]({skill_url}) | {description} |")

        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(CONTRIBUTING_SECTION)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"<!-- Last updated: {now} -->")
    lines.append(README_FOOTER)
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import urllib.parse  # noqa: F401 – imported here for search_skill_files

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repos",
        help="Comma-separated repo names to scan (e.g. anomalib,dlstreamer). "
             "Use 'all' to scan the entire org.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated README to stdout instead of writing it.",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("Error: set GITHUB_TOKEN (or GH_TOKEN) environment variable.")

    # Resolve repo list
    repos_raw = os.environ.get("REPOS") or args.repos
    if repos_raw and repos_raw.strip().lower() != "all":
        repos = [r.strip() for r in repos_raw.split(",") if r.strip()]
    elif repos_raw and repos_raw.strip().lower() == "all":
        repos = None  # org-wide search
    else:
        repos = DEFAULT_REPOS

    print(f"Scanning repos: {repos or 'entire org'}", file=sys.stderr)

    # Step 1: find all SKILL.md files
    items = search_skill_files(token, repos)
    print(f"Found {len(items)} SKILL.md file(s)", file=sys.stderr)

    # Step 2: fetch frontmatter and group by repo
    # Skip the template SKILL.md in the skills repo itself
    skills_by_repo: dict[str, list[dict]] = {}
    repo_meta: dict = {}
    for item in items:
        repo = item["repo"]
        path = item["path"]
        # Skip template files
        if path.startswith("template/"):
            continue
        fm = fetch_frontmatter(token, repo, path)
        if not fm.get("name"):
            print(f"  [skip] {repo}/{path} — no name in frontmatter", file=sys.stderr)
            continue
        entry = {"path": path, **fm}
        skills_by_repo.setdefault(repo, []).append(entry)
        if repo not in repo_meta:
            repo_meta[repo] = get_repo_meta(token, repo)
        print(f"  + [{repo}] {fm['name']}", file=sys.stderr)

    if not skills_by_repo:
        print("No skills found — README not updated.", file=sys.stderr)
        sys.exit(0)

    # Step 3: build README
    readme = build_readme(skills_by_repo, repo_meta)

    if args.dry_run:
        print(readme)
        return

    # Step 4: write to disk
    readme_path = os.path.join(os.path.dirname(__file__), "..", "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme)
    print("README.md updated.", file=sys.stderr)


if __name__ == "__main__":
    import urllib.parse
    main()
