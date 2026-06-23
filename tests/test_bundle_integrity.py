from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATH_MARKERS = ("/home/", "/data/" + "personal/")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


class BundleIntegrityTests(unittest.TestCase):
    def test_coderouterbench_tables_are_complete(self) -> None:
        root = ROOT / "data" / "coderouterbench"
        summary = read_json(root / "summary.json")

        self.assertEqual(summary["dataset"], "CodeRouterBench")
        self.assertEqual(summary["id"]["tasks"], 9999)
        self.assertEqual(summary["id"]["models"], 8)
        self.assertEqual(summary["id"]["rows"], 79992)
        self.assertEqual(summary["id"]["missing_cells"], 0)
        self.assertEqual(summary["id"]["splits"]["train"], {"rows": 48536, "tasks": 6067})
        self.assertEqual(summary["id"]["splits"]["val"], {"rows": 8104, "tasks": 1013})
        self.assertEqual(summary["id"]["splits"]["test"], {"rows": 23352, "tasks": 2919})
        self.assertEqual(summary["id"]["splits"]["trainval"]["rows"], 56640)
        self.assertEqual(summary["id"]["splits"]["trainval"]["tasks"], 7080)
        self.assertEqual(summary["ood176"]["tasks"], 176)
        self.assertEqual(summary["ood176"]["models"], 8)
        self.assertEqual(summary["ood176"]["rows"], 1408)
        self.assertEqual(summary["ood176"]["missing_cells"], 0)

        id_path = root / "id_results_long.csv"
        ood_path = root / "ood176_results_long.csv"
        with id_path.open(newline="") as fh:
            reader = csv.reader(fh)
            self.assertEqual(
                next(reader),
                ["task_id", "split", "dimension", "model", "score", "cost_usd", "total_tokens", "latency_ms"],
            )
            self.assertEqual(sum(1 for _ in reader), summary["id"]["rows"])

        for split, expected_rows in [
            ("train", 48536),
            ("val", 8104),
            ("test", 23352),
            ("trainval", 56640),
        ]:
            with (root / f"id_{split}_results_long.csv").open(newline="") as fh:
                reader = csv.DictReader(fh)
                self.assertEqual(sum(1 for _ in reader), expected_rows)

        with ood_path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            self.assertIn("task_id", reader.fieldnames or [])
            self.assertIn("model", reader.fieldnames or [])
            self.assertIn("resolved", reader.fieldnames or [])
            self.assertEqual(sum(1 for _ in reader), summary["ood176"]["rows"])

    def test_coderouterbench_dataset_card_controls_hf_preview(self) -> None:
        text = (ROOT / "data" / "coderouterbench" / "README.md").read_text()
        self.assertIn("configs:", text)
        self.assertIn("config_name: default", text)
        self.assertIn("path: id_train_results_long.csv", text)
        self.assertIn("path: id_val_results_long.csv", text)
        self.assertIn("path: id_test_results_long.csv", text)
        self.assertIn("path: ood176_results_long.csv", text)
        self.assertIn("https://huggingface.co/papers/2606.22902", text)
        self.assertIn("https://arxiv.org/abs/2606.22902", text)
        self.assertIn("arxiv:2606.22902", text)
        self.assertNotIn("path: data/id/voter_decisions", text)

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
