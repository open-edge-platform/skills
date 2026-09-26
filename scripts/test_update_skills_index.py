"""Regression tests for the grouped catalog (run with unittest discovery)."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import update_skills_index as index


class GroupedCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="skills-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = [{
            "product": "Example", "slug": "example", "repo": "owner/repo",
            "ref": "main", "path": "skills", "skills": [{"name": "example-one"}],
        }]
        self.content = "---\nname: example-one\ndescription: Example skill\n---\n"
        self.old = self.root / ".agents/skills/old/SKILL.md"
        self.old.parent.mkdir(parents=True)
        self.old.write_text("previous catalog")
        self.lock = self.root / "skills-lock.json"
        self.lock.write_text('{"skills": {"old": {}}}\n')

    def fake_cli(self, cmd, cwd, **kwargs):
        skills = {}
        for entry in self.config:
            for skill in entry["skills"]:
                name = skill["name"]
                directory = cwd / ".agents/skills" / name
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "SKILL.md").write_text(self.content.replace("example-one", name))
                (directory / "references").mkdir(exist_ok=True)
                (directory / "references/guide.md").write_text("bundled reference")
                skills[name] = {
                    "source": entry["repo"],
                    "ref": entry["ref"],
                    "skillPath": f"{index._skill_path(entry, skill)}/{name}/SKILL.md",
                }
        (cwd / "skills-lock.json").write_text(json.dumps({"version": 1, "skills": skills}))
        return 0

    def sync(self):
        with patch.object(index, "_run", side_effect=self.fake_cli):
            return index.install_skills(self.config, self.root)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def test_grouped_publish_preserves_resources_and_upstream_lock(self):
        self.assertTrue(self.sync())
        self.assertFalse(self.old.exists())
        target = self.root / ".agents/skills/example/example-one"
        self.assertEqual((target / "SKILL.md").read_text(), self.content)
        self.assertEqual((target / "references/guide.md").read_text(), "bundled reference")
        self.assertEqual(index.load_skills_lock(self.lock)["example-one"]["skillPath"],
                         "skills/example-one/SKILL.md")

    def test_second_sync_is_idempotent(self):
        self.assertTrue(self.sync())
        before = self.snapshot()
        self.assertTrue(self.sync())
        self.assertEqual(before, self.snapshot())

    def test_product_move_source_change_and_removal(self):
        self.config[0]["skills"].append({"name": "example-two"})
        self.assertTrue(self.sync())
        self.config[0].update(slug="renamed", path="new-source")
        self.config[0]["skills"].pop()
        self.assertTrue(self.sync())
        self.assertFalse((self.root / ".agents/skills/example").exists())
        self.assertTrue((self.root / ".agents/skills/renamed/example-one/SKILL.md").exists())
        self.assertEqual(set(index.load_skills_lock(self.lock)), {"example-one"})
        self.assertEqual(index.load_skills_lock(self.lock)["example-one"]["skillPath"],
                         "new-source/example-one/SKILL.md")

    def test_download_failure_preserves_previous_tree_and_lock(self):
        before = self.snapshot()
        with patch.object(index, "_run", return_value=1):
            self.assertFalse(index.install_skills(self.config, self.root))
        self.assertEqual(before, self.snapshot())

    def test_wrong_source_is_not_published(self):
        before = self.snapshot()
        def wrong_source(cmd, cwd, **kwargs):
            self.fake_cli(cmd, cwd)
            lock = cwd / "skills-lock.json"
            data = json.loads(lock.read_text())
            data["skills"]["example-one"]["skillPath"] = "wrong/SKILL.md"
            lock.write_text(json.dumps(data))
            return 0
        with patch.object(index, "_run", side_effect=wrong_source):
            self.assertFalse(index.install_skills(self.config, self.root))
        self.assertEqual(before, self.snapshot())

    def test_missing_or_mismatched_frontmatter_is_not_published(self):
        self.content = "---\nname: wrong\n---\n"
        before = self.snapshot()
        self.assertFalse(self.sync())
        self.assertEqual(before, self.snapshot())

    def test_wrong_repository_or_revision_is_not_published(self):
        before = self.snapshot()
        for key, value in (("source", "wrong/repo"), ("ref", "wrong-branch")):
            with self.subTest(key=key):
                def wrong_metadata(cmd, cwd, **kwargs):
                    self.fake_cli(cmd, cwd)
                    lock = cwd / "skills-lock.json"
                    data = json.loads(lock.read_text())
                    data["skills"]["example-one"][key] = value
                    lock.write_text(json.dumps(data))
                    return 0
                with patch.object(index, "_run", side_effect=wrong_metadata):
                    self.assertFalse(index.install_skills(self.config, self.root))
                self.assertEqual(before, self.snapshot())

    def test_product_only_changes_do_not_check_upstream_again(self):
        base = copy.deepcopy(self.config)
        del base[0]["slug"]
        with patch.object(index, "urlopen") as request:
            self.assertTrue(index.check_skills_exist(self.config, base_entries=base))
            request.assert_not_called()

    def test_nondefault_ref_and_skill_path_override(self):
        self.config[0]["ref"] = "develop"
        self.config[0]["skills"][0]["path"] = "library/skills"
        self.assertTrue(self.sync())
        metadata = index.load_skills_lock(self.lock)["example-one"]
        self.assertEqual(metadata["ref"], "develop")
        self.assertEqual(metadata["skillPath"], "library/skills/example-one/SKILL.md")

    def test_publish_failure_rolls_back(self):
        before = self.snapshot()
        copyfile = index.shutil.copyfile
        def fail_lock(source, destination, **kwargs):
            if Path(destination) == self.lock:
                raise OSError("simulated disk error")
            return copyfile(source, destination, **kwargs)
        with patch.object(index.shutil, "copyfile", side_effect=fail_lock):
            self.assertFalse(self.sync())
        self.assertEqual(before, self.snapshot())

    def test_dry_run_does_not_write_or_execute_cli(self):
        before = self.snapshot()
        with patch.object(index, "_run") as cli:
            self.assertTrue(index.install_skills(self.config, self.root, dry_run=True))
            cli.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_unsafe_or_duplicate_slugs_and_names_rejected(self):
        for slug in ("../escape", "/absolute", "", "-option", "with space"):
            with self.subTest(slug=slug):
                config = copy.deepcopy(self.config)
                config[0]["slug"] = slug
                with self.assertRaises(ValueError):
                    index.validate_config_entries(config)
        duplicate = copy.deepcopy(self.config) * 2
        with self.assertRaisesRegex(ValueError, "duplicate product slug"):
            index.validate_config_entries(duplicate)
        duplicate = copy.deepcopy(self.config) + copy.deepcopy(self.config)
        duplicate[1]["slug"] = "different"
        with self.assertRaisesRegex(ValueError, "duplicate skill name"):
            index.validate_config_entries(duplicate)

    def test_empty_catalog_or_product_is_rejected(self):
        with self.assertRaises(ValueError):
            index.validate_config_entries([])
        self.config[0]["skills"] = []
        with self.assertRaises(ValueError):
            index.validate_config_entries(self.config)

    def test_staged_symlinks_are_rejected(self):
        before = self.snapshot()
        def linked_skill(cmd, cwd, **kwargs):
            self.fake_cli(cmd, cwd)
            (cwd / ".agents/skills/example-one/link").symlink_to(self.old)
            return 0
        with patch.object(index, "_run", side_effect=linked_skill):
            self.assertFalse(index.install_skills(self.config, self.root))
        self.assertEqual(before, self.snapshot())

    def test_old_base_config_accepted_only_for_comparison(self):
        del self.config[0]["slug"]
        index.validate_config_entries(self.config, require_slug=False)
        with self.assertRaises(ValueError):
            index.validate_config_entries(self.config)

    def test_readme_uses_grouped_link(self):
        self.assertTrue(self.sync())
        with patch.object(index, "_skills_repo_branch", return_value="main"):
            table = index.build_skills_table(index.load_skills_lock(self.lock),
                                             self.root / ".agents/skills", self.config)
        self.assertIn("/.agents/skills/example/example-one", table)
        self.assertIn("1 products, 1 skills", table)

    def test_readme_does_not_require_untracked_lock(self):
        self.assertTrue(self.sync())
        table = index.build_skills_table({}, self.root / ".agents/skills", self.config)
        self.assertIn("1 products, 1 skills", table)

    def test_catalog_link_relocation_is_idempotent(self):
        markdown = self.root / "reference.md"
        markdown.write_text(
            "https://github.com/open-edge-platform/skills/tree/main/"
            ".agents/skills/example-one\n"
            "https://raw.githubusercontent.com/open-edge-platform/skills/main/"
            ".agents/skills/<name>/SKILL.md\n"
        )
        index.relocate_catalog_references(self.root, self.config)
        text = markdown.read_text()
        self.assertIn("/example/example-one", text)
        self.assertIn("/<product-slug>/<name>/SKILL.md", text)
        index.relocate_catalog_references(self.root, self.config)
        self.assertEqual(text, markdown.read_text())


if __name__ == "__main__":
    unittest.main()
