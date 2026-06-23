"""Data management for the routing framework.

Loads oracle labels, computes 3-model oracle, loads task data and result tokens,
performs deterministic train/val/test splitting.
"""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .base import BACKEND_MODELS, MODEL_DATA_ALIASES, MODEL_DATA_REVERSE, SANITIZE_FIELDS

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data"
_DEFAULT_SPLITS_DIR = _DEFAULT_DATA_DIR / "routing" / "splits"


_DEFAULT_EXCLUDE_DIMS = frozenset({"agentic_programming"})


@dataclass
class DataManager:
    data_dir: Path = field(default_factory=lambda: _DEFAULT_DATA_DIR)
    splits_dir: Path = field(default_factory=lambda: _DEFAULT_SPLITS_DIR)
    seed: str = "coding-router-v1"
    exclude_dims: frozenset[str] = field(default_factory=lambda: _DEFAULT_EXCLUDE_DIMS)

    # Loaded data
    tasks: dict[str, dict] = field(default_factory=dict, repr=False)           # task_id -> sanitized task
    oracle_labels: dict[str, dict] = field(default_factory=dict, repr=False)   # task_id -> oracle record
    result_tokens: dict[str, dict[str, dict]] = field(default_factory=dict, repr=False)  # task_id -> model -> {input_tokens, output_tokens}
    train: list[str] = field(default_factory=list, repr=False)
    val: list[str] = field(default_factory=list, repr=False)
    test: list[str] = field(default_factory=list, repr=False)

    # Oracle: best model per task
    oracle_best: dict[str, str] = field(default_factory=dict, repr=False)  # task_id -> best_model

    def load(self) -> "DataManager":
        """Load all data and perform splitting. Returns self for chaining."""
        self._load_oracle_labels()
        self._load_result_tokens()
        self._compute_oracle()
        self._load_tasks()
        self._split()
        return self

    @staticmethod
    def _canonicalize_scores(scores: dict) -> dict:
        """Translate data-file model names to canonical BACKEND_MODELS names."""
        return {MODEL_DATA_REVERSE.get(k, k): v for k, v in scores.items()}

    def _load_oracle_labels(self):
        """Load oracle_labels.jsonl, keeping tasks with at least 2 backend models scored."""
        path = self.data_dir / "analysis" / "oracle_labels.jsonl"
        with open(path) as f:
            for line in f:
                record = json.loads(line)
                # Skip excluded dimensions
                if record.get("dimension") in self.exclude_dims:
                    continue
                # Translate legacy model names in scores to canonical names
                record["all_scores"] = self._canonicalize_scores(record.get("all_scores", {}))
                scores = record["all_scores"]
                # Require at least 2 backend models to have scores (minimum for routing)
                n_scored = sum(1 for m in BACKEND_MODELS if m in scores)
                if n_scored >= 2:
                    self.oracle_labels[record["task_id"]] = record

    def _compute_oracle(self):
        """Compute oracle via paper lex-tiebreak:
        (1) max performance, (2) min dollar cost, (3) min total tokens, (4) alphabetical.
        """
        pricing_path = _PROJECT_ROOT / "data" / "matrices" / "phase1_id" / "model_pricing.json"
        legacy_pricing_path = _PROJECT_ROOT / "configs" / "model_pricing.json"
        pricing = {}
        if pricing_path.exists():
            pricing = json.loads(pricing_path.read_text()).get("models", {})
        elif legacy_pricing_path.exists():
            pricing = json.loads(legacy_pricing_path.read_text()).get("models", {})
        for task_id, record in self.oracle_labels.items():
            scores = record["all_scores"]
            available = [m for m in BACKEND_MODELS if m in scores]
            if not available:
                self.oracle_best[task_id] = BACKEND_MODELS[0]
                continue
            best_model = max(
                available,
                key=lambda m: (
                    scores.get(m, 0.0),
                    -self._get_cost_for_oracle(task_id, m, pricing),
                    -self._get_token_count_for_oracle(task_id, m),
                    m,
                ),
            )
            self.oracle_best[task_id] = best_model

    def _get_token_count_for_oracle(self, task_id: str, model: str) -> int:
        """Get total token count for oracle tiebreaking. Called before result_tokens is fully loaded."""
        tokens = self.result_tokens.get(task_id, {}).get(model, {})
        return tokens.get("input_tokens", 0) + tokens.get("output_tokens", 0)

    def _get_cost_for_oracle(self, task_id: str, model: str, pricing: dict) -> float:
        """Per-task USD cost; lower is better (lex-tiebreak stage 2)."""
        tokens = self.result_tokens.get(task_id, {}).get(model, {})
        p = pricing.get(model, {})
        return (tokens.get("input_tokens", 0) * p.get("input_per_1m", 0) / 1e6
                + tokens.get("output_tokens", 0) * p.get("output_per_1m", 0) / 1e6)

    def _load_result_tokens(self):
        """Load per-task token usage from results/ for each backend model."""
        results_dir = self.data_dir / "results"
        for model in BACKEND_MODELS:
            # Try canonical name first, then data alias (e.g., Qwen3-Max -> 通义千问Max)
            model_dir = results_dir / model
            if not model_dir.exists():
                data_name = MODEL_DATA_ALIASES.get(model)
                if data_name:
                    model_dir = results_dir / data_name
            if not model_dir.exists():
                continue
            for jsonl_file in model_dir.glob("*.jsonl"):
                with open(jsonl_file) as f:
                    for line in f:
                        record = json.loads(line)
                        task_id = record["task_id"]
                        if task_id not in self.oracle_labels:
                            continue
                        if task_id not in self.result_tokens:
                            self.result_tokens[task_id] = {}
                        self.result_tokens[task_id][model] = {
                            "input_tokens": record.get("input_tokens", 0),
                            "output_tokens": record.get("output_tokens", 0),
                        }

    def _load_tasks(self):
        """Load task content from processed/ JSONL files (sanitized)."""
        processed_dir = self.data_dir / "processed"
        for jsonl_file in processed_dir.glob("*.jsonl"):
            with open(jsonl_file) as f:
                for line in f:
                    task = json.loads(line)
                    task_id = task.get("task_id")
                    if task_id and task_id in self.oracle_labels:
                        self.tasks[task_id] = {
                            k: v for k, v in task.items() if k not in SANITIZE_FIELDS
                        }

    def _split(self):
        """Deterministic 60/10/30 split using md5(task_id + seed)."""
        self.train, self.val, self.test = [], [], []
        for task_id in sorted(self.oracle_labels.keys()):
            h = hashlib.md5(f"{task_id}{self.seed}".encode()).hexdigest()
            bucket = int(h[:8], 16) % 100
            if bucket < 60:
                self.train.append(task_id)
            elif bucket < 70:
                self.val.append(task_id)
            else:
                self.test.append(task_id)

        # Save splits
        self.splits_dir.mkdir(parents=True, exist_ok=True)
        for name, ids in [("train", self.train), ("val", self.val), ("test", self.test)]:
            with open(self.splits_dir / f"{name}.json", "w") as f:
                json.dump(ids, f)

    def get_split(self, split: str) -> list[str]:
        """Get task IDs for a split."""
        splits = {"train": self.train, "val": self.val, "test": self.test}
        if split not in splits:
            raise ValueError(f"Invalid split '{split}'. Must be one of: {list(splits.keys())}")
        return splits[split]

    def get_score(self, task_id: str, model: str):
        """Look up the score for a task-model pair. Returns None if no score exists."""
        record = self.oracle_labels.get(task_id)
        if not record:
            return None
        scores = record.get("all_scores", {})
        if model not in scores:
            return None
        return scores[model]

    def get_backend_tokens(self, task_id: str, model: str) -> dict:
        """Look up token usage for a task-model pair."""
        return self.result_tokens.get(task_id, {}).get(model, {"input_tokens": 0, "output_tokens": 0})

    def get_oracle_model(self, task_id: str) -> str:
        """Get the 3-model oracle's best model for a task."""
        return self.oracle_best.get(task_id, BACKEND_MODELS[0])

    def get_oracle_score(self, task_id: str) -> float:
        """Get the oracle (best achievable) score for a task."""
        return self.get_score(task_id, self.get_oracle_model(task_id))

    def get_task(self, task_id: str) -> Optional[dict]:
        """Get sanitized task content."""
        return self.tasks.get(task_id)

    def get_dimension_best_models(self) -> dict[str, str]:
        """Compute the best model per dimension from training data."""
        dim_scores: dict[str, dict[str, list[float]]] = {}
        for task_id in self.train:
            task = self.tasks.get(task_id)
            if not task:
                continue
            dim = task.get("dimension", "unknown")
            if dim not in dim_scores:
                dim_scores[dim] = {m: [] for m in BACKEND_MODELS}
            for m in BACKEND_MODELS:
                s = self.get_score(task_id, m)
                if s is not None:
                    dim_scores[dim][m].append(s)

        result = {}
        for dim, model_scores in dim_scores.items():
            best_model = max(
                BACKEND_MODELS,
                key=lambda m: sum(model_scores[m]) / max(len(model_scores[m]), 1) if model_scores[m] else -1,
            )
            result[dim] = best_model
        return result
