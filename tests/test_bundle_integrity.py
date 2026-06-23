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
        self.assertEqual(summary["id"]["missing_token_records"], 148)
        self.assertAlmostEqual(summary["id"]["cost_usd_total"], 618.179743, places=6)
        self.assertEqual(summary["id"]["splits"]["probing"]["rows"], 56640)
        self.assertEqual(summary["id"]["splits"]["probing"]["tasks"], 7080)
        self.assertEqual(summary["id"]["splits"]["probing"]["source_splits"], ["train", "val"])
        self.assertEqual(summary["id"]["splits"]["id_test"]["rows"], 23352)
        self.assertEqual(summary["id"]["splits"]["id_test"]["tasks"], 2919)
        self.assertEqual(summary["id"]["splits"]["id_test"]["source_splits"], ["test"])
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
                [
                    "task_id",
                    "split",
                    "source_split",
                    "dimension",
                    "model",
                    "score",
                    "cost_usd",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "latency_ms",
                    "cost_source",
                ],
            )
            self.assertEqual(sum(1 for _ in reader), summary["id"]["rows"])

        with id_path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            nonzero_cost_rows = sum(float(row["cost_usd"] or 0.0) > 0 for row in rows)
            missing_token_rows = sum(row["cost_source"] == "missing_token_record" for row in rows)
            self.assertEqual({row["split"] for row in rows}, {"probing", "id_test"})
            self.assertEqual({row["source_split"] for row in rows}, {"train", "val", "test"})
            self.assertEqual(nonzero_cost_rows, 79844)
            self.assertEqual(missing_token_rows, 148)
            self.assertAlmostEqual(sum(float(row["cost_usd"] or 0.0) for row in rows), 618.179743, places=6)

        for split, expected_rows in [
            ("probing", 56640),
            ("test", 23352),
        ]:
            with (root / f"id_{split}_results_long.csv").open(newline="") as fh:
                reader = csv.DictReader(fh)
                self.assertEqual(sum(1 for _ in reader), expected_rows)

        for obsolete in [
            "id_train_results_long.csv",
            "id_train_tasks.jsonl",
            "id_val_results_long.csv",
            "id_val_tasks.jsonl",
            "id_trainval_results_long.csv",
            "id_trainval_tasks.jsonl",
            "id_id_test_results_long.csv",
            "id_id_test_tasks.jsonl",
        ]:
            self.assertFalse((root / obsolete).exists(), obsolete)

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
        self.assertIn("path: id_probing_results_long.csv", text)
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
