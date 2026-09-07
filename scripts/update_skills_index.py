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
      skills — list of skill objects with name and optional path
                (each skill is installed as .agents/skills/<name>)
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
    if not lock_path.exists():
        return
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
        rc = subprocess.run(cmd, cwd=str(cwd), env={**os.environ, "DISABLE_TELEMETRY": "1"}).returncode
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


def _lock_source_matches(lock_meta: dict, entry: dict, skill: str | dict) -> bool:
    """Return whether an installed skill still has its configured source."""
    if lock_meta.get("source") != entry["repo"]:
        return False
    expected_ref = entry.get("ref", "main").strip() or "main"
    if (lock_meta.get("ref") or "main") != expected_ref:
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
      - remove skills that are no longer configured, plus any whose
        configured source (repo/ref/path) changed
      - (re)add every configured skill, batched per (repo, ref) so each
        source repo is cloned only once per run no matter how many skills —
        or product entries — pull from it (e.g. edge-ai-libraries spans 5
        entries / 8 skills but is cloned exactly once)

    --agent universal  → installs only into .agents/skills/
    --copy             → copies files (no symlinks; fully committable)
    --full-depth       → needed since adds now target the repo root instead
                         of a skill-scoped GitHub tree URL

    Returns True if all skills synced successfully, False if any failed.
    """
    lock_path = repo_root / "skills-lock.json"
    installed = load_skills_lock(lock_path)
    configured = {
        _skill_name(skill): (entry, skill)
        for entry in config_entries
        for skill in entry["skills"]
    }
    has_error = False

    # Detect stale skills from disk so removal works even when skills-lock.json
    # is not committed (i.e., starts absent and is written fresh each CI run).
    local_skills_dir = repo_root / ".agents" / "skills"
    installed_on_disk = {d.name for d in local_skills_dir.iterdir() if d.is_dir()} if local_skills_dir.is_dir() else set()
    stale_skills = sorted(installed_on_disk - set(configured))
    relocated_skills = sorted(
        name
        for name, (entry, skill) in configured.items()
        if name in installed and not _lock_source_matches(installed[name], entry, skill)
    )
    to_remove = sorted(set(stale_skills) | set(relocated_skills))

    if to_remove:
        logger.info(
            "Removing %d skill(s) before (re)install (%d stale, %d relocated): %s",
            len(to_remove), len(stale_skills), len(relocated_skills), ", ".join(to_remove),
        )
        cmd = ["npx", "skills", "remove", *to_remove, "--agent", "universal", "--yes"]
        if dry_run:
            logger.info("[dry-run] %s", " ".join(cmd))
        elif _run(cmd, repo_root) != 0:
            logger.error("Failed to remove skill(s): %s", ", ".join(to_remove))
            has_error = True
        elif stale_skills:
            # skills CLI 1.5.11 removes project files but only prunes its
            # global lock, so reconcile the project lock explicitly.
            # Relocated skills keep their (stale) lock entry until the add
            # below overwrites it with the corrected one.
            remove_skills_from_lock(lock_path, stale_skills)

    # Group every configured skill by (repo, ref) across ALL config entries,
    # so one product repo referenced from several entries (e.g.
    # edge-ai-libraries) still results in a single clone.
    groups: dict[tuple[str, str], list[tuple[dict, str | dict]]] = {}
    for entry in config_entries:
        key = (entry["repo"], entry["ref"].strip())
        for skill in entry["skills"]:
            groups.setdefault(key, []).append((entry, skill))

    for (repo, ref), members in groups.items():
        skill_names = [_skill_name(skill) for _, skill in members]
        source = _build_repo_source({"repo": repo, "ref": ref})
        cmd = [
            "npx", "skills", "add", source,
            "--skill", *skill_names,
            "--agent", "universal", "--copy", "--full-depth", "--yes",
        ]

        if dry_run:
            logger.info("[dry-run] %s", " ".join(cmd))
            continue

        logger.info("Syncing %d skill(s) from %s%s: %s",
                    len(skill_names), repo, f"#{ref}" if ref and ref != "main" else "", ", ".join(skill_names))
        rc = _run(cmd, repo_root)
        if rc != 0:
            logger.error("npx skills exited %d for %s (%s)", rc, source, ", ".join(skill_names))
            has_error = True
            continue

        logger.info("✓ Synced %s: %s", source, ", ".join(skill_names))

        # Verify each skill landed at its expected path — catches a name
        # collision between subtrees resolving to the wrong SKILL.md.
        current_lock = load_skills_lock(lock_path)
        for entry, skill in members:
            name = _skill_name(skill)
            lock_meta = current_lock.get(name)
            if not lock_meta:
                # Skill absent after batch add — the CLI's findSkillDirs has a
                # hardcoded maxDepth=5 so skills nested 6+ levels deep are
                # silently skipped. Retry with a path-scoped tree URL which
                # resets the scan root to the skill's .github/skills/ dir.
                skill_path = _skill_path(entry, skill)
                if skill_path:
                    tree_ref = entry.get("ref", "main").strip() or "main"
                    ref_suffix = f"#{tree_ref}" if tree_ref != "main" else ""
                    tree_source = f"{entry['repo']}/{skill_path}{ref_suffix}"
                    logger.warning(
                        "Skill '%s' absent after batch add — retrying with path-scoped source %s",
                        name, tree_source,
                    )
                    _run(
                        ["npx", "skills", "add", tree_source,
                         "--skill", name, "--agent", "universal", "--copy", "--yes"],
                        repo_root, retries=1,
                    )
                    current_lock = load_skills_lock(lock_path)
                    lock_meta = current_lock.get(name)
            if not lock_meta:
                logger.error("Skill '%s' missing from skills-lock.json after add", name)
                has_error = True
                continue
            source_path = _skill_path(entry, skill)
            expected_path = f"{source_path}/{name}/SKILL.md" if source_path else None
            actual_path = lock_meta.get("skillPath")
            if expected_path and actual_path != expected_path:
                logger.warning(
                    "Skill '%s' installed from unexpected path %r (expected %r) — possible name collision",
                    name, actual_path, expected_path,
                )

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

def _skills_repo_branch(repo_root: Path) -> str:
    """Return the current git branch, falling back to 'main'."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        branch = result.stdout.strip()
        if not branch or branch == "HEAD":
            return os.getenv("GITHUB_REF_NAME") or "main"
        return branch
    except subprocess.CalledProcessError:
        return os.getenv("GITHUB_REF_NAME") or "main"


def build_skills_table(skills_lock: dict, local_skills_dir: Path, config_entries: list[dict]) -> str:
    """
    Build only the skills table rows from installed SKILL.md files.
    Returns the full replacement block including sentinel comments and timestamp.
    config_entries supplies per-skill metadata: ref (branch) and optional path
    override. The prompts URL is derived from the local example-prompts directory.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    repo_root = local_skills_dir.parent.parent
    skills_branch = _skills_repo_branch(repo_root)

    # Index config extras by individual skill name for quick lookup.
    config_by_skill: dict = {}
    for e in config_entries:
        skills = e["skills"]
        for s in skills:
            skill_name = s["name"] if isinstance(s, dict) else s
            config_by_skill[skill_name] = {**e}

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
        print(f"  + [{product}] {fm['name']}", file=sys.stderr)
        rows.append({
            "product": product,
            "repo_url": f"https://github.com/{canonical_repo}",
            "skill_name": fm["name"],
            "skill_url": f"https://github.com/open-edge-platform/skills/tree/{skills_branch}/.agents/skills/{skill_name}",
        })

    rows.sort(key=lambda r: (r["product"], r["skill_name"]))

    # Group rows by product so multi-skill products appear on a single table row.
    product_groups: dict[str, list[dict]] = {}
    for row in rows:
        product_groups.setdefault(row["product"], []).append(row)

    lines = [
        f"{SKILLS_INDEX_BEGIN}",
        f"<!-- Last updated: {now} -->",
        "| Product | Skills |",
        "|---------|--------|",
    ]
    for product, group in product_groups.items():
        repo_url = group[0]["repo_url"]
        skills_cell = ", ".join(f"[{r['skill_name']}]({r['skill_url']})" for r in group)
        lines.append(f"| [{product}]({repo_url}) | {skills_cell} |")
    lines.append(f"| **Total** | **{len(product_groups)} products, {len(rows)} skills** |")
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
