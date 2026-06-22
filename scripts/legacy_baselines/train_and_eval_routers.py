#!/usr/bin/env python3
"""Train and evaluate LogReg and BERT/MLP routers.

Usage:
    # Train both routers and evaluate on the test split
    python scripts/train_and_eval_routers.py

    # Train only LogReg
    python scripts/train_and_eval_routers.py --routers logreg

    # Evaluate on validation split
    python scripts/train_and_eval_routers.py --split val

    # Include baselines in comparison table
    python scripts/train_and_eval_routers.py --compare-baselines

    # Skip training (load previously saved models)
    python scripts/train_and_eval_routers.py --load-only
"""
import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.routing.base import BACKEND_MODELS, RoutingDecision
from src.routing.data_manager import DataManager
from dataclasses import asdict
from src.routing.evaluator import RouterEvaluator, RouterMetrics
from src.routing.trained_routers import LogRegRouter, BERTMLPRouter


from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train and evaluate trained router baselines (LogReg + BERT/MLP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--routers", type=str, default="bert_mlp",
        help="Comma-separated list of routers to train: logreg, bert_mlp (default: both)",
    )
    parser.add_argument(
        "--split", type=str, default="test", choices=["train", "val", "test"],
        help="Split to evaluate on (default: test)",
    )
    parser.add_argument(
        "--model-dir", type=str, default=None,
        help="Directory to save/load trained models (default: data/routing/trained_models)",
    )
    parser.add_argument(
        "--compare-baselines", action="store_true",
        help="Include random and dimension_best baselines in comparison table",
    )
    parser.add_argument(
        "--load-only", action="store_true",
        help="Skip training; load previously saved models and evaluate",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Limit evaluation to first N tasks (0 = all, useful for quick testing)",
    )
    return parser.parse_args()


async def run_router(router, tasks: list[dict], limit: int = 0) -> list[RoutingDecision]:
    """Run a router on a list of tasks and return decisions."""
    if limit > 0:
        tasks = tasks[:limit]
    decisions = []
    async with router:
        for i, task in enumerate(tasks):
            try:
                decision = await router.route(task)
                decisions.append(decision)
            except Exception as e:
                decisions.append(RoutingDecision(
                    task_id=task["task_id"],
                    chosen_model=BACKEND_MODELS[0],
                    confidence=0.0,
                    reasoning=f"Error: {e}",
                ))
            if (i + 1) % 200 == 0 or (i + 1) == len(tasks):
                logger.info("[%s] %d/%d tasks routed", router.name, i + 1, len(tasks))
    return decisions


def print_metrics(name: str, m: RouterMetrics):
    """Print a single router's metrics (same format as run_routers.py)."""
    print(f"\n{'='*60}")
    print(f"Router: {name}")
    print(f"{'='*60}")
    print(f"  Tasks evaluated:     {m.n_tasks}")
    print(f"  Avg Performance:     {m.avg_performance:.4f}")
    print(f"  Oracle Performance:  {m.oracle_performance:.4f}")
    print(f"  Oracle Gap:          {m.oracle_gap:.4f} ({m.oracle_gap_pct:.1f}%)")
    print(f"  Routing Accuracy:    {m.routing_accuracy:.4f}")
    print(f"  Strong Model Rate:   {m.strong_model_call_rate:.4f}")
    print(f"  Avg Router Tokens:   {m.avg_router_tokens:.0f}")
    print(f"  Avg Backend Tokens:  {m.avg_backend_tokens:.0f}")
    print(f"  Avg Total Tokens:    {m.avg_total_tokens:.0f}")
    print(f"  Perf/Cost Ratio:     {m.perf_cost_ratio:.4f}")
    print(f"\n  Model Distribution:")
    for model, pct in sorted(m.model_distribution.items()):
        print(f"    {model}: {pct:.1%}")
    if m.per_dimension:
        print(f"\n  Per-Dimension Performance:")
        for dim in sorted(m.per_dimension.keys()):
            d = m.per_dimension[dim]
            print(f"    {dim:25s}: perf={d['avg_performance']:.4f}  "
                  f"oracle={d['oracle_performance']:.4f}  "
                  f"gap={d['oracle_gap']:.4f}  "
                  f"acc={d['routing_accuracy']:.4f}  "
                  f"n={d['n_tasks']}")


def print_comparison_table(results: dict[str, RouterMetrics]):
    """Print a comparison table of all routers."""
    print(f"\n{'='*110}")
    print(f"{'Router':<25s} | {'Perf':>8s} | {'OracleGap':>10s} | "
          f"{'Accuracy':>9s} | {'Strong%':>8s} | {'AvgTokens':>10s} | {'P/C Ratio':>10s}")
    print(f"{'-'*25}-+-{'-'*8}-+-{'-'*10}-+-{'-'*9}-+-{'-'*8}-+-{'-'*10}-+-{'-'*10}")

    for name, m in results.items():
        print(
            f"{name:<25s} | {m.avg_performance:>8.4f} | {m.oracle_gap:>10.4f} | "
            f"{m.routing_accuracy:>9.4f} | {m.strong_model_call_rate:>7.1%} | "
            f"{m.avg_total_tokens:>10.0f} | {m.perf_cost_ratio:>10.4f}"
        )

    print(f"{'='*110}")


async def main():
    args = parse_args()
    router_names = [r.strip() for r in args.routers.split(",")]
    model_dir = Path(args.model_dir) if args.model_dir else None

    # ----- Load data -----
    print("Loading data...")
    dm = DataManager()
    dm.load()
    print(f"  Loaded {len(dm.oracle_labels)} tasks ({len(BACKEND_MODELS)}-model)")
    print(f"  Train: {len(dm.train)}, Val: {len(dm.val)}, Test: {len(dm.test)}")

    split_ids = dm.get_split(args.split)
    tasks = [t for tid in split_ids if (t := dm.get_task(tid)) is not None]
    print(f"  Evaluating on {args.split} split: {len(tasks)} tasks")
    if args.limit > 0:
        print(f"  Limiting to {args.limit} tasks")

    evaluator = RouterEvaluator(dm)
    all_results: dict[str, RouterMetrics] = {}

    # ----- Optional: baseline routers for comparison -----
    if args.compare_baselines:
        from src.routing.baselines import RandomRouter, DimensionRouter

        print("\n--- Running Baseline Routers (for comparison) ---")
        # Random
        decisions = await run_router(RandomRouter(seed=42), tasks, args.limit)
        m = evaluator.evaluate(decisions, args.split)
        all_results["random"] = m
        print_metrics("random", m)

        # Dimension best
        dim_map = dm.get_dimension_best_models()
        decisions = await run_router(DimensionRouter(dimension_map=dim_map), tasks, args.limit)
        m = evaluator.evaluate(decisions, args.split)
        all_results["dimension_best"] = m
        print_metrics("dimension_best", m)

    # ----- LogReg Router -----
    if "logreg" in router_names:
        print("\n--- LogReg Router ---")
        kw = {"model_dir": model_dir} if model_dir else {}
        router = LogRegRouter(**kw)

        if args.load_only:
            print("  Loading previously trained model...")
            router.load()
        else:
            start = time.monotonic()
            print("  Training...")
            router.train(dm)
            elapsed = time.monotonic() - start
            print(f"  Training time: {elapsed:.1f}s")
            router.save()
            print(f"  Model saved to {router.model_dir}")

        print("  Evaluating...")
        decisions = await run_router(router, tasks, args.limit)
        m = evaluator.evaluate(decisions, args.split)
        all_results["logreg"] = m
        print_metrics("logreg", m)

    # ----- BERT / MLP Router -----
    if "bert_mlp" in router_names:
        print("\n--- BERT/MLP Router ---")
        kw = {"model_dir": model_dir} if model_dir else {}
        router = BERTMLPRouter(**kw)

        if args.load_only:
            print("  Loading previously trained model...")
            router.load()
        else:
            start = time.monotonic()
            print("  Training...")
            router.train(dm)
            elapsed = time.monotonic() - start
            print(f"  Training time: {elapsed:.1f}s (backend: {router.name})")
            router.save()
            print(f"  Model saved to {router.model_dir}")

        print("  Evaluating...")
        decisions = await run_router(router, tasks, args.limit)
        m = evaluator.evaluate(decisions, args.split)
        all_results[router.name] = m
        print_metrics(router.name, m)

    # ----- Save metrics to JSON -----
    results_dir = PROJECT_ROOT / "data" / "routing" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    for name, m in all_results.items():
        out_path = results_dir / f"{name}_metrics.json"
        with open(out_path, "w") as f:
            json.dump(asdict(m), f, indent=2)
        print(f"  Metrics saved to {out_path}")

    # ----- Comparison table -----
    if len(all_results) > 1:
        print_comparison_table(all_results)

    # ----- OOD Evaluation: agentic_programming -----
    print("\n" + "=" * 60)
    print("OOD Evaluation: agentic_programming")
    print("=" * 60)

    # Load a separate DataManager that ONLY has agentic_programming
    dm_ood = DataManager(exclude_dims=frozenset())
    dm_ood.load()
    ood_split_ids = dm_ood.get_split(args.split)
    ood_tasks = [
        t for tid in ood_split_ids
        if (t := dm_ood.get_task(tid)) is not None
        and t.get("dimension") == "agentic_programming"
    ]

    if not ood_tasks:
        print("  No agentic_programming tasks found in test split. Skipping OOD eval.")
    else:
        print(f"  OOD tasks: {len(ood_tasks)}")
        ood_evaluator = RouterEvaluator(dm_ood)
        ood_results: dict[str, RouterMetrics] = {}

        # Re-use trained routers (already in memory), just run on OOD tasks
        if "logreg" in router_names and "logreg" in all_results:
            kw = {"model_dir": model_dir} if model_dir else {}
            router = LogRegRouter(**kw)
            router.load()
            decisions = await run_router(router, ood_tasks, args.limit)
            m = ood_evaluator.evaluate(decisions, args.split)
            ood_results["logreg"] = m
            print_metrics("logreg (OOD)", m)

        if "bert_mlp" in router_names and any(
            k in all_results for k in ("bert_mlp", "tfidf_mlp")
        ):
            kw = {"model_dir": model_dir} if model_dir else {}
            router = BERTMLPRouter(**kw)
            router.load()
            decisions = await run_router(router, ood_tasks, args.limit)
            m = ood_evaluator.evaluate(decisions, args.split)
            ood_results[router.name] = m
            print_metrics(f"{router.name} (OOD)", m)

        if args.compare_baselines:
            from src.routing.baselines import RandomRouter, DimensionRouter

            decisions = await run_router(RandomRouter(seed=42), ood_tasks, args.limit)
            m = ood_evaluator.evaluate(decisions, args.split)
            ood_results["random"] = m
            print_metrics("random (OOD)", m)

            # DimensionBest uses dim map from core 9 dims (trained on ID data)
            dim_map = dm.get_dimension_best_models()
            decisions = await run_router(DimensionRouter(dimension_map=dim_map), ood_tasks, args.limit)
            m = ood_evaluator.evaluate(decisions, args.split)
            ood_results["dimension_best"] = m
            print_metrics("dimension_best (OOD)", m)

        # Save OOD metrics
        for name, m in ood_results.items():
            out_path = results_dir / f"{name}_ood_metrics.json"
            with open(out_path, "w") as f:
                json.dump(asdict(m), f, indent=2)
            print(f"  Metrics saved to {out_path}")

        if len(ood_results) > 1:
            print_comparison_table(ood_results)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
