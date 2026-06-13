#!/usr/bin/env python3

#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Sync selected skills into .agents/skills/ and regenerate skills index section in README.md.

skills-config.json is the single source of truth.  The script:
  1. Reads skills-config.json and runs `npx skills add/update` for each entry,
     targeting only .agents/skills/ (via --agent universal --copy).
  2. Reads the installed SKILL.md files from .agents/skills/ directly to
     parse frontmatter, and reads skills-lock.json for upstream repo/path
     metadata to build GitHub links.

Usage:
    python scripts/update_skills_index.py [--dry-run] [--no-install] [--config PATH]
"""

import argparse
import json
import re
import subprocess
import sys
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
      repo   — full "org/repo" name  (e.g. "open-edge-platform/dlstreamer")
      skill  — skill folder name     (becomes .agents/skills/<skill>)
    """
    if not config_path.exists():
        sys.exit(f"Error: skills-config.json not found at {config_path}")
    with config_path.open(encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("skills", [])
    valid = []
    for entry in entries:
        if "repo" in entry and "skill" in entry:
            valid.append(entry)
        else:
            print(f"  [warn] skipping malformed entry (needs repo+skill): {entry}", file=sys.stderr)
    return valid


def load_skills_lock(lock_path: Path) -> dict:
    """
    Return the skills dict from skills-lock.json (written by `npx skills`).
    Keys are skill names; values include source, skillPath, etc.
    """
    if not lock_path.exists():
        return {}
    with lock_path.open(encoding="utf-8") as f:
        return json.load(f).get("skills", {})


# ---------------------------------------------------------------------------
# Installation via `npx skills`
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path) -> int:
    print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def install_skills(config_entries: list[dict], repo_root: Path, dry_run: bool = False) -> None:
    """
    For each entry in skills-config.json:
      - `npx skills update <name> --yes`                        if already in skills-lock.json
      - `npx skills add <repo> --skill <name>
           --agent universal --copy --yes`                      otherwise

    --agent universal  → installs only into .agents/skills/
    --copy             → copies files (no symlinks; fully committable)
    """
    installed = set(load_skills_lock(repo_root / "skills-lock.json").keys())

    for entry in config_entries:
        repo, skill = entry["repo"], entry["skill"]
        if skill in installed:
            cmd = ["npx", "skills", "update", skill, "--yes"]
        else:
            cmd = ["npx", "skills", "add", repo,
                   "--skill", skill, "--agent", "universal", "--copy", "--yes"]

        if dry_run:
            print(f"  [dry-run] {' '.join(cmd)}", file=sys.stderr)
            continue

        rc = _run(cmd, repo_root)
        if rc != 0:
            print(f"  [warn] exited {rc} for '{skill}'", file=sys.stderr)
        else:
            print(f"  ✓ {skill}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Frontmatter parser (reads from local disk — no API call)
# ---------------------------------------------------------------------------

def parse_frontmatter(skill_md: Path) -> dict:
    """Parse YAML frontmatter from a locally installed SKILL.md file."""
    if not skill_md.exists():
        return {}
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
    if end is None:
        return {}
    fm: dict = {}
    for line in lines[1:end]:
        m = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


# ---------------------------------------------------------------------------
# README builder (reads from .agents/skills/ + skills-lock.json)
# ---------------------------------------------------------------------------

def build_skills_table(skills_lock: dict, local_skills_dir: Path, config_entries: list[dict]) -> str:
    """
    Build only the skills table rows from installed SKILL.md files.
    Returns the full replacement block including sentinel comments and timestamp.
    config_entries supplies optional extra metadata (e.g. prompts_url) per skill.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # Index config extras by skill name for quick lookup
    config_by_skill = {e["skill"]: e for e in config_entries}

    rows: list[dict] = []
    for skill_name, lock_meta in skills_lock.items():
        repo = lock_meta.get("source", "")
        skill_path = lock_meta.get("skillPath", "")
        if not repo or not skill_path:
            print(f"  [skip] {skill_name} — missing source/skillPath in lock", file=sys.stderr)
            continue

        local_skill_md = local_skills_dir / skill_name / "SKILL.md"
        fm = parse_frontmatter(local_skill_md)
        if not fm.get("name"):
            print(f"  [skip] {skill_name} — no name in frontmatter", file=sys.stderr)
            continue

        print(f"  + [{repo}] {fm['name']}", file=sys.stderr)
        prompts_url = config_by_skill.get(skill_name, {}).get("prompts_url") or None
        rows.append({
            "repo_name": repo.split("/")[-1],
            "repo_url": f"https://github.com/{repo}",
            "skill_name": fm["name"],
            "skill_url": f"https://github.com/{repo}/blob/main/{skill_path}",
            "description": fm.get("description", ""),
            "prompts_url": prompts_url,
        })

    rows.sort(key=lambda r: (r["repo_name"], r["skill_name"]))

    lines = [
        f"{SKILLS_INDEX_BEGIN}",
        f"<!-- Last updated: {now} -->",
        "| Repository | Prompts | Skill | Description |",
        "|------------|---------|-------|-------------|",
    ]
    for row in rows:
        prompts_cell = f"[Prompts]({row['prompts_url']})" if row["prompts_url"] else "—"
        lines.append(
            f"| [{row['repo_name']}]({row['repo_url']}) "
            f"| {prompts_cell} "
            f"| [{row['skill_name']}]({row['skill_url']}) "
            f"| {row['description']} |"
        )
    lines.append(SKILLS_INDEX_END)
    return "\n".join(lines)


def update_readme(readme_path: Path, skills_lock: dict, local_skills_dir: Path, config_entries: list[dict]) -> None:
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

    new_block = build_skills_table(skills_lock, local_skills_dir, config_entries)
    updated = content[:begin_idx] + new_block + content[end_idx + len(SKILLS_INDEX_END):]
    readme_path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    repo_root = Path(__file__).resolve().parent.parent
    local_skills_dir = repo_root / ".agents" / "skills"

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show install commands and print README without writing anything.")
    parser.add_argument("--install", dest="install", action="store_true", default=True,
                        help="Sync earmarked skills via npx skills (default: on).")
    parser.add_argument("--no-install", dest="install", action="store_false",
                        help="Skip installation; only rebuild README.md.")
    parser.add_argument("--config", default=str(repo_root / "skills-config.json"),
                        help="Path to skills-config.json.")
    args = parser.parse_args()

    # Step 1 — install / update skills via npx skills
    entries = load_skills_config(Path(args.config))
    if args.install:
        print(f"Syncing {len(entries)} skill(s) via npx skills …", file=sys.stderr)
        install_skills(entries, repo_root, dry_run=args.dry_run)

    # Step 2 — update only the skills index section in README.md
    skills_lock = load_skills_lock(repo_root / "skills-lock.json")
    if not skills_lock:
        print("skills-lock.json is empty or missing — README not updated.", file=sys.stderr)
        sys.exit(0)

    print(f"Updating README skills index from {len(skills_lock)} installed skill(s) …", file=sys.stderr)
    readme_path = repo_root / "README.md"

    if args.dry_run:
        print(build_skills_table(skills_lock, local_skills_dir, entries))
        return

    update_readme(readme_path, skills_lock, local_skills_dir, entries)
    print("README.md updated.", file=sys.stderr)


if __name__ == "__main__":
    main()