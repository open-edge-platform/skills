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

Modes:
    (default)     Sync skills via npx and update README.md skills index.
    --no-install  Skip npx sync; only rebuild the README.md skills index from
                  already-installed skills in .agents/skills/ and skills-lock.json.
    --dry-run     Print the npx commands that would run and the generated skills
                  table block to stdout without installing anything or writing files.
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


def _build_source(entry: dict) -> str:
    """
    Build the npx skills add source argument from a config entry.

    Format used per ref:
        <repo>                  — main branch, no custom path (shorthand)
        <repo>#<ref>            — non-main branch or tag
    """
    repo = entry["repo"]
    ref = entry.get("ref", "").strip()

    if not ref or ref == "main":
        return repo

    return f"{repo}#{ref}"


def install_skills(config_entries: list[dict], repo_root: Path, dry_run: bool = False) -> bool:
    """
    For each entry in skills-config.json:
      - `npx skills update <name> --yes`                        if already in skills-lock.json
      - `npx skills add <source> --skill <name>
           --agent universal --copy --yes`                      otherwise

    <source> is derived from repo + ref + path via _build_source(), supporting
    the default branch, alternate branches/tags, and sub-directory paths.

    --agent universal  → installs only into .agents/skills/
    --copy             → copies files (no symlinks; fully committable)

    Returns True if all skills synced successfully, False if any failed.
    """
    installed = set(load_skills_lock(repo_root / "skills-lock.json").keys())
    has_error = False

    for entry in config_entries:
        source = _build_source(entry)
        skills = entry["skill"] if isinstance(entry["skill"], list) else [entry["skill"]]
        for skill in skills:
            skill_name = skill["name"] if isinstance(skill, dict) else skill
            if skill_name in installed:
                cmd = ["npx", "skills", "update", skill_name, "--yes"]
            else:
                cmd = ["npx", "skills", "add", source,
                       "--skill", skill_name, "--agent", "universal", "--copy", "--yes"]

            if dry_run:
                print(f"  [dry-run] {' '.join(cmd)}", file=sys.stderr)
                continue

            rc = _run(cmd, repo_root)
            if rc != 0:
                print(f"  [error] exited {rc} for '{skill_name}'", file=sys.stderr)
                has_error = True
            else:
                print(f"  ✓ {skill_name}", file=sys.stderr)

    return not has_error


# ---------------------------------------------------------------------------
# Frontmatter parser (reads from local disk — no API call)
# ---------------------------------------------------------------------------

def parse_frontmatter(skill_md: Path) -> dict:
    """Parse YAML frontmatter from a locally installed SKILL.md file.

    Handles plain scalar values and YAML block scalars (>, >-, |, |-).
    """
    if not skill_md.exists():
        return {}
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
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
            else:
                fm[key] = val.strip('"').strip("'")
        i += 1
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

    # Index config extras by individual skill name for quick lookup.
    # Each value stores the parent entry plus the skill-level prompts_url (if any).
    config_by_skill: dict = {}
    for e in config_entries:
        skills = e["skill"] if isinstance(e["skill"], list) else [e["skill"]]
        for s in skills:
            skill_name = s["name"] if isinstance(s, dict) else s
            skill_prompts_url = s.get("prompts_url") if isinstance(s, dict) else None
            config_by_skill[skill_name] = {**e, "_skill_prompts_url": skill_prompts_url or ""}

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

        cfg = config_by_skill.get(skill_name, {})
        product = cfg.get("product") or repo.split("/")[-1]
        # Use the canonical repo from config if available; fall back to lock source
        canonical_repo = cfg.get("repo") or repo
        ref = cfg.get("ref") or "HEAD"
        print(f"  + [{product}] {fm['name']}", file=sys.stderr)
        prompts_url = cfg.get("_skill_prompts_url") or None
        rows.append({
            "product": product,
            "repo_url": f"https://github.com/{canonical_repo}",
            "skill_name": fm["name"],
            "skill_url": f"https://github.com/{canonical_repo}/blob/{ref}/{skill_path}",
            "description": fm.get("description", ""),
            "prompts_url": prompts_url,
        })

    rows.sort(key=lambda r: (r["product"], r["skill_name"]))

    # Group rows by product so multi-skill products appear on a single table row.
    product_groups: dict[str, list[dict]] = {}
    for row in rows:
        product_groups.setdefault(row["product"], []).append(row)

    lines = [
        f"{SKILLS_INDEX_BEGIN}",
        f"<!-- Last updated: {now} -->",
        "| Product | Skill | Skill Description |",
        "|---------|-------|-------------------|",
    ]
    for product, group in product_groups.items():
        repo_url = group[0]["repo_url"]
        for i, r in enumerate(group):
            # First skill shows the linked product name; subsequent skills use
            # a continuation marker so readers know they belong to the same product.
            product_cell = f"[{product}]({repo_url})" if i == 0 else f"↳"
            skill_cell = (
                f"[{r['skill_name']}]({r['skill_url']}) ([Prompts]({r['prompts_url']}))"
                if r["prompts_url"]
                else f"[{r['skill_name']}]({r['skill_url']})"
            )
            lines.append(
                f"| {product_cell} "
                f"| {skill_cell} "
                f"| {r['description']} |"
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
                        help="Print npx commands and the generated skills table to stdout without installing or writing any files.")
    parser.add_argument("--install", dest="install", action="store_true", default=True,
                        help="Sync skills via npx skills add/update, then rebuild README.md (default).")
    parser.add_argument("--no-install", dest="install", action="store_false",
                        help="Skip npx sync; only rebuild the README.md skills index from already-installed skills.")
    parser.add_argument("--config", default=str(repo_root / "skills-config.json"),
                        help="Path to skills-config.json.")
    args = parser.parse_args()

    # Step 1 — install / update skills via npx skills
    entries = load_skills_config(Path(args.config))
    if args.install:
        print(f"Syncing {len(entries)} skill(s) via npx skills …", file=sys.stderr)
        success = install_skills(entries, repo_root, dry_run=args.dry_run)
        if not success:
            sys.exit(1)

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