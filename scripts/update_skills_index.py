#!/usr/bin/env python3

#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Regenerate the skills index section in README.md.

For each skill in skills-config.json, fetches SKILL.md directly from GitHub
to extract the skill name and description, then splices an updated table into
README.md between the sentinel comments.

Usage:
    python scripts/update_skills_index.py [--config PATH]
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


SKILLS_INDEX_BEGIN = "<!-- BEGIN SKILLS INDEX -->"
SKILLS_INDEX_END = "<!-- END SKILLS INDEX -->"


# ---------------------------------------------------------------------------
# Config / lock helpers
# ---------------------------------------------------------------------------

def load_skills_config(config_path: Path) -> list[dict]:
    """
    Read skills-config.json.  Each entry must have:
      repo   — full "org/repo" name       (e.g. "open-edge-platform/dlstreamer")
      skill  — list of skill folder names
    Optional per entry:
      ref    — branch, tag, or commit hash to read from (default: "main")
      path   — path prefix inside the repo where skills live (default: ".github/skills")
    """
    if not config_path.exists():
        sys.exit(f"Error: skills-config.json not found at {config_path}")
    with config_path.open(encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("skills", [])
    valid = []
    for entry in entries:
        if "repo" in entry and "skill" in entry:
            if isinstance(entry["skill"], str):
                entry = {**entry, "skill": [entry["skill"]]}
            valid.append(entry)
        else:
            print(f"  [warn] skipping malformed entry (needs repo+skill): {entry}", file=sys.stderr)
    return valid


# ---------------------------------------------------------------------------
# GitHub fetch + frontmatter parser
# ---------------------------------------------------------------------------

def fetch_skill_md(repo: str, ref: str, skill_file_path: str) -> str:
    """Fetch raw SKILL.md content from GitHub for the given repo/ref/path."""
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{skill_file_path}"
    try:
        with urllib.request.urlopen(url) as resp:  # noqa: S310
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        print(f"  [warn] HTTP {exc.code} fetching {url}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] failed to fetch {url}: {exc}", file=sys.stderr)
    return ""


def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from SKILL.md content.

    Handles plain scalar values and YAML block scalars (>, >-, |, |-).
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = next((i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---"), None)
    if end is None:
        return {}
    fm: dict = {}
    fm_lines = lines[1:end]
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        m = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val in (">", ">-", "|", "|-"):
                # YAML block scalar: collect subsequent indented continuation lines
                folded = val in (">", ">-")
                block_lines = []
                i += 1
                while i < len(fm_lines) and fm_lines[i][:1] in (" ", "\t"):
                    block_lines.append(fm_lines[i].strip())
                    i += 1
                fm[key] = " ".join(block_lines) if folded else "\n".join(block_lines)
                continue
            fm[key] = val.strip('"').strip("'")
        i += 1
    return fm


# ---------------------------------------------------------------------------
# README builder
# ---------------------------------------------------------------------------

def build_skills_table(config_entries: list[dict]) -> str:
    """
    Build the skills table by fetching SKILL.md from GitHub for each configured skill.
    Returns the full replacement block including sentinel comments and timestamp.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    rows: list[dict] = []
    for entry in config_entries:
        repo = entry["repo"]
        product = entry.get("product") or repo.split("/")[-1]
        ref = entry.get("ref") or "main"
        path = entry.get("path", ".github/skills")
        prompts_url = entry.get("prompts_url") or None

        for skill_name in entry["skill"]:
            skill_file_path = f"{path}/{skill_name}/SKILL.md" if path else f"{skill_name}/SKILL.md"
            content = fetch_skill_md(repo, ref, skill_file_path)
            if not content:
                print(f"  [skip] {skill_name} — could not fetch SKILL.md", file=sys.stderr)
                continue

            fm = parse_frontmatter(content)
            if not fm.get("name"):
                print(f"  [skip] {skill_name} — no name in frontmatter", file=sys.stderr)
                continue

            print(f"  + [{repo}] {fm['name']}", file=sys.stderr)
            repo_path_url = f"https://github.com/{repo}/tree/{ref}/{path}" if path else f"https://github.com/{repo}"
            rows.append({
                "product": product,
                "repo_path_url": repo_path_url,
                "skill_name": fm["name"],
                "skill_url": f"https://github.com/{repo}/blob/{ref}/{skill_file_path}",
                "description": fm.get("description", ""),
                "prompts_url": prompts_url,
            })

    rows.sort(key=lambda r: (r["product"], r["skill_name"]))

    lines = [
        f"{SKILLS_INDEX_BEGIN}",
        f"<!-- Last updated: {now} -->",
        "| Product | Prompts | Skill | Description |",
        "|------------|---------|-------|-------------|",
    ]
    for row in rows:
        prompts_cell = f"[Prompts]({row['prompts_url']})" if row["prompts_url"] else "—"
        lines.append(
            f"| [{row['product']}]({row['repo_path_url']}) "
            f"| {prompts_cell} "
            f"| [{row['skill_name']}]({row['skill_url']}) "
            f"| {row['description']} |"
        )
    lines.append(SKILLS_INDEX_END)
    return "\n".join(lines)


def update_readme(readme_path: Path, config_entries: list[dict]) -> None:
    """
    Splice the generated skills table into README.md between the sentinel
    comments, leaving everything outside the sentinels unchanged.
    """
    content = readme_path.read_text(encoding="utf-8")

    begin_idx = content.find(SKILLS_INDEX_BEGIN)
    end_idx = content.find(SKILLS_INDEX_END)

    if begin_idx == -1 or end_idx == -1:
        sys.exit(
            f"Error: could not find '{SKILLS_INDEX_BEGIN}' / '{SKILLS_INDEX_END}' "
            f"sentinels in {readme_path}. Add them to README.md to mark the auto-updated region."
        )

    new_block = build_skills_table(config_entries)
    updated = content[:begin_idx] + new_block + content[end_idx + len(SKILLS_INDEX_END):]
    readme_path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    repo_root = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(repo_root / "skills-config.json"),
                        help="Path to skills-config.json.")
    args = parser.parse_args()

    entries = load_skills_config(Path(args.config))
    skill_count = sum(len(e["skill"]) for e in entries)
    print(f"Updating README skills index for {skill_count} skill(s) …", file=sys.stderr)

    readme_path = repo_root / "README.md"

    update_readme(readme_path, entries)
    print("README.md updated.", file=sys.stderr)


if __name__ == "__main__":
    main()