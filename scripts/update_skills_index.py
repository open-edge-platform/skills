#!/usr/bin/env python3

#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Sync selected skills into .agents/skills/ and regenerate skills index section in README.md.

skills-config.json is the single source of truth.  The script:
  1. Reads skills-config.json, removes unconfigured skills, updates existing
     skills, and adds new or relocated skills. Explicit GitHub tree URLs built
     from repo/ref/path/name let product repos use different skill layouts.
  2. Reads the installed SKILL.md files from .agents/skills/ directly to
     parse frontmatter, and reads skills-lock.json for upstream repo/path
     metadata to build GitHub links.

Usage:
    python scripts/update_skills_index.py [--dry-run] [--no-install] [--config PATH]
    python scripts/update_skills_index.py --check-only [--base-config PATH] [--config PATH]

Modes:
    (default)     Sync skills via npx and update README.md skills index.
    --no-install  Skip npx sync; only rebuild the README.md skills index from
                  already-installed skills in .agents/skills/ and skills-lock.json.
    --dry-run     Print the npx commands that would run and the generated skills
                  table block to stdout without installing anything or writing files.
    --check-only  Check that added or relocated skills exist at their configured
                  GitHub source without installing or writing files.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


SKILLS_INDEX_BEGIN = "<!-- BEGIN SKILLS INDEX -->"
SKILLS_INDEX_END = "<!-- END SKILLS INDEX -->"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config / lock helpers
# ---------------------------------------------------------------------------

def load_skills_config(config_path: Path) -> list[dict]:
    """
    Read skills-config.json.  Each product must have:
      repo   — full "org/repo" name  (e.g. "open-edge-platform/dlstreamer")
      skills — skill folder names    (become .agents/skills/<skill>)
    """
    if not config_path.exists():
        sys.exit(f"Error: skills-config.json not found at {config_path}")
    with config_path.open(encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("products", [])
    valid = []
    for entry in entries:
        if "repo" in entry and "skills" in entry:
            valid.append(entry)
        else:
            print(f"  [warn] skipping malformed entry (needs repo+skills): {entry}", file=sys.stderr)
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


def remove_skills_from_lock(lock_path: Path, skill_names: list[str]) -> None:
    """Remove project skills from the lock file after the CLI removes them."""
    with lock_path.open(encoding="utf-8") as f:
        data = json.load(f)

    skills = data.get("skills", {})
    for skill_name in skill_names:
        if skills.pop(skill_name, None) is not None:
            logger.info("skills-lock.json: removed entry for '%s'", skill_name)

    lock_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    logger.debug("skills-lock.json written to %s", lock_path)


# ---------------------------------------------------------------------------
# Installation via `npx skills`
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path, retries: int = 2, retry_delay: float = 5.0) -> int:
    """Run an npx skills command, retrying on failure.

    `npx skills` clones its source repo from scratch on every add/update/remove.
    Large source repos (e.g. multi-gigabyte monorepos) occasionally hit
    transient network errors ("Recv failure: Connection reset by peer") during
    that clone, so failures are retried a few times before being reported.
    """
    attempts = retries + 1
    for attempt in range(1, attempts + 1):
        suffix = f" (attempt {attempt}/{attempts})" if attempts > 1 else ""
        logger.info("$ %s%s", " ".join(cmd), suffix)
        rc = subprocess.run(cmd, cwd=str(cwd)).returncode
        if rc == 0:
            return rc
        if attempt < attempts:
            logger.warning("Command exited %d — retrying in %.0fs: %s", rc, retry_delay, " ".join(cmd))
            time.sleep(retry_delay)
        else:
            logger.error("Command exited %d after %d attempt(s): %s", rc, attempts, " ".join(cmd))
    return rc


def _build_repo_source(entry: dict) -> str:
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


def _skill_name(skill: str | dict) -> str:
    return skill["name"] if isinstance(skill, dict) else skill


def _skill_path(entry: dict, skill: str | dict) -> str:
    if isinstance(skill, dict) and skill.get("path"):
        return skill["path"].strip().strip("/")
    return entry.get("path", "").strip().strip("/")


def _build_skill_source(entry: dict, skill: str | dict) -> str:
    """Build the npx skills add source for one skill.

    When a source path is configured, use a direct GitHub tree URL so discovery
    does not depend on the product repo's overall layout. Without a path, fall
    back to the repo shorthand supported by the skills CLI.
    """
    source_path = _skill_path(entry, skill)
    if not source_path:
        return _build_repo_source(entry)

    repo = entry["repo"]
    ref = entry["ref"].strip()
    return f"https://github.com/{repo}/tree/{ref}/{source_path}/{_skill_name(skill)}"


def _lock_source_matches(lock_meta: dict, entry: dict, skill: str | dict) -> bool:
    """Return whether an installed skill still has its configured source."""
    if lock_meta.get("source") != entry["repo"]:
        return False
    if lock_meta.get("ref") != entry["ref"].strip():
        return False

    source_path = _skill_path(entry, skill)
    if not source_path:
        return True

    expected_path = f"{source_path}/{_skill_name(skill)}/SKILL.md"
    return lock_meta.get("skillPath") == expected_path


def check_skills_exist(
    config_entries: list[dict], github_token: str = "", base_entries: list[dict] | None = None
) -> bool:
    """Check that added or relocated skills contain a SKILL.md at their source."""
    has_error = False
    checked = 0
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    base_sources = set()
    for entry in base_entries or []:
        for skill in entry["skills"]:
            base_sources.add((entry["repo"], entry["ref"].strip(), _skill_path(entry, skill), _skill_name(skill)))

    for entry in config_entries:
        for skill in entry["skills"]:
            skill_name = _skill_name(skill)
            repo = entry["repo"]
            ref = entry["ref"].strip()
            source_path = _skill_path(entry, skill)
            if (repo, ref, source_path, skill_name) in base_sources:
                continue

            checked += 1
            skill_path = "/".join(filter(None, (source_path, skill_name, "SKILL.md")))
            url = (
                f"https://api.github.com/repos/{repo}/contents/{quote(skill_path, safe='/')}?"
                f"{urlencode({'ref': ref})}"
            )
            detail = "unexpected response"
            try:
                with urlopen(Request(url, headers=headers), timeout=30) as response:  # nosec B310
                    exists = response.status == 200
            except HTTPError as error:
                exists = False
                detail = f"HTTP {error.code}"
            except URLError as error:
                exists = False
                detail = str(error.reason)

            if exists:
                print(f"  ✓ {repo}@{ref}:{skill_path}", file=sys.stderr)
            else:
                print(f"  [error] {repo}@{ref}:{skill_path} ({detail})", file=sys.stderr)
                has_error = True

    if checked == 0:
        print("No added or relocated skills to check.", file=sys.stderr)

    return not has_error


def install_skills(config_entries: list[dict], repo_root: Path, dry_run: bool = False) -> bool:
    """
    Reconcile installed skills with skills-config.json:
      - remove skills that are no longer configured
      - update installed skills whose configured source is unchanged
      - add new skills and remove/re-add skills whose source changed

    <source> is a direct GitHub tree URL when path is configured, otherwise it
    falls back to the skills CLI's repo shorthand ("org/repo" or "org/repo#ref").

    --agent universal  → installs only into .agents/skills/
    --copy             → copies files (no symlinks; fully committable)

    Returns True if all skills synced successfully, False if any failed.
    """
    installed = load_skills_lock(repo_root / "skills-lock.json")
    configured = {
        _skill_name(skill)
        for entry in config_entries
        for skill in entry["skills"]
    }
    has_error = False

    stale_skills = sorted(set(installed) - configured)
    if stale_skills:
        logger.info("Removing %d stale skill(s) no longer in skills-config.json: %s",
                    len(stale_skills), ", ".join(stale_skills))
        cmd = [
            "npx", "skills", "remove", *stale_skills,
            "--agent", "universal", "--yes",
        ]
        if dry_run:
            logger.info("[dry-run] %s", " ".join(cmd))
        else:
            if _run(cmd, repo_root) != 0:
                logger.error("Failed to remove stale skills: %s", ", ".join(stale_skills))
                has_error = True
            else:
                # skills CLI 1.5.11 removes project files but only prunes its
                # global lock, so reconcile the project lock explicitly.
                remove_skills_from_lock(repo_root / "skills-lock.json", stale_skills)

    for entry in config_entries:
        repo = entry["repo"]
        skills = entry["skills"]
        for skill in skills:
            skill_name = _skill_name(skill)
            logger.info("Processing skill '%s' from %s", skill_name, repo)
            lock_meta = installed.get(skill_name)
            if lock_meta and _lock_source_matches(lock_meta, entry, skill):
                logger.info("Skill '%s' source unchanged — updating", skill_name)
                cmd = ["npx", "skills", "update", skill_name, "--yes"]
            else:
                if lock_meta:
                    logger.info("Skill '%s' source changed — removing before re-adding", skill_name)
                    remove_cmd = [
                        "npx", "skills", "remove", skill_name,
                        "--agent", "universal", "--yes",
                    ]
                    if dry_run:
                        logger.info("[dry-run] %s", " ".join(remove_cmd))
                    elif _run(remove_cmd, repo_root) != 0:
                        logger.error("Failed to remove relocated skill '%s'", skill_name)
                        has_error = True
                        continue
                else:
                    logger.info("Skill '%s' is new — adding", skill_name)

                source = _build_skill_source(entry, skill)
                cmd = ["npx", "skills", "add", source,
                       "--skill", skill_name, "--agent", "universal", "--copy", "--yes"]

            if dry_run:
                logger.info("[dry-run] %s", " ".join(cmd))
                continue

            rc = _run(cmd, repo_root)
            if rc != 0:
                logger.error("npx skills exited %d for '%s'", rc, skill_name)
                has_error = True
            else:
                logger.info("✓ Synced '%s'", skill_name)

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
        skills = e["skills"]
        for s in skills:
            skill_name = s["name"] if isinstance(s, dict) else s
            skill_prompts_url = s.get("prompts_url") if isinstance(s, dict) else None
            config_by_skill[skill_name] = {**e, "_skill_prompts_url": skill_prompts_url or ""}

    rows: list[dict] = []
    for skill_name, lock_meta in skills_lock.items():
        if skill_name not in config_by_skill:
            print(f"  [skip] {skill_name} — not present in skills-config.json", file=sys.stderr)
            continue

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
            "skill_url": f"https://github.com/open-edge-platform/skills/tree/main/.agents/skills/{skill_name}",
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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)

    repo_root = Path(__file__).resolve().parent.parent
    local_skills_dir = repo_root / ".agents" / "skills"

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print npx commands and the generated skills table to stdout without installing or writing any files.")
    parser.add_argument("--install", dest="install", action="store_true", default=True,
                        help="Sync skills via npx skills remove/update/add, then rebuild README.md (default).")
    parser.add_argument("--no-install", dest="install", action="store_false",
                        help="Skip npx sync; only rebuild the README.md skills index from already-installed skills.")
    parser.add_argument("--check-only", action="store_true",
                        help="Check that configured skills contain a SKILL.md on GitHub, then exit.")
    parser.add_argument("--base-config",
                        help="With --check-only, only check skills added or relocated relative to this config.")
    parser.add_argument("--config", default=str(repo_root / "skills-config.json"),
                        help="Path to skills-config.json.")
    args = parser.parse_args()

    entries = load_skills_config(Path(args.config))
    if args.check_only:
        base_entries = load_skills_config(Path(args.base_config)) if args.base_config else None
        if not check_skills_exist(entries, os.environ.get("GITHUB_TOKEN", ""), base_entries):
            sys.exit(1)
        return

    # Step 1 — reconcile skills via npx skills
    if args.install:
        logger.info("Syncing %d product(s) via npx skills …", len(entries))
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
