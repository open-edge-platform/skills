import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


update_skills_index = load_module("update_skills_index", "scripts/update_skills_index.py")
run_multi_cli_eval = load_module("run_multi_cli_eval", "tools/run_multi_cli_eval.py")


class UpdateSkillsIndexValidationTests(unittest.TestCase):
    def test_validate_config_entries_accepts_safe_values(self):
        entries = [
            {
                "repo": "open-edge-platform/skills",
                "ref": "release-1.0",
                "path": "nested/skills/",
                "skills": [
                    {"name": "safe-skill", "path": "deeper/path/"},
                    "another-skill",
                ],
            }
        ]

        update_skills_index.validate_config_entries(entries)

        self.assertEqual(entries[0]["path"], "nested/skills")
        self.assertEqual(entries[0]["skills"][0]["path"], "deeper/path")

    def test_validate_config_entries_rejects_unsafe_values(self):
        entries = [
            {
                "repo": "open-edge-platform/skills",
                "ref": "main:danger",
                "skills": [{"name": "safe-skill", "path": "../escape"}],
            }
        ]

        with self.assertRaises(ValueError):
            update_skills_index.validate_config_entries(entries)


class RunMultiCliEvalPathSafetyTests(unittest.TestCase):
    def test_eval_dir_name_slugifies_untrusted_fields(self):
        eval_meta = {"id": "../7", "prompt": "Prompt", "eval_name": "../../Bad Name"}

        result = run_multi_cli_eval.eval_dir_name(eval_meta)

        self.assertEqual(result, "eval-7-bad-name")

    def test_save_run_writes_under_sanitized_config_directory(self):
        eval_meta = {"id": 5, "prompt": "Prompt", "eval_name": "Simple Eval"}
        result = run_multi_cli_eval.RunResult(response_text="ok")

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            run_dir = run_multi_cli_eval.save_run(workspace, "copilot", eval_meta, "../with skill", result)

            self.assertTrue(run_dir.is_dir())
            self.assertEqual(run_dir.relative_to(workspace).parts[:4], ("copilot", "eval-5-simple-eval", "with-skill", "run-1"))


if __name__ == "__main__":
    unittest.main()
