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
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


SKILLS_INDEX_BEGIN = "<!-- BEGIN SKILLS INDEX -->"
SKILLS_INDEX_END = "<!-- END SKILLS INDEX -->"

logger = logging.getLogger(__name__)

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SKILL_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


# ---------------------------------------------------------------------------
# Config / lock helpers
# ---------------------------------------------------------------------------


def _validate_git_ref(ref: str) -> str:
    """Reject ref names that are unsafe to pass to git/GitHub tooling."""
    ref = str(ref).strip()
    if not ref:
        raise ValueError("ref must not be empty")
    if (
        ref.startswith(("-", "/", "."))
        or ref.endswith(("/", "."))
        or ".." in ref
        or "//" in ref
        or "@{" in ref
        or any(char in ref for char in (" ", "~", "^", ":", "?", "*", "[", "\\"))
    ):
        raise ValueError(f"unsafe ref value: {ref!r}")
    return ref


def _validate_skill_path(path: str) -> str:
    """Reject path traversal and option-like path components."""
    cleaned = str(path).strip().strip("/")
    if not cleaned:
        raise ValueError("path must not be empty")
    segments = cleaned.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(f"unsafe path value: {path!r}")
    if any(not _SKILL_PATH_SEGMENT_RE.fullmatch(segment) for segment in segments):
        raise ValueError(f"unsafe path value: {path!r}")
    return cleaned


def validate_config_entries(config_entries: list[dict], require_slug: bool = True) -> None:
    """Validate config values before using them in subprocesses or API requests."""
    if not config_entries:
        raise ValueError("at least one product is required")
    slugs = set()
    names = set()
    for entry in config_entries:
        slug = entry.get("slug")
        if require_slug or slug is not None:
            if not isinstance(slug, str) or not _SKILL_NAME_RE.fullmatch(slug):
                raise ValueError(f"unsafe product slug: {slug!r}")
            if slug in slugs:
                raise ValueError(f"duplicate product slug: {slug!r}")
            slugs.add(slug)
        repo = entry.get("repo", "")
        if not _REPO_RE.fullmatch(repo):
            raise ValueError(f"unsafe repo value: {repo!r}")
        if "ref" in entry:
            ref = entry["ref"]
            entry["ref"] = "main" if ref is None or (isinstance(ref, str) and not ref.strip()) else _validate_git_ref(ref)
        else:
            entry["ref"] = "main"
        if "path" in entry:
            entry["path"] = _validate_skill_path(entry["path"])
        if not entry.get("skills"):
            raise ValueError("each product must contain at least one skill")
        for skill in entry.get("skills", []):
            if isinstance(skill, dict):
                name = skill.get("name", "")
                if not _SKILL_NAME_RE.fullmatch(name):
                    raise ValueError(f"unsafe skill name: {name!r}")
                if "path" in skill:
                    skill["path"] = _validate_skill_path(skill["path"])
            elif not _SKILL_NAME_RE.fullmatch(skill):
                raise ValueError(f"unsafe skill name: {skill!r}")
            name = _skill_name(skill)
            if name in names:
                raise ValueError(f"duplicate skill name: {name!r}")
            names.add(name)

def load_skills_config(config_path: Path) -> list[dict]:
    """
    Read skills-config.json.  Each product must have:
      repo   — full "org/repo" name  (e.g. "open-edge-platform/dlstreamer")
      skills — list of skill objects with name and optional path
                (each skill is published as .agents/skills/<slug>/<name>)
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
            raise ValueError("malformed product entry (needs repo+skills)")
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

def _run(cmd: list[str], cwd: Path, retries: int = 2, retry_delay: float = 5.0) -> int:
    """Run an npx skills command, retrying on failure.

    `npx skills` clones its source repo from scratch on every add/update/remove.
    Large source repos (e.g. multi-gigabyte monorepos) occasionally hit
    transient network errors ("Recv failure: Connection reset by peer") during
    that clone, so failures are retried a few times before being reported.
    """
    if cmd[:2] == ["npx", "skills"]:
        cli = Path(__file__).resolve().parent.parent / "node_modules/skills/dist/cli.mjs"
        if not cli.is_file():
            logger.error("Run npm ci before syncing skills.")
            return 1
        cmd = ["node", str(cli), *cmd[2:]]
    env = {**os.environ, "DISABLE_TELEMETRY": "1"}
    # The CLI dereferences links when copying. Prevent Git from checking out
    # source symlinks, which could otherwise expose files outside the checkout.
    config_count = int(env.get("GIT_CONFIG_COUNT", "0"))
    env.update({
        "GIT_CONFIG_COUNT": str(config_count + 1),
        f"GIT_CONFIG_KEY_{config_count}": "core.symlinks",
        f"GIT_CONFIG_VALUE_{config_count}": "false",
    })
    attempts = retries + 1
    for attempt in range(1, attempts + 1):
        suffix = f" (attempt {attempt}/{attempts})" if attempts > 1 else ""
        logger.info("$ %s%s", " ".join(cmd), suffix)
        rc = subprocess.run(cmd, cwd=str(cwd), env=env).returncode
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
    """Stage a complete catalog before replacing the managed skills tree."""
    validate_config_entries(config_entries)
    if dry_run:
        for entry in config_entries:
            for skill in entry["skills"]:
                logger.info("[dry-run] Publish %s/%s", entry["slug"], _skill_name(skill))
        return _install_flat_skills(config_entries, repo_root, dry_run=True)

    with tempfile.TemporaryDirectory(prefix="skills-sync-") as temporary:
        workspace = Path(temporary)
        staging = workspace / "install"
        staging.mkdir()
        if not _install_flat_skills(config_entries, staging):
            return False
        grouped = workspace / "grouped"
        grouped.mkdir()
        try:
            for entry in config_entries:
                for skill in entry["skills"]:
                    name = _skill_name(skill)
                    source = staging / ".agents/skills" / name
                    if source.is_symlink() or any(p.is_symlink() for p in source.rglob("*")):
                        raise ValueError(f"Skill contains symlinks: {name}")
                    if parse_frontmatter(source / "SKILL.md").get("name") != name:
                        raise ValueError(f"Missing or mismatched skill: {name}")
                    shutil.copytree(source, grouped / entry["slug"] / name)
            relocate_catalog_references(grouped, config_entries)
        except (OSError, ValueError) as error:
            logger.error("Staged catalog rejected: %s", error)
            return False

        target = repo_root / ".agents/skills"
        lock = repo_root / "skills-lock.json"
        backup = workspace / "previous"
        had_target = target.exists()
        old_lock = lock.read_bytes() if lock.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        if had_target:
            shutil.copytree(target, backup, symlinks=True)
        try:
            if had_target:
                shutil.rmtree(target)
            shutil.copytree(grouped, target)
            shutil.copyfile(staging / "skills-lock.json", lock)
        except OSError:
            if target.exists():
                shutil.rmtree(target)
            if had_target:
                shutil.copytree(backup, target, symlinks=True)
            if old_lock is None:
                lock.unlink(missing_ok=True)
            else:
                lock.write_bytes(old_lock)
            logger.exception("Publishing failed; restored previous catalog")
            return False
    return True


def relocate_catalog_references(skills_root: Path, config_entries: list[dict]) -> None:
    """Keep imported Markdown links to this catalog valid after upstream sync."""
    slugs = {
        _skill_name(skill): entry["slug"]
        for entry in config_entries
        for skill in entry["skills"]
    }
    pattern = re.compile(
        r"(https://(?:github\.com/open-edge-platform/skills/tree/|"
        r"raw\.githubusercontent\.com/open-edge-platform/skills/)"
        r"[^ \n`]+?/\.agents/skills/)([^/ \n`)#]+)(?=[/ \n`)#]|$)"
    )

    def replace(match: re.Match) -> str:
        name = match[2]
        if name == "<name>":
            return f"{match[1]}<product-slug>/{name}"
        if name in slugs:
            # A slug may equal its skill name; do not nest already-grouped links.
            remainder = match.string[match.end():]
            if remainder.startswith(f"/{name}"):
                return match[0]
            return f"{match[1]}{slugs[name]}/{name}"
        return match[0]

    for markdown in skills_root.rglob("*.md"):
        original = markdown.read_text(encoding="utf-8")
        updated = pattern.sub(replace, original)
        updated = re.sub(
            r"npx skills@[\d.]+ add open-edge-platform/skills\b",
            "npx skills@1.7.0 add open-edge-platform/skills",
            updated,
        )
        if updated != original:
            markdown.write_text(updated, encoding="utf-8")


def _install_flat_skills(config_entries: list[dict], repo_root: Path, dry_run: bool = False) -> bool:
    """
    Install configured skills into a fresh staging workspace:
      - add every configured skill, batched per (repo, ref) so each
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
    has_error = False

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
            if lock_meta.get("source") != entry["repo"]:
                logger.error("Skill '%s' installed from unexpected repository", name)
                has_error = True
            if (lock_meta.get("ref") or "main") != entry["ref"]:
                logger.error("Skill '%s' installed from unexpected revision", name)
                has_error = True
            source_path = _skill_path(entry, skill)
            expected_path = f"{source_path}/{name}/SKILL.md" if source_path else None
            actual_path = lock_meta.get("skillPath")
            if expected_path and actual_path != expected_path:
                has_error = True
                logger.error(
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
    for skill_name, cfg in config_by_skill.items():
        repo = cfg["repo"]
        local_skill_md = local_skills_dir / cfg["slug"] / skill_name / "SKILL.md"
        fm = parse_frontmatter(local_skill_md)
        if not fm.get("name"):
            print(f"  [skip] {skill_name} — no name in frontmatter", file=sys.stderr)
            continue

        product = cfg.get("product") or repo.split("/")[-1]
        print(f"  + [{product}] {fm['name']}", file=sys.stderr)
        rows.append({
            "product": product,
            "repo_url": f"https://github.com/{repo}",
            "skill_name": fm["name"],
            "skill_url": f"https://github.com/open-edge-platform/skills/tree/{skills_branch}/.agents/skills/{cfg['slug']}/{skill_name}",
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

    try:
        entries = load_skills_config(Path(args.config))
        validate_config_entries(entries)
    except ValueError as error:
        sys.exit(f"Error: {error}")
    if args.check_only:
        base_entries = load_skills_config(Path(args.base_config)) if args.base_config else None
        if base_entries:
            try:
                validate_config_entries(base_entries, require_slug=False)
            except ValueError as error:
                sys.exit(f"Error: {error}")
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
    print("Updating README skills index from the configured catalog …", file=sys.stderr)
    readme_path = repo_root / "README.md"

    if args.dry_run:
        print(build_skills_table(skills_lock, local_skills_dir, entries))
        return

    update_readme(readme_path, skills_lock, local_skills_dir, entries)
    print("README.md updated.", file=sys.stderr)


if __name__ == "__main__":
    main()
