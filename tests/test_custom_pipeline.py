from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.pipeline import run_pipeline  # noqa: E402


class CustomPipelineTest(unittest.TestCase):
    def test_example_pipeline_runs_multiple_evaluations(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(ROOT / "configs" / "eval_pipeline.example.json", Path(tmp))

            self.assertEqual(result["matrix"], Path(tmp) / "matrix.json")
            self.assertTrue((Path(tmp) / "summary.csv").exists())
            self.assertTrue((Path(tmp) / "summary.md").exists())
            self.assertTrue((Path(tmp) / "decisions" / "ACRouter_custom_cascade.jsonl").exists())

            by_name = {row["router"]: row for row in result["summary"]}
            self.assertEqual(by_name["ACRouter custom cascade"]["n"], 3)
            self.assertEqual(by_name["ACRouter custom cascade"]["AvgPerf%"], 100.0)
            self.assertIn("Always toy-fast", by_name)
            self.assertIn("Oracle", by_name)

            results = json.loads((Path(tmp) / "results.json").read_text())
            resolved = json.loads((Path(tmp) / "resolved_config.json").read_text())
            self.assertEqual(results["matrix"], "matrix.json")
            self.assertEqual(resolved["_matrix_path"], "matrix.json")
            self.assertNotIn(str(ROOT), json.dumps(results))

    def test_duplicate_task_model_results_fail_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tasks.jsonl").write_text('{"task_id":"t1"}\n')
            (root / "results.jsonl").write_text(
                "\n".join(
                    [
                        '{"task_id":"t1","model":"m1","resolved":true}',
                        '{"task_id":"t1","model":"m1","resolved":false}',
                    ]
                )
                + "\n"
            )
            config = {
                "tasks_path": "tasks.jsonl",
                "results_path": "results.jsonl",
                "models": {"m1": {}},
                "evaluations": [{"type": "always", "model": "m1"}],
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config))

            with self.assertRaisesRegex(ValueError, "duplicate result row"):
                run_pipeline(config_path, root / "out")


if __name__ == "__main__":
    unittest.main()
