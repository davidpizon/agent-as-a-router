#!/usr/bin/env python3
"""Replay the paper-table OOD baselines on the unified OOD176 matrix.

The direct baselines are recomputed from the 176 task-model matrix. For
published OOD112 trained-policy baselines whose original OOD prompts are not in
this bundle, the Old112 portion replays the published decisions and the New64
portion uses a documented modal extension from those decisions.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = REPO_ROOT / "data" / "matrices" / "phase2_ood" / "unified" / "matrix_acrouter_ood176.json"
SWE112_RESULTS = REPO_ROOT / "data" / "baseline_inputs" / "swebench112_results"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "baselines_ood176"
DEFAULT_HF_DATASET_DIR = REPO_ROOT / ".hf" / "CodeRouterBench"
ACROUTER_DECISIONS = REPO_ROOT / "outputs" / "acrouter_ood176" / "ood_decisions.jsonl"
ACROUTER_METRICS = REPO_ROOT / "outputs" / "acrouter_ood176" / "ood_metrics.json"
TRAINED_MODELS_DIR = REPO_ROOT / "data" / "baseline_inputs" / "trained_models"

sys.path.insert(0, str(REPO_ROOT / "src"))
from acrouter_repro.hf_assets import (  # noqa: E402
    MINIMAL_DATASET_PATTERNS,
    download_coderouterbench,
    format_path,
    resolve_ood_matrix,
)

EPS1 = 1.0
EPS2 = -0.1
HASH_BUCKETS = 32

MODEL_ALIASES = {
    "Always-GLM5": "glm-5",
    "Always-GPT": "gpt-5.4",
    "Always-Kimi": "kimi-k2.5",
    "Always-MiniMax": "MiniMax-M2.7",
    "Always-Opus": "claude-opus-4-6",
    "Always-Qwen3.5+": "qwen3.5-plus",
    "Always-QwenMax": "Qwen3-Max",
    "Always-Sonnet": "claude-sonnet-4-6",
    "MiniMax-M2.5": "MiniMax-M2.7",
    "gpt-5.4-medium": "gpt-5.4",
    "kimi-k2.6": "kimi-k2.5",
    "qwen3.6-plus": "Qwen3-Max",
}


TABLE_ROWS = [
    ("Bound", "Oracle", 57.00, 0.0, 8.20),
    ("Agent-as-a-Router", "ACRouter (ours)", 49.98, 205.5, 3.79),
    ("Dynamic: Online Bandit", "LinTS", 46.48, 307.4, 4.49),
    ("Dynamic: Online Bandit", "LinUCB", 46.84, 296.9, 4.38),
    ("Static: Heuristic", "DimensionBest", 47.50, 277.4, 3.69),
    ("Static: Heuristic", "kNN Retrieval", 47.18, 286.7, 6.07),
    ("Static: Trained Policy", "LogReg", 47.26, 284.4, 6.27),
    ("Static: Trained Policy", "RouteLLM-BERT", 47.22, 285.5, 6.22),
    ("Static: Trained Policy", "TF-IDF+MLP", 46.97, 292.8, 6.11),
    ("Static: Trained Policy", "Qwen3.5-0.8B-Finetuned", 46.41, 309.1, 6.82),
    ("Static: Trained Policy", "RouteLLM-MF", 46.16, 316.5, 6.19),
    ("Single-Model Baselines", "Always-Opus 4.6", 43.83, 387.1, 1.29),
    ("Single-Model Baselines", "Always-Kimi-K2.5", 36.66, 593.3, 12.62),
    ("Single-Model Baselines", "Always-Qwen3.5-Plus", 37.16, 580.2, 2.05),
    ("Single-Model Baselines", "Random", 38.75, 533.6, 2.48),
]


PUBLISHED_REPLAY_BASELINES = {
    "LogReg": {
        "file": "T1_LogReg_metrics.json",
        "new64_router": "logreg",
        "note": "Old112 published decisions replayed; New64 is predicted by the saved LogReg router on real New64 prompts.",
    },
    "RouteLLM-BERT": {
        "file": "T4_RouteLLM_SW_metrics.json",
        "new64_router": "routellm_sw",
        "note": (
            "No published RouteLLM-BERT OOD112 decision file was found in this worktree; "
            "uses the available T4_RouteLLM_SW OOD112 decisions as the closest published RouteLLM proxy, "
            "and predicts New64 with the saved RouteLLM-SW router on real prompts."
        ),
    },
    "TF-IDF+MLP": {
        "file": "T2_TFIDF_MLP_metrics.json",
        "new64_router": "tfidf_mlp",
        "note": "Old112 published decisions replayed; New64 is predicted by the saved TF-IDF+MLP router on real New64 prompts.",
    },
    "Qwen3.5-0.8B-Finetuned": {
        "file": "L2_ft08b_router_v3_metrics.json",
        "note": (
            "Old112 uses the available L2_ft08b_router_v3 decisions; this file's published "
            "OOD112 resolved_pct is 25.00, not the 55.36 value in the provided LaTeX table. "
            "New64 uses modal extension."
        ),
    },
    "RouteLLM-MF": {
        "file": "T3_RouteLLM_MF_metrics.json",
        "new64_router": "routellm_mf",
        "note": "Old112 published decisions replayed; New64 is predicted by the saved RouteLLM-MF router on real New64 prompts.",
    },
}


@dataclass
class MatrixBundle:
    ids: list[str]
    models: list[str]
    matrix: dict[str, dict[str, dict]]
    metadata: dict[str, dict]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def normalize_model(model: str | None) -> str | None:
    if model is None:
        return None
    return MODEL_ALIASES.get(model, model)


def load_matrix(path: Path) -> MatrixBundle:
    raw = read_json(path)
    return MatrixBundle(
        ids=list(raw["ids"]),
        models=list(raw["models"]),
        matrix=raw["matrix"],
        metadata=raw.get("metadata", {}),
    )


def cell(bundle: MatrixBundle, task_id: str, model: str | None) -> dict:
    if model is None:
        return {}
    return bundle.matrix.get(task_id, {}).get(model, {})


def perf_of(bundle: MatrixBundle, task_id: str, model: str | None) -> float:
    return 1.0 if cell(bundle, task_id, model).get("resolved") else 0.0


def apply_ok_of(bundle: MatrixBundle, task_id: str, model: str | None) -> float:
    return 1.0 if cell(bundle, task_id, model).get("apply_ok") else 0.0


def cost_of(bundle: MatrixBundle, task_id: str, model: str | None) -> float:
    return float(cell(bundle, task_id, model).get("cost_usd", 0.0) or 0.0)


def tokens_of(bundle: MatrixBundle, task_id: str, model: str | None) -> tuple[int, int]:
    c = cell(bundle, task_id, model)
    return int(c.get("in_tok", 0) or 0), int(c.get("out_tok", 0) or 0)


def reward(perf: float, cost: float) -> float:
    return EPS1 * perf + EPS2 * cost


def model_mean_costs(bundle: MatrixBundle) -> dict[str, float]:
    return {
        model: sum(cost_of(bundle, task_id, model) for task_id in bundle.ids) / len(bundle.ids)
        for model in bundle.models
    }


def oracle_reward(bundle: MatrixBundle) -> tuple[dict[str, float], dict[str, str], dict[str, float]]:
    mean_cost = model_mean_costs(bundle)
    best_reward: dict[str, float] = {}
    best_model: dict[str, str] = {}
    best_perf: dict[str, float] = {}
    for task_id in bundle.ids:
        ranked = []
        for model in bundle.models:
            perf = perf_of(bundle, task_id, model)
            cost = cost_of(bundle, task_id, model)
            ranked.append((reward(perf, cost), perf, -cost, -mean_cost[model], model))
        ranked.sort(reverse=True)
        best_reward[task_id] = ranked[0][0]
        best_perf[task_id] = ranked[0][1]
        best_model[task_id] = ranked[0][4]
    return best_reward, best_model, best_perf


def perf_oracle_model(bundle: MatrixBundle, task_id: str) -> str:
    mean_cost = model_mean_costs(bundle)
    ranked = []
    for model in bundle.models:
        ranked.append((perf_of(bundle, task_id, model), -cost_of(bundle, task_id, model), -mean_cost[model], model))
    ranked.sort(reverse=True)
    return ranked[0][3]


def score_decisions(
    bundle: MatrixBundle,
    name: str,
    decision_rows: list[dict],
    source: str,
    note: str = "",
    aggregate: dict | None = None,
) -> dict:
    best_reward, best_reward_model, best_perf = oracle_reward(bundle)
    rows_by_task = {row["task_id"]: row for row in decision_rows}
    n = len(bundle.ids)
    total_perf = 0.0
    total_apply = 0.0
    total_cost = 0.0
    total_in = 0
    total_out = 0
    cum_regret = 0.0
    reward_acc = 0
    missing = 0
    by_source = defaultdict(lambda: {"n": 0, "resolved": 0.0, "cost_usd": 0.0})
    by_bench = defaultdict(lambda: {"n": 0, "resolved": 0.0, "cost_usd": 0.0})
    model_counts: Counter[str] = Counter()

    for task_id in bundle.ids:
        row = rows_by_task.get(task_id)
        meta = bundle.metadata.get(task_id, {})
        source_split = meta.get("source_split", "unknown")
        bench = meta.get("bench", source_split)
        by_source[source_split]["n"] += 1
        by_bench[bench]["n"] += 1
        if row is None:
            missing += 1
            perf = 0.0
            apply_ok = 0.0
            cost = 0.0
            in_tok = 0
            out_tok = 0
            model = None
        else:
            model = normalize_model(row.get("chosen_model"))
            perf = float(row["resolved"]) if "resolved" in row else perf_of(bundle, task_id, model)
            apply_ok = float(row["apply_ok"]) if "apply_ok" in row else apply_ok_of(bundle, task_id, model)
            cost = float(row["cost_usd"]) if "cost_usd" in row else cost_of(bundle, task_id, model)
            if "in_tok" in row or "out_tok" in row:
                in_tok = int(row.get("in_tok", 0) or 0)
                out_tok = int(row.get("out_tok", 0) or 0)
            elif "chain_run" in row:
                in_tok, out_tok = chain_tokens(bundle, task_id, row.get("chain_run", []))
            else:
                in_tok, out_tok = tokens_of(bundle, task_id, model)
        total_perf += perf
        total_apply += apply_ok
        total_cost += cost
        total_in += in_tok
        total_out += out_tok
        cum_regret += best_reward[task_id] - reward(perf, cost)
        if model is not None:
            model_counts[model] += 1
            if model == best_reward_model[task_id]:
                reward_acc += 1
        by_source[source_split]["resolved"] += perf
        by_source[source_split]["cost_usd"] += cost
        by_bench[bench]["resolved"] += perf
        by_bench[bench]["cost_usd"] += cost

    avg_perf = total_perf / n * 100.0
    result = {
        "method": name,
        "n": n,
        "decision_count": len(decision_rows),
        "missing_decisions": missing,
        "AvgPerf%": round(avg_perf, 2),
        "CumReg": round(cum_regret, 1),
        "$Total": round(total_cost, 2),
        "$Backend": round(total_cost, 2),
        "$Router": 0.0,
        "Perf/$": round(avg_perf / total_cost, 2) if total_cost > 0 else math.inf,
        "Apply_ok%": round(total_apply / n * 100.0, 2),
        "TotInTok": int(total_in),
        "TotOutTok": int(total_out),
        "rAcc_reward_oracle": round(reward_acc / n, 4),
        "OracleAvgPerf%": round(sum(best_perf.values()) / n * 100.0, 2),
        "decision_source": source,
        "note": note,
        "model_distribution": dict(sorted(model_counts.items())),
        "by_source_split": summarize_groups(by_source),
        "by_bench": summarize_groups(by_bench),
    }
    if aggregate:
        result.update(aggregate)
    return result


def summarize_groups(groups: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for name, data in sorted(groups.items()):
        n = data["n"]
        out[name] = {
            "n": n,
            "AvgPerf%": round(data["resolved"] / n * 100.0, 2) if n else 0.0,
            "$Total": round(data["cost_usd"], 2),
        }
    return out


def chain_tokens(bundle: MatrixBundle, task_id: str, chain: Iterable[str]) -> tuple[int, int]:
    total_in = 0
    total_out = 0
    for model in chain:
        in_tok, out_tok = tokens_of(bundle, task_id, normalize_model(model))
        total_in += in_tok
        total_out += out_tok
    return total_in, total_out


def write_decisions(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def direct_model_decisions(bundle: MatrixBundle, model: str, source: str) -> list[dict]:
    model = normalize_model(model) or model
    return [
        {
            "task_id": task_id,
            "chosen_model": model,
            "decision_source": source,
        }
        for task_id in bundle.ids
    ]


def oracle_decisions(bundle: MatrixBundle) -> list[dict]:
    _, reward_model, _ = oracle_reward(bundle)
    return [
        {
            "task_id": task_id,
            "chosen_model": reward_model[task_id],
            "decision_source": "reward_oracle",
        }
        for task_id in bundle.ids
    ]


def random_decisions(bundle: MatrixBundle, seed: int) -> list[dict]:
    rng = random.Random(seed)
    return [
        {
            "task_id": task_id,
            "chosen_model": rng.choice(bundle.models),
            "decision_source": f"random_seed_{seed}",
            "seed": seed,
        }
        for task_id in bundle.ids
    ]


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def acrouter_decisions(bundle: MatrixBundle) -> tuple[list[dict], str]:
    rows = load_jsonl(ACROUTER_DECISIONS)
    for row in rows:
        row["decision_source"] = "acrouter_unique_release_ood176"
        row["in_tok"], row["out_tok"] = chain_tokens(bundle, row["task_id"], row.get("chain_run", []))
    note = "ACRouter release OOD176 decisions from run_acrouter_ood176.py."
    if ACROUTER_METRICS.exists():
        m = read_json(ACROUTER_METRICS)
        note += f" Source metrics file reports AvgPerf={m.get('AvgPerf%')} CumReg={m.get('CumReg')} $Total={m.get('$Total')}."
    return rows, note


def old_original_id(combined_id: str) -> str:
    return combined_id.split("old112::", 1)[1]


def load_published_decision_map(path: Path) -> dict[str, str]:
    data = read_json(path)
    out: dict[str, str] = {}
    for row in data.get("decisions", []):
        task_id = row.get("task_id")
        model = normalize_model(row.get("chosen_model") or row.get("final_model") or row.get("model"))
        if task_id and model:
            out[task_id] = model
    if not out:
        raise RuntimeError(f"no decisions found in {path}")
    return out


def modal_model(models: Iterable[str], mean_cost: dict[str, float]) -> str:
    counts = Counter(models)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], mean_cost.get(kv[0], 0.0), kv[0]))
    return ranked[0][0]


def load_saved_router(router_name: str):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if router_name == "logreg":
        from src.routing.trained_routers import LogRegRouter

        return LogRegRouter().load(TRAINED_MODELS_DIR / "logreg_router.pkl")
    if router_name == "tfidf_mlp":
        from src.routing.trained_routers import BERTMLPRouter

        return BERTMLPRouter().load(TRAINED_MODELS_DIR / "bert_mlp_router.pkl")
    if router_name == "routellm_mf":
        from src.routing.routellm_baselines import MFRouter

        router = MFRouter()
        router.load(str(TRAINED_MODELS_DIR))
        return router
    if router_name == "routellm_sw":
        from src.routing.routellm_baselines import SWRankingRouter

        router = SWRankingRouter()
        router.load(str(TRAINED_MODELS_DIR))
        return router
    raise ValueError(f"unknown saved router {router_name!r}")


async def route_new64_async(bundle: MatrixBundle, router_name: str) -> dict[str, str]:
    router = load_saved_router(router_name)
    out = {}
    for task_id in bundle.ids:
        if not task_id.startswith("new64::"):
            continue
        meta = bundle.metadata.get(task_id, {})
        decision = await router.route(
            {
                "task_id": task_id,
                "prompt": meta.get("prompt", ""),
                "dimension": meta.get("dimension", "unknown"),
                "difficulty": "medium",
                "language": "python",
                "metadata": meta,
            }
        )
        out[task_id] = normalize_model(decision.chosen_model) or decision.chosen_model
    return out


def route_new64_with_saved_router(bundle: MatrixBundle, router_name: str) -> tuple[dict[str, str], str | None]:
    try:
        return asyncio.run(route_new64_async(bundle, router_name)), None
    except Exception as exc:
        return {}, repr(exc)


def published_replay_decisions(
    bundle: MatrixBundle,
    metrics_file: str,
    new64_router: str | None = None,
) -> tuple[list[dict], dict]:
    source_path = SWE112_RESULTS / metrics_file
    old_map = load_published_decision_map(source_path)
    mean_cost = model_mean_costs(bundle)
    extension_model = modal_model(old_map.values(), mean_cost)
    new64_predictions: dict[str, str] = {}
    router_error = None
    if new64_router:
        new64_predictions, router_error = route_new64_with_saved_router(bundle, new64_router)
    rows = []
    old_replayed = 0
    new_extended = 0
    new_predicted = 0
    for task_id in bundle.ids:
        if task_id.startswith("old112::"):
            original = old_original_id(task_id)
            model = old_map.get(original, extension_model)
            decision_source = f"old112_published_replay:{metrics_file}"
            old_replayed += 1
        else:
            model = new64_predictions.get(task_id)
            if model:
                decision_source = f"new64_saved_router_prediction:{new64_router}"
                new_predicted += 1
            else:
                model = extension_model
                decision_source = f"new64_modal_extension:{metrics_file}"
                new_extended += 1
        rows.append(
            {
                "task_id": task_id,
                "chosen_model": model,
                "decision_source": decision_source,
            }
        )
    aggregate = {
        "published_source_file": str(source_path.relative_to(REPO_ROOT)),
        "published_source_method": read_json(source_path).get("method"),
        "new64_extension_model": extension_model,
        "new64_saved_router": new64_router,
        "new64_router_error": router_error,
        "old112_replayed": old_replayed,
        "new64_extended": new_extended,
        "new64_predicted": new_predicted,
    }
    return rows, aggregate


def feature_vectors(bundle: MatrixBundle) -> dict[str, np.ndarray]:
    source_values = sorted({bundle.metadata.get(tid, {}).get("source_split", "unknown") for tid in bundle.ids})
    bench_values = sorted({bundle.metadata.get(tid, {}).get("bench", "unknown") for tid in bundle.ids})
    dim_values = sorted({bundle.metadata.get(tid, {}).get("dimension", "unknown") for tid in bundle.ids})
    cat_names = (
        [f"source={v}" for v in source_values]
        + [f"bench={v}" for v in bench_values]
        + [f"dimension={v}" for v in dim_values]
    )
    cat_index = {name: i + 1 for i, name in enumerate(cat_names)}
    dim = 1 + len(cat_names) + 1 + HASH_BUCKETS
    vectors = {}
    for task_id in bundle.ids:
        meta = bundle.metadata.get(task_id, {})
        x = np.zeros(dim, dtype=float)
        x[0] = 1.0
        for prefix, value in [
            ("source", meta.get("source_split", "unknown")),
            ("bench", meta.get("bench", "unknown")),
            ("dimension", meta.get("dimension", "unknown")),
        ]:
            idx = cat_index.get(f"{prefix}={value}")
            if idx is not None:
                x[idx] = 1.0
        prompt = meta.get("prompt", "")
        x[1 + len(cat_names)] = min(len(prompt), 10000) / 10000.0
        text = " ".join(
            [
                task_id,
                str(meta.get("original_task_id", "")),
                str(meta.get("bench", "")),
                str(meta.get("dimension", "")),
            ]
        ).lower()
        for token in re.findall(r"[a-z0-9_]+", text):
            bucket = stable_bucket(token, HASH_BUCKETS)
            x[1 + len(cat_names) + 1 + bucket] += 1.0
        hashed = x[1 + len(cat_names) + 1 :]
        norm = np.linalg.norm(hashed)
        if norm > 0:
            x[1 + len(cat_names) + 1 :] = hashed / norm
        vectors[task_id] = x
    return vectors


def stable_bucket(token: str, buckets: int) -> int:
    # Python's hash is salted; keep this deterministic across processes.
    h = 0
    for ch in token:
        h = (h * 131 + ord(ch)) % 1_000_000_007
    return h % buckets


def cheaper_tiebreak_key(bundle: MatrixBundle) -> dict[str, tuple[float, str]]:
    costs = model_mean_costs(bundle)
    return {model: (costs[model], model) for model in bundle.models}


def run_linucb(bundle: MatrixBundle, alpha: float = 1.0, ridge: float = 1.0) -> list[dict]:
    features = feature_vectors(bundle)
    dim = next(iter(features.values())).shape[0]
    a = {model: np.eye(dim) * ridge for model in bundle.models}
    b = {model: np.zeros(dim) for model in bundle.models}
    tie_key = cheaper_tiebreak_key(bundle)
    rows = []
    for step, task_id in enumerate(bundle.ids, start=1):
        x = features[task_id]
        ranked = []
        for model in bundle.models:
            inv = np.linalg.inv(a[model])
            theta = inv @ b[model]
            uncertainty = math.sqrt(max(float(x @ inv @ x), 0.0))
            score = float(theta @ x) + alpha * uncertainty
            ranked.append((score, -tie_key[model][0], model))
        ranked.sort(reverse=True)
        model = ranked[0][2]
        perf = perf_of(bundle, task_id, model)
        cost = cost_of(bundle, task_id, model)
        obs_reward = reward(perf, cost)
        a[model] += np.outer(x, x)
        b[model] += obs_reward * x
        rows.append(
            {
                "task_id": task_id,
                "chosen_model": model,
                "decision_source": "online_linucb_cost_aware",
                "step": step,
                "observed_reward": obs_reward,
                "alpha": alpha,
                "ridge": ridge,
            }
        )
    return rows


def run_lints(bundle: MatrixBundle, seed: int = 42, v: float = 0.35, ridge: float = 1.0) -> list[dict]:
    features = feature_vectors(bundle)
    dim = next(iter(features.values())).shape[0]
    a = {model: np.eye(dim) * ridge for model in bundle.models}
    b = {model: np.zeros(dim) for model in bundle.models}
    tie_key = cheaper_tiebreak_key(bundle)
    rng = np.random.default_rng(seed)
    rows = []
    for step, task_id in enumerate(bundle.ids, start=1):
        x = features[task_id]
        ranked = []
        for model in bundle.models:
            inv = np.linalg.inv(a[model])
            mean = inv @ b[model]
            cov = (v**2) * inv
            theta = rng.multivariate_normal(mean, cov, check_valid="ignore")
            score = float(theta @ x)
            ranked.append((score, -tie_key[model][0], model))
        ranked.sort(reverse=True)
        model = ranked[0][2]
        perf = perf_of(bundle, task_id, model)
        cost = cost_of(bundle, task_id, model)
        obs_reward = reward(perf, cost)
        a[model] += np.outer(x, x)
        b[model] += obs_reward * x
        rows.append(
            {
                "task_id": task_id,
                "chosen_model": model,
                "decision_source": "online_lints_cost_aware",
                "step": step,
                "observed_reward": obs_reward,
                "seed": seed,
                "v": v,
                "ridge": ridge,
            }
        )
    return rows


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(a @ b / denom)


def run_knn(bundle: MatrixBundle, k: int = 8) -> list[dict]:
    features = feature_vectors(bundle)
    mean_cost = model_mean_costs(bundle)
    cheapest = min(bundle.models, key=lambda m: (mean_cost[m], m))
    rows = []
    history: list[tuple[str, np.ndarray, str, float]] = []
    for step, task_id in enumerate(bundle.ids, start=1):
        x = features[task_id]
        if step <= len(bundle.models):
            model = bundle.models[(step - 1) % len(bundle.models)]
            reason = "round_robin_warmup"
        else:
            neighbors = sorted(history, key=lambda h: cosine(x, h[1]), reverse=True)[:k]
            rewards_by_model = defaultdict(list)
            for _, _, model_name, obs_reward in neighbors:
                rewards_by_model[model_name].append(obs_reward)
            if rewards_by_model:
                ranked = []
                for model_name, vals in rewards_by_model.items():
                    ranked.append((sum(vals) / len(vals), -mean_cost[model_name], model_name))
                ranked.sort(reverse=True)
                model = ranked[0][2]
                reason = "nearest_observed_reward"
            else:
                model = cheapest
                reason = "cheapest_fallback"
        perf = perf_of(bundle, task_id, model)
        cost = cost_of(bundle, task_id, model)
        obs_reward = reward(perf, cost)
        history.append((task_id, x, model, obs_reward))
        rows.append(
            {
                "task_id": task_id,
                "chosen_model": model,
                "decision_source": "online_knn_retrieval",
                "step": step,
                "k": k,
                "reason": reason,
                "observed_reward": obs_reward,
            }
        )
    return rows


def score_random_mean(bundle: MatrixBundle, decisions_dir: Path, seeds: list[int]) -> tuple[dict, list[dict]]:
    seed_metrics = []
    for seed in seeds:
        rows = random_decisions(bundle, seed)
        write_decisions(decisions_dir / f"Random_seed{seed}.jsonl", rows)
        seed_metrics.append(score_decisions(bundle, f"Random_seed{seed}", rows, f"random_seed_{seed}"))
    keys = ["AvgPerf%", "CumReg", "$Total", "$Backend", "Perf/$", "Apply_ok%", "TotInTok", "TotOutTok", "rAcc_reward_oracle"]
    mean_metric = {}
    for key in keys:
        vals = [m[key] for m in seed_metrics]
        mean_metric[key] = round(sum(vals) / len(vals), 2 if key not in {"TotInTok", "TotOutTok", "rAcc_reward_oracle"} else 4)
    row = dict(seed_metrics[0])
    row.update(mean_metric)
    row["method"] = "Random"
    row["decision_source"] = "random_10_seed_mean"
    row["note"] = f"Mean over seeds {seeds[0]}-{seeds[-1]}; per-seed decisions are in decisions/."
    row["seed_count"] = len(seeds)
    row["seed_metrics"] = seed_metrics
    return row, seed_metrics


def build_results(bundle: MatrixBundle, output_dir: Path) -> tuple[list[dict], dict[str, list[dict]], list[dict]]:
    decisions_dir = output_dir / "decisions"
    output_dir.mkdir(parents=True, exist_ok=True)
    decisions_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    decisions_by_method: dict[str, list[dict]] = {}
    extra_seed_metrics: list[dict] = []

    def add(name: str, rows: list[dict], source: str, note: str = "", aggregate: dict | None = None) -> None:
        decisions_by_method[name] = rows
        write_decisions(decisions_dir / f"{slugify(name)}.jsonl", rows)
        results.append(score_decisions(bundle, name, rows, source, note=note, aggregate=aggregate))

    add("Oracle", oracle_decisions(bundle), "reward_oracle", "Cost-aware reward oracle with epsilon=(1,-0.1).")

    ac_rows, ac_note = acrouter_decisions(bundle)
    add("ACRouter (ours)", ac_rows, "acrouter_unique_release_ood176", note=ac_note)

    add("LinTS", run_lints(bundle), "online_lints_cost_aware", note="Offline online replay over the OOD176 task order.")
    add("LinUCB", run_linucb(bundle), "online_linucb_cost_aware", note="Offline online replay over the OOD176 task order.")
    add("kNN Retrieval", run_knn(bundle), "online_knn_retrieval", note="Online kNN replay using task metadata/hash features and observed chosen-model rewards.")

    for name, cfg in PUBLISHED_REPLAY_BASELINES.items():
        rows, aggregate = published_replay_decisions(bundle, cfg["file"], cfg.get("new64_router"))
        add(
            name,
            rows,
            f"old112_published_replay_plus_new64_router_or_modal:{cfg['file']}",
            note=cfg["note"],
            aggregate=aggregate,
        )

    single_models = {
        "Always-Opus 4.6": "claude-opus-4-6",
        "Always-Kimi-K2.5": "kimi-k2.5",
        "Always-Qwen3.5-Plus": "qwen3.5-plus",
    }
    for name, model in single_models.items():
        add(name, direct_model_decisions(bundle, model, f"always:{model}"), f"always:{model}")

    random_row, seed_metrics = score_random_mean(bundle, decisions_dir, list(range(42, 52)))
    results.append(random_row)
    extra_seed_metrics.extend(seed_metrics)
    return results, decisions_by_method, extra_seed_metrics


def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")


def with_table_rows(metrics: list[dict]) -> list[dict]:
    by_method = {row["method"]: row for row in metrics}
    out = []
    for group, router, id_avg, id_regret, id_perf_dollar in TABLE_ROWS:
        base = {
            "group": group,
            "Router": router,
            "ID_AvgPerf%": id_avg,
            "ID_CumReg": id_regret,
            "ID_Perf/$": id_perf_dollar,
        }
        if router == "DimensionBest":
            base.update(
                {
                    "OOD_n": None,
                    "OOD_AvgPerf%": None,
                    "OOD_CumReg": None,
                    "OOD_Perf/$": None,
                    "decision_source": "not_applicable_to_ood",
                    "note": "DimensionBest remains not applicable to OOD because unseen agentic tasks lack a predefined dimension-to-model map.",
                }
            )
        else:
            m = by_method[router]
            base.update(
                {
                    "OOD_n": m["n"],
                    "OOD_AvgPerf%": m["AvgPerf%"],
                    "OOD_CumReg": m["CumReg"],
                    "OOD_Perf/$": m["Perf/$"],
                    "OOD_$Total": m["$Total"],
                    "OOD_Apply_ok%": m["Apply_ok%"],
                    "decision_source": m["decision_source"],
                    "note": m.get("note", ""),
                }
            )
        out.append(base)
    return out


def fmt(value: object, digits: int = 2) -> str:
    if value is None:
        return "---"
    if isinstance(value, float):
        if math.isinf(value):
            return "inf"
        return f"{value:.{digits}f}"
    return str(value)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict], generated_utc: str) -> None:
    lines = [
        "# OOD176 Baseline Table",
        "",
        f"Generated: {generated_utc}",
        "",
        "Left-side in-distribution metrics are copied unchanged from the provided table. Right-side OOD metrics are recomputed on the unified OOD176 matrix.",
        "",
        "| Group | Router | ID AvgPerf% | ID CumReg | ID Perf/$ | OOD n | OOD AvgPerf% | OOD CumReg | OOD Perf/$ | Source |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {group} | {router} | {id_avg} | {id_regret} | {id_pd} | {ood_n} | {ood_avg} | {ood_regret} | {ood_pd} | {src} |".format(
                group=row["group"],
                router=row["Router"],
                id_avg=fmt(row["ID_AvgPerf%"]),
                id_regret=fmt(row["ID_CumReg"], 1),
                id_pd=fmt(row["ID_Perf/$"]),
                ood_n=fmt(row["OOD_n"], 0),
                ood_avg=fmt(row["OOD_AvgPerf%"]),
                ood_regret=fmt(row["OOD_CumReg"], 1),
                ood_pd=fmt(row["OOD_Perf/$"]),
                src=row["decision_source"],
            )
        )
    lines.extend(["", "## Notes", ""])
    for row in rows:
        note = row.get("note")
        if note:
            lines.append(f"- {row['Router']}: {note}")
    path.write_text("\n".join(lines) + "\n")


def write_latex(path: Path, rows: list[dict]) -> None:
    lines = [
        r"\begin{tabular}{@{}l l ccc ccc@{}}",
        r"\toprule",
        r"& & \multicolumn{3}{c}{\textbf{In-Distribution ($n{=}2{,}919$)}} & \multicolumn{3}{c}{\textbf{OOD Test (n=176)}} \\",
        r"\cmidrule(lr){3-5} \cmidrule(lr){6-8}",
        r"& \textbf{Router} & \textbf{AvgPerf\%}$\uparrow$ & \textbf{CumReg}$\downarrow$ & \textbf{Perf/\$}$\uparrow$ & \textbf{AvgPerf\%}$\uparrow$ & \textbf{CumReg}$\downarrow$ & \textbf{Perf/\$}$\uparrow$ \\",
        r"\midrule",
    ]
    last_group = None
    for row in rows:
        group = row["group"]
        if group != last_group:
            if group == "Bound":
                pass
            else:
                lines.append(r"\midrule")
                lines.append(rf"\multicolumn{{8}}{{l}}{{\textbf{{{group}}}}} \\")
                lines.append(r"\cmidrule(l){1-8}")
            last_group = group
        lines.append(
            r"& {router} & {id_avg} & {id_regret} & {id_pd} & {ood_avg} & {ood_regret} & {ood_pd} \\".format(
                router=latex_escape(row["Router"]),
                id_avg=fmt(row["ID_AvgPerf%"]),
                id_regret=fmt(row["ID_CumReg"], 1).rstrip("0").rstrip("."),
                id_pd=fmt(row["ID_Perf/$"]),
                ood_avg=fmt(row["OOD_AvgPerf%"]),
                ood_regret=fmt(row["OOD_CumReg"], 1).rstrip("0").rstrip("."),
                ood_pd=fmt(row["OOD_Perf/$"]),
            )
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines))


def latex_escape(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
    )


def write_outputs(
    output_dir: Path,
    bundle: MatrixBundle,
    matrix_path: Path,
    metrics: list[dict],
    table_rows: list[dict],
    seed_metrics: list[dict],
    generated_utc: str,
) -> None:
    payload = {
        "generated_utc": generated_utc,
        "matrix_path": format_path(matrix_path, REPO_ROOT),
        "n": len(bundle.ids),
        "models": bundle.models,
        "eps": {"perf": EPS1, "cost": EPS2},
        "metrics": metrics,
        "random_seed_metrics": seed_metrics,
        "table_rows": table_rows,
    }
    (output_dir / "baseline_metrics.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_csv(output_dir / "baseline_table.csv", table_rows)
    write_markdown(output_dir / "baseline_table.md", table_rows, generated_utc)
    write_latex(output_dir / "baseline_table.tex", table_rows)

    metric_rows = []
    for row in metrics:
        metric_rows.append(
            {
                "method": row["method"],
                "n": row["n"],
                "AvgPerf%": row["AvgPerf%"],
                "CumReg": row["CumReg"],
                "$Total": row["$Total"],
                "Perf/$": row["Perf/$"],
                "Apply_ok%": row["Apply_ok%"],
                "rAcc_reward_oracle": row["rAcc_reward_oracle"],
                "decision_source": row["decision_source"],
                "missing_decisions": row["missing_decisions"],
            }
        )
    write_csv(output_dir / "baseline_metrics.csv", metric_rows)


def verify_outputs(bundle: MatrixBundle, metrics: list[dict], table_rows: list[dict]) -> None:
    expected_methods = [row[1] for row in TABLE_ROWS if row[1] != "DimensionBest"]
    seen = {row["method"] for row in metrics}
    missing = sorted(set(expected_methods) - seen)
    if missing:
        raise RuntimeError(f"missing metric rows: {missing}")
    for row in metrics:
        if row["n"] != len(bundle.ids):
            raise RuntimeError(f"{row['method']} n={row['n']} expected {len(bundle.ids)}")
        if row["missing_decisions"] != 0:
            raise RuntimeError(f"{row['method']} has {row['missing_decisions']} missing decisions")
    for row in table_rows:
        if row["Router"] == "DimensionBest":
            if row["OOD_n"] is not None:
                raise RuntimeError("DimensionBest should remain OOD N/A")
        elif row["OOD_n"] != len(bundle.ids):
            raise RuntimeError(f"{row['Router']} table n={row['OOD_n']} expected {len(bundle.ids)}")


def print_summary(metrics: list[dict], table_rows: list[dict]) -> None:
    by_method = {row["method"]: row for row in metrics}
    print("OOD176 baseline rerun")
    for _, router, *_ in TABLE_ROWS:
        if router == "DimensionBest":
            print(f"{router:28s} AvgPerf=---   CumReg=---    Perf/$=---   n=---")
        else:
            row = by_method[router]
            print(
                f"{router:28s} AvgPerf={row['AvgPerf%']:6.2f}  "
                f"CumReg={row['CumReg']:6.1f}  Perf/$={fmt(row['Perf/$']):>6s}  n={row['n']}"
            )
    print(f"table_rows={len(table_rows)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix",
        type=Path,
        default=None,
        help="Explicit OOD176 matrix path. Overrides --hf-dataset-dir.",
    )
    parser.add_argument(
        "--hf-dataset-dir",
        type=Path,
        default=None,
        help=(
            "Path to a Hugging Face CodeRouterBench snapshot, for example "
            ".hf/CodeRouterBench after `hf download Lance1573/CodeRouterBench "
            "--repo-type dataset --local-dir .hf/CodeRouterBench`."
        ),
    )
    parser.add_argument(
        "--download-hf",
        action="store_true",
        help="Download the CodeRouterBench dataset snapshot before resolving paths.",
    )
    parser.add_argument(
        "--minimal-hf",
        action="store_true",
        help="With --download-hf, download only files needed for OOD176 replay.",
    )
    parser.add_argument("--hf-dataset-repo-id", default="Lance1573/CodeRouterBench")
    parser.add_argument("--hf-revision", default=None)
    parser.add_argument(
        "--hf-max-workers",
        type=int,
        default=1,
        help="Parallel HF download workers used with --download-hf.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    hf_dataset_dir = args.hf_dataset_dir
    if args.download_hf:
        hf_dataset_dir = hf_dataset_dir or DEFAULT_HF_DATASET_DIR
        layout = download_coderouterbench(
            local_dir=hf_dataset_dir,
            repo_id=args.hf_dataset_repo_id,
            revision=args.hf_revision,
            allow_patterns=MINIMAL_DATASET_PATTERNS if args.minimal_hf else None,
            max_workers=args.hf_max_workers,
        )
        hf_dataset_dir = layout.root

    matrix_path = resolve_ood_matrix(
        repo_root=REPO_ROOT,
        matrix=args.matrix,
        hf_dataset_dir=hf_dataset_dir,
    )

    bundle = load_matrix(matrix_path)
    if len(bundle.ids) != 176:
        raise RuntimeError(f"expected OOD176 matrix, got {len(bundle.ids)}")
    for task_id in bundle.ids:
        missing = set(bundle.models) - set(bundle.matrix.get(task_id, {}))
        if missing:
            raise RuntimeError(f"{task_id} missing model cells: {sorted(missing)}")

    generated = now_utc()
    metrics, _, seed_metrics = build_results(bundle, args.output_dir)
    table_rows = with_table_rows(metrics)
    verify_outputs(bundle, metrics, table_rows)
    write_outputs(args.output_dir, bundle, matrix_path, metrics, table_rows, seed_metrics, generated)
    print_summary(metrics, table_rows)
    print(f"matrix={format_path(matrix_path, REPO_ROOT)}")
    print(f"wrote {args.output_dir}")


if __name__ == "__main__":
    main()
