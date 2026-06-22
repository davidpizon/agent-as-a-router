from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATH_MARKERS = ("/home/", "/data/" + "personal/")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


class BundleIntegrityTests(unittest.TestCase):
    def test_ood176_matrix_is_complete_and_path_sanitized(self) -> None:
        path = ROOT / "data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json"
        data = read_json(path)

        self.assertEqual(len(data["ids"]), 176)
        self.assertEqual(len(data["models"]), 8)
        self.assertEqual(set(data["ids"]), set(data["matrix"]))

        models = set(data["models"])
        for task_id in data["ids"]:
            self.assertEqual(set(data["matrix"][task_id]), models, task_id)

        metadata = data["metadata"]
        counts = {"old112": 0, "new64": 0}
        for task_id, row in metadata.items():
            for marker in PRIVATE_PATH_MARKERS:
                self.assertNotIn(marker, row.get("prompt_source", ""))
            counts[row["source_split"]] += 1
            self.assertIn(task_id, data["ids"])

        self.assertEqual(counts, {"old112": 112, "new64": 64})
        self.assertEqual(data["summary"]["old112_prompt_source"], "data/matrices/phase2_ood/unified/tasks.jsonl")
        self.assertEqual(data["summary"]["new64_prompt_source"], "data/matrices/phase2_ood/unified/tasks.jsonl")

    def test_new64_raw_matrix_counts(self) -> None:
        data = read_json(ROOT / "data/matrices/phase2_ood/raw/new64/matrix.json")
        self.assertEqual(data["kept_counts"], {"featurebench": 49, "longcli": 14, "swe_ci": 1})
        self.assertEqual(len(data["matrix_rows"]), 64)
        self.assertEqual(len(data["models"]), 8)
        self.assertEqual(len(data["excluded_swe_ci_task_ids"]), 8)

    def test_reference_baseline_outputs_are_complete(self) -> None:
        payload = read_json(ROOT / "outputs/baselines_ood176/baseline_metrics.json")
        self.assertEqual(payload["n"], 176)
        self.assertEqual(payload["matrix_path"], "data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json")
        self.assertEqual(len(payload["metrics"]), 14)
        self.assertEqual(len(payload["table_rows"]), 15)

        for metric in payload["metrics"]:
            self.assertEqual(metric["n"], 176, metric["method"])
            self.assertEqual(metric["decision_count"], 176, metric["method"])
            self.assertEqual(metric["missing_decisions"], 0, metric["method"])
            source = metric.get("published_source_file", "")
            for marker in PRIVATE_PATH_MARKERS:
                self.assertNotIn(marker, source)

        for path in (ROOT / "outputs/baselines_ood176/decisions").glob("*.jsonl"):
            with path.open() as fh:
                self.assertEqual(sum(1 for _ in fh), 176, path.name)

    def test_core_and_baseline_modules_import(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        sys.path.insert(0, str(ROOT))

        from acrouter_repro.ood_repro import OODData  # noqa: PLC0415
        from src.routing.baselines import RandomRouter  # noqa: PLC0415

        self.assertTrue(callable(OODData))
        self.assertEqual(RandomRouter(seed=1).name, "random")


if __name__ == "__main__":
    unittest.main()
