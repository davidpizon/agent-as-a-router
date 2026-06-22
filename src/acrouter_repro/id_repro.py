"""ID reproduction: per-dimension hard voter selection and paper metrics."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re

from .constants import (
    BACKEND_MODELS,
    ID_VOTERS,
    MODEL_ALIASES,
    PRICING_TABLE6,
    REWARD_COST_WEIGHT,
)
from .io_utils import read_json, read_jsonl, write_json, write_jsonl


class IDData:
    def __init__(self, data_root: Path):
        self.root = data_root
        self.oracle_labels = self._load_oracle_labels()
        self.tokens = self._load_tokens()
        self.dimensions = {
            row["task_id"]: row["dimension"]
            for row in read_jsonl(self.root / "task_dimensions.jsonl")
        }
        self.splits = {
            name: read_json(self.root / "splits" / f"{name}.json")
            for name in ["train", "val", "test"]
        }
        self.voter_picks = self._load_voter_picks()
        self.perf_oracle_model = {
            tid: self._perf_oracle_model(tid)
            for tid in self.oracle_labels
        }
        self.reward_oracle_value = {
            tid: self._reward_oracle_value(tid)
            for tid in self.oracle_labels
        }

    def _canonical_model(self, model: str) -> str:
        return MODEL_ALIASES.get(model, model)

    def _load_oracle_labels(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for row in read_jsonl(self.root / "oracle_labels.jsonl"):
            scores = {
                self._canonical_model(model): float(score)
                for model, score in row.get("all_scores", {}).items()
            }
            if sum(model in scores for model in BACKEND_MODELS) >= 2:
                out[row["task_id"]] = scores
        return out

    def _load_tokens(self) -> dict[str, dict[str, dict[str, int]]]:
        out: dict[str, dict[str, dict[str, int]]] = {}
        for row in read_jsonl(self.root / "tokens.jsonl"):
            tid = row["task_id"]
            model = self._canonical_model(row["model"])
            out.setdefault(tid, {})[model] = {
                "input_tokens": int(row.get("input_tokens", 0) or 0),
                "output_tokens": int(row.get("output_tokens", 0) or 0),
            }
        return out

    def _load_voter_picks(self) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        decisions_dir = self.root / "voter_decisions"
        for voter in ID_VOTERS:
            path = decisions_dir / f"{voter}.jsonl"
            if not path.exists():
                continue
            out[voter] = {
                row["task_id"]: self._canonical_model(row["chosen_model"])
                for row in read_jsonl(path)
            }
        return out

    def split(self, name: str) -> list[str]:
        if name not in self.splits:
            raise ValueError(f"Unknown split {name!r}; expected train, val, or test")
        return self.splits[name]

    def score(self, task_id: str, model: str) -> float:
        return self.oracle_labels.get(task_id, {}).get(model, 0.0)

    def cost(self, task_id: str, model: str) -> float:
        toks = self.tokens.get(task_id, {}).get(model, {})
        input_tokens = toks.get("input_tokens", 0)
        output_tokens = toks.get("output_tokens", 0)
        input_price, output_price = PRICING_TABLE6.get(model, (0.0, 0.0))
        return (input_tokens / 1_000_000 * input_price) + (
            output_tokens / 1_000_000 * output_price
        )

    def _token_count(self, task_id: str, model: str) -> int:
        toks = self.tokens.get(task_id, {}).get(model, {})
        return toks.get("input_tokens", 0) + toks.get("output_tokens", 0)

    def _perf_oracle_model(self, task_id: str) -> str:
        scores = self.oracle_labels.get(task_id, {})
        available = [model for model in BACKEND_MODELS if model in scores]
        if not available:
            return BACKEND_MODELS[0]
        return max(
            available,
            key=lambda model: (
                scores.get(model, 0.0),
                -self._token_count(task_id, model),
                model,
            ),
        )

    def _reward_oracle_value(self, task_id: str) -> float:
        scores = self.oracle_labels.get(task_id, {})
        available = [model for model in BACKEND_MODELS if model in scores]
        if not available:
            return 0.0
        return max(
            self.score(task_id, model) - REWARD_COST_WEIGHT * self.cost(task_id, model)
            for model in available
        )


def select_per_dimension(data: IDData, tune_ids: list[str]) -> dict[str, str]:
    by_dim: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for tid in tune_ids:
        dim = data.dimensions.get(tid)
        if not dim:
            continue
        for voter, picks in data.voter_picks.items():
            if tid in picks:
                by_dim[dim][voter].append(data.score(tid, picks[tid]))

    selection: dict[str, str] = {}
    for dim, voter_scores in by_dim.items():
        selection[dim] = max(
            voter_scores,
            key=lambda voter: sum(voter_scores[voter]) / len(voter_scores[voter]),
        )
    return selection


def route_per_dimension(
    data: IDData,
    selection: dict[str, str],
    eval_ids: list[str],
) -> list[dict]:
    rows: list[dict] = []
    for tid in eval_ids:
        dim = data.dimensions.get(tid)
        voter = selection.get(dim, "dimension_best")
        chosen = data.voter_picks.get(voter, {}).get(tid)
        if chosen:
            rows.append(
                {
                    "task_id": tid,
                    "chosen_model": chosen,
                    "voter": voter,
                    "dimension": dim,
                }
            )
    return rows


def group_key(data: IDData, task_id: str, mode: str) -> str:
    dim = data.dimensions.get(task_id, "unknown")
    parts = task_id.split("_")
    if mode == "dimension":
        return dim
    if mode == "source":
        match = re.match(r"(dim\d+)_([^_/]+)", task_id)
        return match.group(2) if match else task_id.split("/")[0]
    if mode == "first3":
        return "_".join(parts[:3])
    raise ValueError(f"unknown group mode: {mode}")


def _candidate_value(data: IDData, task_id: str, model: str, objective: str) -> float | None:
    if model not in data.oracle_labels.get(task_id, {}):
        return None
    value = data.score(task_id, model)
    if objective == "reward":
        value -= REWARD_COST_WEIGHT * data.cost(task_id, model)
    elif objective != "perf":
        raise ValueError(f"unknown objective: {objective}")
    return value


def learn_hierarchical_group_model_map(
    data: IDData,
    tune_ids: list[str],
    modes: tuple[str, ...] = ("first3", "source", "dimension"),
    min_count: int = 50,
    shrink: float = 500.0,
    objective: str = "perf",
) -> dict:
    global_stats: dict[str, list[float]] = defaultdict(list)
    grouped: dict[str, dict[str, dict[str, list[float]]]] = {
        mode: defaultdict(lambda: defaultdict(list)) for mode in modes
    }

    for tid in tune_ids:
        if tid not in data.oracle_labels:
            continue
        for model in BACKEND_MODELS:
            value = _candidate_value(data, tid, model, objective)
            if value is None:
                continue
            global_stats[model].append(value)
            for mode in modes:
                grouped[mode][group_key(data, tid, mode)][model].append(value)

    global_mean = {
        model: sum(values) / len(values)
        for model, values in global_stats.items()
        if values
    }
    fallback = max(global_mean, key=global_mean.get)
    levels = []
    for mode in modes:
        mapping = {}
        for key, model_values in grouped[mode].items():
            best_model = None
            best_value = -1e9
            for model, values in model_values.items():
                if len(values) < min_count:
                    continue
                value = (sum(values) + shrink * global_mean.get(model, 0.0)) / (
                    len(values) + shrink
                )
                if value > best_value:
                    best_model = model
                    best_value = value
            if best_model:
                mapping[key] = best_model
        levels.append({"mode": mode, "mapping": mapping})

    return {
        "policy": "hierarchical_group_model_map",
        "hyperparameter_selection": "train_fit_val_score_grid",
        "modes": list(modes),
        "min_count": min_count,
        "shrink": shrink,
        "objective": objective,
        "fallback_model": fallback,
        "levels": levels,
    }


def route_hierarchical_group_model_map(
    data: IDData,
    selection: dict,
    eval_ids: list[str],
) -> list[dict]:
    rows: list[dict] = []
    for tid in eval_ids:
        chosen = selection["fallback_model"]
        matched_key = None
        matched_mode = "fallback"
        for level in selection["levels"]:
            mode = level["mode"]
            key = group_key(data, tid, mode)
            if key in level["mapping"]:
                chosen = level["mapping"][key]
                matched_key = key
                matched_mode = mode
                break
        rows.append(
            {
                "task_id": tid,
                "chosen_model": chosen,
                "voter": "hierarchical_group_model_map",
                "dimension": data.dimensions.get(tid),
                "matched_mode": matched_mode,
                "matched_key": matched_key,
            }
        )
    return rows


def score_decisions(data: IDData, rows: list[dict]) -> dict:
    n = len(rows)
    total_perf = 0.0
    total_cost = 0.0
    cum_reg = 0.0
    correct = 0
    missing_score = 0

    for row in rows:
        tid = row["task_id"]
        model = row["chosen_model"]
        perf = data.score(tid, model)
        if tid not in data.oracle_labels or model not in data.oracle_labels.get(tid, {}):
            missing_score += 1
        cost = data.cost(tid, model)
        reward = perf - REWARD_COST_WEIGHT * cost
        total_perf += perf
        total_cost += cost
        cum_reg += data.reward_oracle_value.get(tid, reward) - reward
        correct += int(model == data.perf_oracle_model.get(tid))

    avg_perf = total_perf / n * 100 if n else 0.0
    return {
        "n": n,
        "AvgPerf%": round(avg_perf, 2),
        "CumReg": round(cum_reg, 1),
        "$Total": round(total_cost, 2),
        "Perf/$": round(avg_perf / total_cost, 2) if total_cost else float("inf"),
        "rAcc_perf_oracle": round(correct / n, 4) if n else 0.0,
        "missing_score": missing_score,
    }


def run_id(
    data_root: Path,
    output_dir: Path,
    tune_split: str = "val",
    eval_split: str = "test",
    policy: str = "hierarchical",
) -> dict:
    data = IDData(data_root)
    eval_ids = data.split(eval_split)
    if policy == "voter":
        tune_ids = data.split(tune_split)
        selection = select_per_dimension(data, tune_ids)
        decisions = route_per_dimension(data, selection, eval_ids)
        fit_splits = [tune_split]
        selection_protocol = "per_dimension_voter_selection"
    elif policy == "hierarchical":
        fit_splits = ["train"]
        if tune_split != "train":
            fit_splits.append(tune_split)
        tune_ids = [tid for split in fit_splits for tid in data.split(split)]
        selection = learn_hierarchical_group_model_map(data, tune_ids)
        decisions = route_hierarchical_group_model_map(data, selection, eval_ids)
        selection_protocol = "hierarchical_group_model_map"
    else:
        raise ValueError(f"unknown ID policy: {policy}")
    metrics = score_decisions(data, decisions)
    if eval_split in fit_splits and eval_split == "test":
        leakage_risk = "test_tuned_not_clean"
    elif eval_split in fit_splits:
        leakage_risk = "same_split_tuned"
    else:
        leakage_risk = "none"
    metrics.update(
        {
            "policy": policy,
            "tune_split": "+".join(fit_splits),
            "eval_split": eval_split,
            "selection_protocol": selection_protocol,
            "leakage_risk": leakage_risk,
        }
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "id_decisions.jsonl", decisions)
    write_json(output_dir / "id_selection.json", selection)
    write_json(output_dir / "id_metrics.json", metrics)
    return {"selection": selection, "metrics": metrics, "decisions": decisions}
