#!/usr/bin/env python3
"""Load and validate the skills catalog before any consumer acts on it."""

import argparse
import json
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "skills-config.yaml"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SKILL_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class _CatalogLoader(yaml.SafeLoader):
    """Accept a single, JSON-compatible YAML document without YAML indirection."""

    def compose_node(self, parent, index):
        event = self.peek_event()
        if isinstance(event, yaml.events.AliasEvent) or getattr(event, "anchor", None):
            raise ValueError("YAML anchors and aliases are not allowed")
        if getattr(event, "tag", None):
            raise ValueError("Explicit YAML tags are not allowed")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            if key_node.tag != "tag:yaml.org,2002:str":
                raise ValueError("Catalog keys must be strings; YAML merge keys are not allowed")
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"Duplicate catalog key: {key!r}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _validate_git_ref(ref: str) -> str:
    """Reject ref names that are unsafe to pass to git/GitHub tooling."""
    ref = ref.strip()
    if not ref:
        raise ValueError("ref must not be empty")
    if (
        ref.startswith(("-", "/", "."))
        or ref.endswith(("/", "."))
        or ".." in ref
        or "//" in ref
        or "@{" in ref
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in ref)
        or any(char in ref for char in ("~", "^", ":", "?", "*", "[", "\\"))
    ):
        raise ValueError(f"unsafe ref value: {ref!r}")
    return ref


def _validate_skill_path(path: str) -> str:
    """Reject path traversal and option-like path components."""
    cleaned = path.strip().strip("/")
    if not cleaned:
        raise ValueError("path must not be empty")
    segments = cleaned.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(f"unsafe path value: {path!r}")
    if any(segment.startswith("-") or not _SKILL_PATH_SEGMENT_RE.fullmatch(segment) for segment in segments):
        raise ValueError(f"unsafe path value: {path!r}")
    return cleaned


def validate_config_entries(entries: list[dict]) -> None:
    """Validate structure and source values, then normalize refs and paths."""
    schema = json.loads((REPO_ROOT / "skills-config.schema.json").read_text(encoding="utf-8"))
    error = next(Draft202012Validator(schema).iter_errors({"products": entries}), None)
    if error:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"{location}: {error.message}")
    names = set()
    for entry in entries:
        if not _REPO_RE.fullmatch(entry["repo"]):
            raise ValueError(f"unsafe repo value: {entry['repo']!r}")
        if not entry["product"].strip():
            raise ValueError("product must not be blank")
        entry["ref"] = _validate_git_ref(entry["ref"])
        if "path" in entry:
            entry["path"] = _validate_skill_path(entry["path"])
        for skill in entry["skills"]:
            name = skill["name"]
            if not _SKILL_NAME_RE.fullmatch(name):
                raise ValueError(f"unsafe skill name: {name!r}")
            if name in names:
                raise ValueError(f"Duplicate skill name: {name!r}")
            names.add(name)
            if "path" in skill:
                skill["path"] = _validate_skill_path(skill["path"])


def load_skills_config(config_path: Path) -> list[dict]:
    """Read YAML, failing before any partial catalog is used."""
    config_path = Path(config_path)
    try:
        if config_path.suffix not in {".yaml", ".yml"}:
            raise ValueError("Catalog extension must be .yaml or .yml")
        text = config_path.read_text(encoding="utf-8")
        data = yaml.load(text, Loader=_CatalogLoader)
        if not isinstance(data, dict) or set(data) != {"products"}:
            raise ValueError("Catalog must be a mapping containing only 'products'")
        entries = data["products"]
        validate_config_entries(entries)
        return entries
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ValueError(f"{config_path}: {error}") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    try:
        entries = load_skills_config(args.config)
    except ValueError as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Validated {len(entries)} products and {sum(len(entry['skills']) for entry in entries)} skills")


if __name__ == "__main__":
    main()
