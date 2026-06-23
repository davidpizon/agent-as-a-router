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


def expected_cost(model: str, input_tokens: int, output_tokens: int, pricing: dict) -> float:
    price = pricing["models"][model]
    cost = (
        input_tokens * float(price["input_per_1m"])
        + output_tokens * float(price["output_per_1m"])
    ) / 1_000_000
    return round(cost, 9)


class BundleIntegrityTests(unittest.TestCase):
    def test_runtime_pricing_constants_match_release_pricing(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))

        from acrouter_repro.constants import PRICING_TABLE6  # noqa: PLC0415

        pricing = read_json(ROOT / "data" / "matrices" / "phase1_id" / "model_pricing.json")
        expected = {
            model: (
                float(row["input_per_1m"]),
                float(row["output_per_1m"]),
            )
            for model, row in pricing["models"].items()
        }
        self.assertEqual(PRICING_TABLE6, expected)

    def test_coderouterbench_tables_are_complete(self) -> None:
        root = ROOT / "data" / "coderouterbench"
        summary = read_json(root / "summary.json")
        pricing = read_json(ROOT / "data" / "matrices" / "phase1_id" / "model_pricing.json")

        self.assertEqual(summary["dataset"], "CodeRouterBench")
        self.assertEqual(summary["id"]["tasks"], 9999)
        self.assertEqual(summary["id"]["models"], 8)
        self.assertEqual(summary["id"]["rows"], 79992)
        self.assertEqual(summary["id"]["missing_cells"], 0)
        self.assertEqual(summary["id"]["missing_token_records"], 148)
        self.assertAlmostEqual(summary["id"]["cost_usd_total"], 408.082583, places=6)
        self.assertEqual(summary["id"]["splits"]["probing"]["rows"], 56640)
        self.assertEqual(summary["id"]["splits"]["probing"]["tasks"], 7080)
        self.assertEqual(summary["id"]["splits"]["probing"]["source_splits"], ["train", "val"])
        self.assertAlmostEqual(summary["id"]["splits"]["probing"]["cost_usd_total"], 291.957249, places=6)
        self.assertEqual(summary["id"]["splits"]["probing"]["missing_token_records"], 106)
        self.assertEqual(summary["id"]["splits"]["id_test"]["rows"], 23352)
        self.assertEqual(summary["id"]["splits"]["id_test"]["tasks"], 2919)
        self.assertEqual(summary["id"]["splits"]["id_test"]["source_splits"], ["test"])
        self.assertAlmostEqual(summary["id"]["splits"]["id_test"]["cost_usd_total"], 116.125334, places=6)
        self.assertEqual(summary["id"]["splits"]["id_test"]["missing_token_records"], 42)
        self.assertEqual(summary["ood176"]["tasks"], 176)
        self.assertEqual(summary["ood176"]["models"], 8)
        self.assertEqual(summary["ood176"]["rows"], 1408)
        self.assertEqual(summary["ood176"]["missing_cells"], 0)
        self.assertAlmostEqual(summary["ood176"]["cost_usd_total"], 422.147494, places=6)

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
            missing_token_rows = sum(row["cost_source"] == "missing_token_record_zero_total" for row in rows)
            self.assertEqual({row["split"] for row in rows}, {"probing", "id_test"})
            self.assertEqual({row["source_split"] for row in rows}, {"train", "val", "test"})
            self.assertEqual(nonzero_cost_rows, 79844)
            self.assertEqual(missing_token_rows, 148)
            self.assertAlmostEqual(sum(float(row["cost_usd"] or 0.0) for row in rows), 408.082583, places=6)
            for row in rows:
                self.assertAlmostEqual(
                    float(row["cost_usd"] or 0.0),
                    expected_cost(row["model"], int(row["input_tokens"] or 0), int(row["output_tokens"] or 0), pricing),
                    places=9,
                    msg=row["task_id"],
                )

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
            ood_rows = list(reader)
            self.assertEqual(len(ood_rows), summary["ood176"]["rows"])
            self.assertEqual({row["cost_source"] for row in ood_rows}, {"token_log_pricing"})
            self.assertAlmostEqual(sum(float(row["cost_usd"] or 0.0) for row in ood_rows), 422.147494, places=6)
            for row in ood_rows:
                self.assertAlmostEqual(
                    float(row["cost_usd"] or 0.0),
                    expected_cost(row["model"], int(row["in_tok"] or 0), int(row["out_tok"] or 0), pricing),
                    places=9,
                    msg=row["task_id"],
                )

    def test_ood_matrices_use_release_pricing(self) -> None:
        pricing = read_json(ROOT / "data" / "matrices" / "phase1_id" / "model_pricing.json")
        matrix_paths = [
            ROOT / "data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json",
            ROOT / "data/matrices/phase2_ood/raw/old112/matrix.json",
            ROOT / "data/ood/matrix.json",
            ROOT / "data/baseline_inputs/swebench112_results/matrix.json",
        ]
        expected_totals = {
            "matrix_acrouter_ood176.json": 422.147494,
            "matrix.json": 268.639478,
        }
        for path in matrix_paths:
            payload = read_json(path)
            total = 0.0
            for task_id, model_cells in payload["matrix"].items():
                for model, cell in model_cells.items():
                    if model not in pricing["models"]:
                        continue
                    cost = expected_cost(
                        model,
                        int(cell.get("in_tok", 0) or 0),
                        int(cell.get("out_tok", 0) or 0),
                        pricing,
                    )
                    self.assertAlmostEqual(
                        float(cell.get("cost_usd", 0.0) or 0.0),
                        cost,
                        places=9,
                        msg=f"{path}:{task_id}:{model}",
                    )
                    total += cost
            self.assertAlmostEqual(total, expected_totals[path.name], places=6)

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
        self.assertIn("https://github.com/LanceZPF/agent-as-a-router", text)
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
