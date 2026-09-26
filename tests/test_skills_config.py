"""Regression tests for catalog parsing, migration, and consumer behavior."""

import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import generate_skill_compliance_report as report
from scripts import skills_config as catalog
from scripts import update_skills_index as index


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = {
            "products": [{
                "product": "Example",
                "repo": "example/skills",
                "ref": "main",
                "path": "skills/runtime",
                "skills": [
                    {"name": "first-skill"},
                    {"name": "second-skill", "path": "skills/inference"},
                ],
            }],
        }
        self.yaml_path = self.write("catalog.yaml", yaml.safe_dump(self.data))
        self.json_path = self.write("catalog.json", json.dumps(self.data))

    def write(self, name, content):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_formats_and_comments_are_equivalent(self):
        expected = self.data["products"]
        for suffix in ("yaml", "yml", "json"):
            text = json.dumps(self.data) if suffix == "json" else "# Comment\n" + yaml.safe_dump(self.data)
            with self.subTest(suffix=suffix):
                self.assertEqual(catalog.load_skills_config(self.write(f"input.{suffix}", text)), expected)

    def test_repository_catalog_round_trip(self):
        entries = catalog.load_skills_config(catalog.DEFAULT_CONFIG)
        legacy = self.write("historical.json", json.dumps({"products": entries}))
        self.assertEqual(catalog.load_skills_config(legacy), entries)
        paths = {
            skill["name"]: index._skill_path(entry, skill)
            for entry in entries for skill in entry["skills"]
        }
        self.assertEqual(paths["physicalai-runtime-configuring-inference-pipeline"], "skills/inference")
        self.assertEqual(paths["physicalai-runtime-adding-a-camera-backend"], "skills/capture")
        self.assertEqual(paths["getitune-training-a-model"], "skills/library")
        self.assertEqual(paths["geti-using-the-pipeline"], "skills/application")

    def test_quoted_ambiguous_scalars_remain_strings(self):
        for ref in ("on", "yes", "null", "123", "2026-09-25"):
            with self.subTest(ref=ref):
                text = self.yaml_path.read_text().replace("ref: main", f'ref: "{ref}"')
                loaded = catalog.load_skills_config(self.write("quoted.yaml", text))
                self.assertEqual(loaded[0]["ref"], ref)

    def test_invalid_yaml_is_rejected_with_filename(self):
        invalid = [
            "", "null", "[]", "products: []", "products: [", "products:\n\t- bad",
            "products: []\nproducts: []",
            "products: []\n---\nproducts: []",
            "products: &items []", "products: *items",
            "products: !custom []", "products: !!seq []",
            "<<: {}\nproducts: []",
            "1: []", "? [complex, key]\n: []",
            "products: false", "products: 123", "products: null",
            self.yaml_path.read_text().replace("ref: main", "ref: main\n  ref: develop"),
        ]
        for text in invalid:
            with self.subTest(text=text):
                path = self.write("invalid.yaml", text)
                with self.assertRaises(ValueError) as error:
                    catalog.load_skills_config(path)
                self.assertIn(str(path), str(error.exception))

    def test_schema_and_source_safety(self):
        for field, values in {
            "repo": ("bad", "-option", "example/repo\n"),
            "ref": ("", " ", None, 123, True, "../main", "-main", "main\nbranch", "main\x00x"),
            "path": ("", "../skills", "skills/../bad", "skills//bad", "-option/skills"),
            "product": (" ", None),
            "skills": ([], ["first-skill"], [{"name": "-option"}], [{"name": "bad\n"}]),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    data = copy.deepcopy(self.data)
                    data["products"][0][field] = value
                    path = self.write("invalid.yaml", yaml.safe_dump(data))
                    with self.assertRaises(ValueError):
                        catalog.load_skills_config(path)

    def test_required_unknown_and_duplicate_fields(self):
        cases = []
        for field in ("product", "repo", "ref", "skills"):
            data = copy.deepcopy(self.data)
            del data["products"][0][field]
            cases.append(data)
        data = copy.deepcopy(self.data)
        data["extra"] = True
        cases.append(data)
        data = copy.deepcopy(self.data)
        data["products"][0]["extra"] = True
        cases.append(data)
        data = copy.deepcopy(self.data)
        data["products"][0]["skills"][0]["extra"] = True
        cases.append(data)
        data = copy.deepcopy(self.data)
        data["products"].append(copy.deepcopy(data["products"][0]))
        cases.append(data)
        data = copy.deepcopy(self.data)
        data["products"][0]["skills"].append({"name": "first-skill"})
        cases.append(data)
        data = copy.deepcopy(self.data)
        data["products"][0]["skills"][0]["path"] = "../bad"
        cases.append(data)
        for data in cases:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    catalog.load_skills_config(self.write("invalid.yaml", yaml.safe_dump(data)))

    def test_unquoted_non_string_refs_are_rejected(self):
        for ref in ("on", "yes", "null", "123", "2026-09-25"):
            with self.subTest(ref=ref):
                text = self.yaml_path.read_text().replace("ref: main", f"ref: {ref}")
                with self.assertRaises(ValueError):
                    catalog.load_skills_config(self.write("unquoted.yaml", text))

    def test_legacy_json_duplicate_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate catalog key"):
            catalog.load_skills_config(self.write("duplicate.json", '{"products": [], "products": []}'))

    def test_missing_unsupported_and_conflicting_catalogs(self):
        for path in (self.root / "missing.yaml", self.write("catalog.txt", self.yaml_path.read_text())):
            with self.subTest(path=path), self.assertRaises(ValueError):
                catalog.load_skills_config(path)
        yaml_path = self.write("skills-config.yaml", self.yaml_path.read_text())
        json_path = self.write("skills-config.json", self.json_path.read_text())
        for path in (yaml_path, json_path):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Both canonical"):
                catalog.load_skills_config(path)

    def test_equivalent_base_catalogs_do_not_query_github(self):
        head = catalog.load_skills_config(self.yaml_path)
        for path in (self.json_path, self.yaml_path):
            with self.subTest(path=path), patch.object(index, "urlopen") as request, redirect_stderr(io.StringIO()):
                self.assertTrue(index.check_skills_exist(head, base_entries=catalog.load_skills_config(path)))
                request.assert_not_called()

    def test_added_and_relocated_skills_are_checked(self):
        base = catalog.load_skills_config(self.json_path)
        head = copy.deepcopy(base)
        head[0]["skills"][1]["path"] = "skills/new"
        head[0]["skills"].append({"name": "third-skill"})
        with patch.object(index, "urlopen") as request, redirect_stderr(io.StringIO()):
            request.return_value.__enter__.return_value.status = 200
            self.assertTrue(index.check_skills_exist(head, base_entries=base))
            urls = [call.args[0].full_url for call in request.call_args_list]
        self.assertEqual(urls, [
            "https://api.github.com/repos/example/skills/contents/skills/new/second-skill/SKILL.md?ref=main",
            "https://api.github.com/repos/example/skills/contents/skills/runtime/third-skill/SKILL.md?ref=main",
        ])

    def test_invalid_head_or_base_cannot_cause_side_effects(self):
        invalid = self.write("invalid.yaml", "products: []")
        cases = [
            ["--config", str(invalid)],
            ["--config", str(invalid), "--dry-run"],
            ["--config", str(invalid), "--no-install"],
            ["--config", str(self.yaml_path), "--check-only", "--base-config", str(invalid)],
            ["--config", str(self.yaml_path), "--check-only", "--base-config", str(self.root / "missing.json")],
        ]
        for args in cases:
            with (
                self.subTest(args=args),
                patch.object(sys, "argv", ["update_skills_index.py", *args]),
                patch.object(index, "install_skills") as install,
                patch.object(index, "update_readme") as update,
                patch.object(index, "urlopen") as request,
            ):
                with self.assertRaises(SystemExit):
                    index.main()
                install.assert_not_called()
                update.assert_not_called()
                request.assert_not_called()

    def test_cli_modes_and_defaults(self):
        for args, install_expected, update_expected in [
            ([], True, True), (["--install"], True, True),
            (["--no-install"], False, True), (["--dry-run"], True, False),
            (["--check-only"], False, False),
        ]:
            with (
                self.subTest(args=args),
                patch.object(sys, "argv", ["update_skills_index.py", *args]),
                patch.object(index, "load_skills_config", return_value=self.data["products"]) as load,
                patch.object(index, "install_skills", return_value=True) as install,
                patch.object(index, "load_skills_lock", return_value={"first-skill": {}}),
                patch.object(index, "update_readme") as update,
                patch.object(index, "build_skills_table", return_value="table"),
                patch.object(index, "check_skills_exist", return_value=True),
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()),
            ):
                index.main()
                load.assert_called_once_with(catalog.DEFAULT_CONFIG)
                self.assertEqual(install.called, install_expected)
                self.assertEqual(update.called, update_expected)
                if install_expected:
                    self.assertEqual(install.call_args.kwargs["dry_run"], "--dry-run" in args)

    def test_install_plan_and_readme_are_format_independent(self):
        skills_root = self.root / ".agents" / "skills"
        entries = catalog.load_skills_config(self.yaml_path)
        lock = {}
        for skill in entries[0]["skills"]:
            name = skill["name"]
            directory = skills_root / name
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
            lock[name] = {
                "source": entries[0]["repo"],
                "ref": "main",
                "skillPath": f"{index._skill_path(entries[0], skill)}/{name}/SKILL.md",
            }
        self.write("skills-lock.json", json.dumps({"skills": lock}))
        plans, tables = [], []
        for path in (self.json_path, self.yaml_path):
            entries = catalog.load_skills_config(path)
            with patch.object(index, "_run") as run, self.assertLogs(index.logger, level="INFO") as logs:
                self.assertTrue(index.install_skills(entries, self.root, dry_run=True))
                run.assert_not_called()
                plans.append(logs.output)
            with (
                patch.object(index, "_skills_repo_branch", return_value="main"),
                patch.object(index, "datetime") as clock,
                redirect_stderr(io.StringIO()),
            ):
                clock.now.return_value.strftime.return_value = "fixed timestamp"
                tables.append(index.build_skills_table(lock, skills_root, entries))
        self.assertEqual(plans[0], plans[1])
        self.assertFalse(any("npx skills remove" in line for line in plans[0]))
        self.assertEqual(tables[0], tables[1])
        self.assertIn("**1 products, 2 skills**", tables[0])
        self.assertIn("/tree/main/.agents/skills/second-skill", tables[0])

    def test_compliance_mapping_and_links_are_format_independent(self):
        (self.root / "first-skill" / "example-prompts").mkdir(parents=True)
        with patch.dict("os.environ", {"GITHUB_REF_NAME": "main"}), redirect_stdout(io.StringIO()):
            old = report.SkillComplianceReportGenerator(self.root, skills_config_path=str(self.json_path))
            new = report.SkillComplianceReportGenerator(self.root, skills_config_path=str(self.yaml_path))
        self.assertEqual(old.skills_config, {"first-skill": "Example", "second-skill": "Example"})
        self.assertEqual(old.skills_config, new.skills_config)
        self.assertEqual(old.skills_prompts_url, new.skills_prompts_url)
        self.assertTrue(new.skills_prompts_url["first-skill"].endswith("/first-skill/example-prompts"))
        self.assertEqual(new.skills_prompts_url["second-skill"], "")

    def test_compliance_report_rejects_invalid_or_missing_config(self):
        for path in (self.write("invalid.yaml", "products: []"), self.root / "missing.yaml"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                report.SkillComplianceReportGenerator(self.root, skills_config_path=str(path))
        with (
            patch.object(report, "DEFAULT_CONFIG", self.root / "missing.yaml"),
            patch.object(report.SkillComplianceReportGenerator, "scan_skills") as scan,
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(ValueError):
                report.main()
            scan.assert_not_called()

    def test_base_workflow_selects_actual_format(self):
        workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/check-skills-config.yml").read_text())
        step = next(step for step in workflow["jobs"]["check-skills"]["steps"] if step.get("id") == "base-config")
        git_mock = """
        git() {
          if [[ "$1" == cat-file ]]; then
            case "$3" in
              *:skills-config.yaml) [[ "$HAS_YAML" == true ]];;
              *:skills-config.json) [[ "$HAS_JSON" == true ]];;
              *) return 1;;
            esac
          elif [[ "$1" == show ]]; then
            printf '%s\\n' "$2"
          else
            return 1
          fi
        }
        """
        for has_yaml, has_json, expected in [
            ("true", "false", "yaml"), ("false", "true", "json"),
            ("true", "true", None), ("false", "false", None),
        ]:
            with self.subTest(yaml=has_yaml, json=has_json):
                output = self.write("output", "")
                result = subprocess.run(
                    ["bash", "-e", "-c", git_mock + step["run"]],
                    env={
                        "BASE_SHA": "a" * 40, "RUNNER_TEMP": str(self.root),
                        "GITHUB_OUTPUT": str(output), "HAS_YAML": has_yaml, "HAS_JSON": has_json,
                    },
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode == 0, expected is not None, result.stderr)
                if expected:
                    self.assertEqual(output.read_text().strip(), f"path={self.root}/skills-config.base.{expected}")
                    self.assertEqual(
                        (self.root / f"skills-config.base.{expected}").read_text().strip(),
                        f"{'a' * 40}:skills-config.{expected}",
                    )
                else:
                    self.assertEqual(output.read_text(), "")


if __name__ == "__main__":
    unittest.main()
