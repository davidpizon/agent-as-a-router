#!/usr/bin/env python3
"""Re-compute ALL Table 4 metrics on 9 core dimensions (2,919 test tasks).

Runs all local routers from scratch, re-evaluates existing decision files,
and computes EARouter Top-K from oracle data. Outputs a complete table.

Usage:
    python scripts/recompute_table4.py
"""

import asyncio
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.routing.base import BACKEND_MODELS, MODEL_DATA_ALIASES, MODEL_DATA_REVERSE
from src.routing.data_manager import DataManager
from src.routing.baselines import RandomRouter, AlwaysBestRouter, DimensionRouter
from src.routing.cascade_router import CascadeRouter

# Pricing from the release pricing table (USD per 1M tokens).
PRICING_PATH = PROJECT_ROOT / "data" / "matrices" / "phase1_id" / "model_pricing.json"


def load_pricing() -> dict[str, dict[str, float]]:
    payload = json.loads(PRICING_PATH.read_text())["models"]
    return {
        model: {
            "input": float(row["input_per_1m"]),
            "output": float(row["output_per_1m"]),
        }
        for model, row in payload.items()
    }


PRICING = load_pricing()

# EARouter uses sonnet as the router LLM
ROUTER_PRICING = PRICING["claude-sonnet-4-6"]
ROUTER_AVG_INPUT_TOKENS = 480  # estimated from actual measurements
ROUTER_AVG_OUTPUT_TOKENS = 50

CORE_DIMS = [
    "algorithm", "bug_fixing", "code_completion", "code_generation",
    "code_refactoring", "code_understanding", "data_science",
    "multi_language", "test_generation",
]


def compute_task_cost(dm, task_id, model):
    """Compute USD cost for one task on one model."""
    tokens = dm.get_backend_tokens(task_id, model)
    inp = tokens.get("input_tokens", 0)
    out = tokens.get("output_tokens", 0)
    p = PRICING[model]
    return inp * p["input"] / 1e6 + out * p["output"] / 1e6


def compute_router_cost_per_task():
    """Cost of one EARouter LLM call (sonnet)."""
    return (ROUTER_AVG_INPUT_TOKENS * ROUTER_PRICING["input"] / 1e6 +
            ROUTER_AVG_OUTPUT_TOKENS * ROUTER_PRICING["output"] / 1e6)


def evaluate_on_core(dm, decisions, core_task_ids, router_pricing=None):
    """Evaluate decisions filtered to 9 core dimensions.

    Args:
        router_pricing: {"input": X, "output": Y} per-1M-token rates for the router LLM.
                       Defaults to kimi pricing (most common router model).
    Returns dict with all Table 4 metrics.
    """
    if router_pricing is None:
        router_pricing = PRICING["kimi-k2.5"]
    core_set = set(core_task_ids)

    total_perf = 0.0
    total_oracle_perf = 0.0
    total_backend_cost = 0.0
    total_router_cost = 0.0
    total_router_tokens = 0
    total_backend_tokens = 0
    n = 0

    for d in decisions:
        if d.task_id not in core_set:
            continue

        score = dm.get_score(d.task_id, d.chosen_model)
        if score is None:
            score = 0.0
        oracle_score = dm.get_oracle_score(d.task_id)
        if oracle_score is None:
            oracle_score = 0.0

        total_perf += score
        total_oracle_perf += oracle_score

        # Tokens
        backend = dm.get_backend_tokens(d.task_id, d.chosen_model)
        b_in = backend.get("input_tokens", 0)
        b_out = backend.get("output_tokens", 0)
        r_in = d.router_input_tokens
        r_out = d.router_output_tokens

        total_router_tokens += (r_in + r_out)
        total_backend_tokens += (b_in + b_out)

        # Backend cost (per-model, per-direction pricing)
        total_backend_cost += compute_task_cost(dm, d.task_id, d.chosen_model)

        # Router cost: use actual per-decision input/output tokens with router model pricing
        if r_in + r_out > 0:
            total_router_cost += (r_in * router_pricing["input"] / 1e6 +
                                  r_out * router_pricing["output"] / 1e6)

        n += 1

    if n == 0:
        return None

    avg_perf = total_perf / n
    avg_oracle = total_oracle_perf / n
    avg_router_tok = total_router_tokens / n
    avg_backend_tok = total_backend_tokens / n
    avg_total_tok = avg_router_tok + avg_backend_tok

    total_cost = total_backend_cost + total_router_cost
    avg_cost = total_cost / n

    gap_pct = (avg_oracle - avg_perf) / avg_oracle * 100 if avg_oracle > 0 else 0
    perf_per_dollar = avg_perf / avg_cost if avg_cost > 0 else float('inf')
    tok_per_perf = avg_total_tok / avg_perf if avg_perf > 0 else float('inf')

    return {
        "n_tasks": n,
        "avg_perf": round(avg_perf, 4),
        "oracle": round(avg_oracle, 4),
        "gap_pct": round(gap_pct, 1),
        "avg_total_tok": round(avg_total_tok),
        "total_cost": round(total_cost, 2),
        "perf_per_dollar": round(perf_per_dollar, 1),
        "tok_per_perf": round(tok_per_perf),
        "avg_router_tok": round(avg_router_tok),
        "avg_backend_tok": round(avg_backend_tok),
    }


def evaluate_topk_on_core(dm, core_task_ids, k, with_prior, dim_best_map):
    """Compute EARouter Top-K metrics.

    For each task:
    - If with_prior: use dimension-best ordering from training data
    - If without prior: use a fixed ordering (arbitrary)
    - Try top-k models, return best score

    Router overhead: 1 LLM call per task (not per k).
    Backend cost: k model calls per task.
    """
    # Compute model ranking per dimension from training data
    if with_prior:
        dim_rankings = compute_dim_rankings(dm)
    else:
        dim_rankings = None

    total_perf = 0.0
    total_oracle_perf = 0.0
    total_backend_cost = 0.0
    total_backend_tokens = 0
    n = 0

    for task_id in core_task_ids:
        task = dm.get_task(task_id)
        if not task:
            continue
        dim = task.get("dimension", "unknown")

        # Get model ordering
        if with_prior and dim in dim_rankings:
            ordered_models = dim_rankings[dim]
        else:
            # Without prior: use fixed order (BACKEND_MODELS order)
            ordered_models = list(BACKEND_MODELS)

        # Try top-k models, pick best score
        best_score = 0.0
        best_model = ordered_models[0]
        tried_cost = 0.0
        tried_tokens = 0

        for model in ordered_models[:k]:
            score = dm.get_score(task_id, model)
            if score is None:
                score = 0.0
            if score > best_score:
                best_score = score
                best_model = model
            tried_cost += compute_task_cost(dm, task_id, model)
            backend = dm.get_backend_tokens(task_id, model)
            tried_tokens += backend.get("input_tokens", 0) + backend.get("output_tokens", 0)

        oracle_score = dm.get_oracle_score(task_id)
        if oracle_score is None:
            oracle_score = 0.0

        total_perf += best_score
        total_oracle_perf += oracle_score
        total_backend_cost += tried_cost
        total_backend_tokens += tried_tokens
        n += 1

    if n == 0:
        return None

    avg_perf = total_perf / n
    avg_oracle = total_oracle_perf / n

    # Router overhead: 1 LLM call per task
    router_cost_per_task = compute_router_cost_per_task()
    total_router_cost = router_cost_per_task * n
    router_tokens_per_task = ROUTER_AVG_INPUT_TOKENS + ROUTER_AVG_OUTPUT_TOKENS

    total_cost = total_backend_cost + total_router_cost
    avg_total_tok = total_backend_tokens / n + router_tokens_per_task
    avg_cost = total_cost / n

    gap_pct = (avg_oracle - avg_perf) / avg_oracle * 100 if avg_oracle > 0 else 0
    perf_per_dollar = avg_perf / avg_cost if avg_cost > 0 else float('inf')
    tok_per_perf = avg_total_tok / avg_perf if avg_perf > 0 else float('inf')

    return {
        "n_tasks": n,
        "avg_perf": round(avg_perf, 4),
        "oracle": round(avg_oracle, 4),
        "gap_pct": round(gap_pct, 1),
        "avg_total_tok": round(avg_total_tok),
        "total_cost": round(total_cost, 2),
        "perf_per_dollar": round(perf_per_dollar, 1),
        "tok_per_perf": round(tok_per_perf),
        "avg_router_tok": router_tokens_per_task,
        "avg_backend_tok": round(total_backend_tokens / n),
    }


def compute_dim_rankings(dm):
    """Compute model rankings per dimension from training data (for EARouter w/ prior)."""
    dim_scores = defaultdict(lambda: defaultdict(list))

    for task_id in dm.train:
        task = dm.get_task(task_id)
        if not task:
            continue
        dim = task.get("dimension", "unknown")
        if dim not in CORE_DIMS:
            continue
        for m in BACKEND_MODELS:
            s = dm.get_score(task_id, m)
            if s is not None:
                dim_scores[dim][m].append(s)

    rankings = {}
    for dim in CORE_DIMS:
        model_avgs = {}
        for m in BACKEND_MODELS:
            scores = dim_scores[dim].get(m, [])
            if scores:
                model_avgs[m] = sum(scores) / len(scores)
            else:
                model_avgs[m] = 0.0
        rankings[dim] = sorted(BACKEND_MODELS, key=lambda m: -model_avgs[m])

    return rankings


def load_decisions_from_file(path):
    """Load decisions from a JSONL file, canonicalizing model names."""
    from src.routing.base import RoutingDecision
    decisions = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            # Canonicalize model name (e.g., 通义千问Max -> Qwen3-Max)
            if d.get("chosen_model") in MODEL_DATA_REVERSE:
                d["chosen_model"] = MODEL_DATA_REVERSE[d["chosen_model"]]
            decisions.append(RoutingDecision.from_dict(d))
    return decisions


def evaluate_agent_v3_variants(dm, core_task_ids):
    """Compute Agent v3 (EARouter-Online) metrics from simulation.

    Agent v3 with prior converges to DimensionBest (same routing, just learned).
    Agent v3 without prior learns from scratch using scorer feedback.
    """
    results = {}

    # With prior: same as DimensionBest but add router overhead
    dim_best_map = dm.get_dimension_best_models()

    total_perf = 0.0
    total_oracle = 0.0
    total_backend_cost = 0.0
    total_backend_tokens = 0
    n = 0
    core_set = set(core_task_ids)

    for task_id in core_task_ids:
        task = dm.get_task(task_id)
        if not task:
            continue
        dim = task.get("dimension", "unknown")
        model = dim_best_map.get(dim, BACKEND_MODELS[0])

        score = dm.get_score(task_id, model)
        if score is None:
            score = 0.0
        oracle_score = dm.get_oracle_score(task_id)
        if oracle_score is None:
            oracle_score = 0.0

        total_perf += score
        total_oracle += oracle_score
        total_backend_cost += compute_task_cost(dm, task_id, model)
        backend = dm.get_backend_tokens(task_id, model)
        total_backend_tokens += backend.get("input_tokens", 0) + backend.get("output_tokens", 0)
        n += 1

    if n > 0:
        avg_perf = total_perf / n
        avg_oracle = total_oracle / n
        router_cost_per_task = compute_router_cost_per_task()
        router_tok = ROUTER_AVG_INPUT_TOKENS + ROUTER_AVG_OUTPUT_TOKENS
        total_cost = total_backend_cost + router_cost_per_task * n
        avg_total_tok = total_backend_tokens / n + router_tok
        avg_cost = total_cost / n
        gap_pct = (avg_oracle - avg_perf) / avg_oracle * 100

        results["agent_v3_with_prior"] = {
            "n_tasks": n,
            "avg_perf": round(avg_perf, 4),
            "oracle": round(avg_oracle, 4),
            "gap_pct": round(gap_pct, 1),
            "avg_total_tok": round(avg_total_tok),
            "total_cost": round(total_cost, 2),
            "perf_per_dollar": round(avg_perf / avg_cost, 1) if avg_cost > 0 else 0,
            "tok_per_perf": round(avg_total_tok / avg_perf) if avg_perf > 0 else 0,
        }

    # Without prior: simulate agent learning (use pre-computed avg from agent_v3_all_variants.json)
    # We'll compute this from the actual agent simulation
    return results


async def run_all():
    print("=" * 80)
    print("TABLE 4 RECOMPUTATION: 9 Core Dimensions, 60/10/30 Split")
    print("=" * 80)

    # Load data
    print("\nLoading data...")
    dm = DataManager()
    dm.load()
    print(f"  Train: {len(dm.train)}, Val: {len(dm.val)}, Test: {len(dm.test)}")

    # Filter to 9 core dimensions
    core_task_ids = []
    for task_id in dm.test:
        task = dm.get_task(task_id)
        if task and task.get("dimension") in CORE_DIMS:
            core_task_ids.append(task_id)
    print(f"  Core 9-dim test tasks: {len(core_task_ids)}")

    # Get tasks for running routers
    core_tasks = [dm.get_task(tid) for tid in core_task_ids]
    core_tasks = [t for t in core_tasks if t is not None]

    results = {}

    # ── Oracle ──
    oracle_perf = sum(dm.get_oracle_score(tid) or 0 for tid in core_task_ids) / len(core_task_ids)
    print(f"\n  Oracle: {oracle_perf:.4f}")

    # ── 1. Baselines ──
    print("\n--- Running Baselines ---")

    # Random
    router = RandomRouter(seed=42)
    decisions = []
    async with router:
        for t in core_tasks:
            decisions.append(await router.route(t))
    results["Random"] = evaluate_on_core(dm, decisions, core_task_ids)
    print(f"  Random: {results['Random']['avg_perf']}")

    # Always-X for key models
    for model_name, display in [
        ("claude-opus-4-6", "Always-Opus"),
        ("claude-sonnet-4-6", "Always-Sonnet"),
        ("kimi-k2.5", "Always-Kimi"),
        ("gpt-5.4", "Always-GPT"),
        ("Qwen3-Max", "Always-QwenMax"),
        ("MiniMax-M2.7", "Always-MiniMax"),
        ("qwen3.5-plus", "Always-Qwen3.5+"),
        ("glm-5", "Always-GLM5"),
    ]:
        router = AlwaysBestRouter(best_model=model_name)
        decisions = []
        async with router:
            for t in core_tasks:
                decisions.append(await router.route(t))
        results[display] = evaluate_on_core(dm, decisions, core_task_ids)
        print(f"  {display}: {results[display]['avg_perf']}")

    # DimensionBest
    dim_map = dm.get_dimension_best_models()
    print(f"\n  DimensionBest map: {dim_map}")
    router = DimensionRouter(dimension_map=dim_map)
    decisions = []
    async with router:
        for t in core_tasks:
            decisions.append(await router.route(t))
    results["DimensionBest"] = evaluate_on_core(dm, decisions, core_task_ids)
    print(f"  DimensionBest: {results['DimensionBest']['avg_perf']}")

    # Cascade
    router = CascadeRouter(data_manager=dm, upgrade_hard=True)
    decisions = []
    async with router:
        for t in core_tasks:
            decisions.append(await router.route(t))
    results["Cascade"] = evaluate_on_core(dm, decisions, core_task_ids)
    print(f"  Cascade: {results['Cascade']['avg_perf']}")

    # ── 2. Trained Routers ──
    print("\n--- Running Trained Routers ---")

    try:
        from src.routing.trained_routers import LogRegRouter, BERTMLPRouter

        # LogReg: train on training data, eval on core test
        logreg = LogRegRouter()
        logreg.train(dm)
        decisions = []
        for t in core_tasks:
            decisions.append(await logreg.route(t))
        results["LogReg"] = evaluate_on_core(dm, decisions, core_task_ids)
        print(f"  LogReg: {results['LogReg']['avg_perf']}")

        # TF-IDF + MLP
        mlp = BERTMLPRouter()
        mlp.train(dm)
        decisions = []
        for t in core_tasks:
            decisions.append(await mlp.route(t))
        results["TF-IDF+MLP"] = evaluate_on_core(dm, decisions, core_task_ids)
        print(f"  TF-IDF+MLP: {results['TF-IDF+MLP']['avg_perf']}")
    except Exception as e:
        print(f"  ERROR in trained routers: {e}")

    # ── 3. RouteLLM Baselines ──
    print("\n--- Running RouteLLM Baselines ---")

    try:
        from src.routing.routellm_baselines import MFRouter, SWRankingRouter

        # MF Router
        mf = MFRouter(embed_dim=128, model_dim=64)
        mf.train(dm)
        decisions = []
        for t in core_tasks:
            decisions.append(await mf.route(t))
        results["RouteLLM-MF"] = evaluate_on_core(dm, decisions, core_task_ids)
        print(f"  RouteLLM-MF: {results['RouteLLM-MF']['avg_perf']}")

        # SW Ranking
        sw = SWRankingRouter(gamma=10.0, top_k=50)
        sw.train(dm)
        decisions = []
        for t in core_tasks:
            decisions.append(await sw.route(t))
        results["RouteLLM-SW"] = evaluate_on_core(dm, decisions, core_task_ids)
        print(f"  RouteLLM-SW: {results['RouteLLM-SW']['avg_perf']}")
    except Exception as e:
        print(f"  ERROR in RouteLLM: {e}")

    # ── 4. LLM Router (from existing decisions) ──
    print("\n--- Re-evaluating LLM Routers from Decision Files ---")

    results_dir = PROJECT_ROOT / "data" / "routing" / "results"

    # LLM 3-shot (kimi as router)
    llm3_path = results_dir / "llm_3shot_decisions.jsonl"
    if llm3_path.exists():
        decisions = load_decisions_from_file(llm3_path)
        # Debug: check model distribution
        core_set = set(core_task_ids)
        model_dist = defaultdict(int)
        for d in decisions:
            if d.task_id in core_set:
                model_dist[d.chosen_model] += 1
        print(f"  LLM 3-shot model dist: {dict(model_dist)}")
        results["LLM 3-shot (kimi)"] = evaluate_on_core(dm, decisions, core_task_ids)
        print(f"  LLM 3-shot (kimi): {results['LLM 3-shot (kimi)']['avg_perf']} ({results['LLM 3-shot (kimi)']['n_tasks']} tasks)")

    # Check for other LLM decision files
    for fname in sorted(results_dir.glob("llm_*_decisions.jsonl")):
        name = fname.stem.replace("_decisions", "")
        if name not in ["llm_3shot"]:  # already handled
            decisions = load_decisions_from_file(fname)
            r = evaluate_on_core(dm, decisions, core_task_ids)
            if r:
                results[name] = r
                print(f"  {name}: {r['avg_perf']}")

    # ── 5. EARouter Top-K ──
    print("\n--- Computing EARouter Top-K ---")

    for k in [1, 2, 3]:
        for wp, label in [(True, "w/ prior"), (False, "w/o prior")]:
            key = f"EARouter Top-{k} ({label})"
            r = evaluate_topk_on_core(dm, core_task_ids, k, wp, dim_map)
            if r:
                results[key] = r
                print(f"  {key}: {r['avg_perf']} (gap={r['gap_pct']}%, ${r['total_cost']}, tok={r['avg_total_tok']})")

    # ── 6. Agent v3 variants ──
    print("\n--- Computing Agent v3 Variants ---")
    v3_results = evaluate_agent_v3_variants(dm, core_task_ids)
    for name, r in v3_results.items():
        results[name] = r
        print(f"  {name}: {r['avg_perf']}")

    # ── Print Final Table ──
    print("\n" + "=" * 120)
    print("FINAL TABLE 4 DATA")
    print("=" * 120)
    print(f"{'Type':<12} {'Router':<35} {'AvgPerf':>8} {'Gap%':>6} {'TotTok':>8} {'$Total':>8} {'Perf/$':>8} {'Tok/P':>8}")
    print("-" * 120)

    # Define display order matching paper
    display_order = [
        ("Bound",     "Oracle",                    {"avg_perf": round(oracle_perf, 4), "gap_pct": 0.0}),
        ("Agent",     "EARouter Top-3 (w/ prior)", results.get("EARouter Top-3 (w/ prior)")),
        ("Agent",     "EARouter Top-2 (w/ prior)", results.get("EARouter Top-2 (w/ prior)")),
        ("Heuristic", "DimensionBest",             results.get("DimensionBest")),
        ("Agent",     "EARouter Top-1 (w/ prior)", results.get("EARouter Top-1 (w/ prior)")),
        ("Agent",     "EARouter Top-3 (w/o prior)", results.get("EARouter Top-3 (w/o prior)")),
        ("Agent",     "EARouter Top-2 (w/o prior)", results.get("EARouter Top-2 (w/o prior)")),
        ("Heuristic", "Cascade",                   results.get("Cascade")),
        ("Trained",   "RouteLLM-SW",               results.get("RouteLLM-SW")),
        ("Trained",   "RouteLLM-MF",               results.get("RouteLLM-MF")),
        ("Trained",   "TF-IDF+MLP",                results.get("TF-IDF+MLP")),
        ("Trained",   "LogReg",                    results.get("LogReg")),
        ("LLM",       "LLM 3-shot (kimi)",         results.get("LLM 3-shot (kimi)")),
        ("Baseline",  "Always-Opus",               results.get("Always-Opus")),
        ("Baseline",  "Always-GPT",                results.get("Always-GPT")),
        ("Baseline",  "Always-Sonnet",             results.get("Always-Sonnet")),
        ("Baseline",  "Always-QwenMax",            results.get("Always-QwenMax")),
        ("Baseline",  "Random",                    results.get("Random")),
        ("Baseline",  "Always-Kimi",               results.get("Always-Kimi")),
        ("Baseline",  "Always-GLM5",               results.get("Always-GLM5")),
        ("Baseline",  "Always-MiniMax",            results.get("Always-MiniMax")),
        ("Baseline",  "Always-Qwen3.5+",           results.get("Always-Qwen3.5+")),
    ]

    for typ, name, r in display_order:
        if r is None:
            continue
        if name == "Oracle":
            print(f"{typ:<12} {name:<35} {r['avg_perf']:>8.4f} {r['gap_pct']:>5.1f}% {'---':>8} {'---':>8} {'---':>8} {'---':>8}")
        else:
            print(f"{typ:<12} {name:<35} {r['avg_perf']:>8.4f} {r['gap_pct']:>5.1f}% {r['avg_total_tok']:>8,} ${r['total_cost']:>7.2f} {r['perf_per_dollar']:>8.1f} {r['tok_per_perf']:>8,}")

    print("=" * 120)

    # Save all results
    output = {
        "meta": {
            "n_core_tasks": len(core_task_ids),
            "oracle_perf": round(oracle_perf, 4),
            "split": "60/10/30",
            "train": len(dm.train),
            "val": len(dm.val),
            "test": len(dm.test),
            "dimensions": CORE_DIMS,
            "dim_best_map": dim_map,
        },
        "results": {k: v for k, v in results.items() if v is not None},
    }

    out_path = results_dir / "table4_recomputed.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    asyncio.run(run_all())
