#!/usr/bin/env python3
"""CLI entry point for running and evaluating routers.

Usage:
    # Baselines (no API calls, instant)
    python scripts/run_routers.py --routers baselines --split test

    # LLM router with default model (claude-sonnet-4-6 via idealab)
    python scripts/run_routers.py --routers llm_zero_shot --split test --limit 10

    # LLM router with open-source model (vLLM/Ollama endpoint)
    python scripts/run_routers.py --routers llm_zero_shot --split test \\
        --router-model qwen3.5-27b-inner-api --model-config configs/models_vllm.yaml

    # All routers + comparison table
    python scripts/run_routers.py --routers all --split test --compare

    # Generate fine-tuning data
    python scripts/run_routers.py --prepare-finetune
"""
import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path

# Force unbuffered output (visible in nohup/background)
os.environ["PYTHONUNBUFFERED"] = "1"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.routing.base import BACKEND_MODELS, RoutingDecision
from src.routing.data_manager import DataManager
from src.routing.evaluator import RouterEvaluator, RouterMetrics
from src.routing.baselines import RandomRouter, AlwaysBestRouter, AlwaysCheapestRouter, DimensionRouter
from src.routing.cascade_router import CascadeRouter


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run and evaluate CodingRouter routers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run baselines only (no API needed)
  %(prog)s --routers baselines --split test

  # Test LLM router on 10 tasks
  %(prog)s --routers llm_zero_shot --split test --limit 10

  # Use a local open-source model as router
  %(prog)s --routers llm_zero_shot --router-model qwen2.5-7b \\
           --model-config configs/models_vllm.yaml

  # Run everything and compare
  %(prog)s --routers all --split test --compare
        """,
    )
    parser.add_argument(
        "--routers", type=str, default="baselines",
        help="Routers to run (comma-separated): baselines, llm_zero_shot, llm_3shot, cascade, all",
    )
    parser.add_argument("--split", type=str, default="test", choices=["train", "val", "test"])
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 = all)")
    parser.add_argument("--config", type=str, default="configs/routing.yaml",
                        help="Path to routing config YAML")
    parser.add_argument("--router-model", type=str, default=None,
                        help="Override LLM router model name (e.g., qwen2.5-7b)")
    parser.add_argument("--model-config", type=str, default=None,
                        help="Override model config YAML path (e.g., configs/models_vllm.yaml)")
    parser.add_argument("--compare", action="store_true", help="Output comparison table")
    parser.add_argument("--prepare-finetune", action="store_true", help="Generate fine-tuning data")
    parser.add_argument("--no-save", action="store_true", help="Do not save results to disk")
    return parser.parse_args()


def load_routing_config(config_path: str) -> dict:
    """Load the routing YAML config."""
    try:
        import yaml
    except ImportError:
        print("WARNING: pyyaml not installed. Using default config. Install: pip install pyyaml")
        return {}
    full_path = PROJECT_ROOT / config_path
    if not full_path.exists():
        print(f"WARNING: Config file not found: {full_path}. Using defaults.")
        return {}
    with open(full_path) as f:
        return yaml.safe_load(f) or {}


async def run_router(router, tasks: list[dict], limit: int = 0) -> list[RoutingDecision]:
    """Run a router on a list of tasks."""
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
            if (i + 1) % 50 == 0 or (i + 1) == len(tasks):
                print(f"  [{router.name}] {i+1}/{len(tasks)} tasks routed", flush=True)

    return decisions


async def run_llm_router(
    router_type: str,
    dm: DataManager,
    tasks: list[dict],
    limit: int,
    cfg: dict,
    router_model_override: str | None = None,
    model_config_override: str | None = None,
):
    """Run an LLM-based router."""
    from src.evaluation.api_client import LLMClient
    from src.routing.llm_router import LLMZeroShotRouter, LLMFewShotRouter

    llm_cfg = cfg.get("llm_router", {})

    # Resolve model config path (CLI override > YAML > default)
    if model_config_override:
        model_config_path = str(PROJECT_ROOT / model_config_override)
    else:
        model_config_path = str(PROJECT_ROOT / llm_cfg.get("model_config", "configs/models_idealab.yaml"))

    # Resolve router model name (CLI override > YAML > default)
    router_model = router_model_override or llm_cfg.get("router_model", "claude-sonnet-4-6")

    print(f"  Router model: {router_model}")
    print(f"  Model config: {model_config_path}")

    client = LLMClient.from_yaml(model_config_path)

    # Validate router model exists in config
    if router_model not in client.models:
        available = list(client.models.keys())
        raise ValueError(
            f"Router model '{router_model}' not found in model config. "
            f"Available models: {available}"
        )

    # Override defaults for routing (fast, short responses)
    client.defaults["temperature"] = llm_cfg.get("temperature", 0.0)
    client.defaults["max_tokens"] = llm_cfg.get("max_tokens", 256)

    try:
        if router_type == "llm_zero_shot":
            router = LLMZeroShotRouter(client, router_model)
        elif router_type == "llm_3shot":
            n_shots = cfg.get("few_shot", {}).get("n_shots", 3)
            router = LLMFewShotRouter(client, dm, router_model, n_shots)
        else:
            raise ValueError(f"Unknown LLM router type: {router_type}")

        return await run_router(router, tasks, limit)
    finally:
        await client.close()


def print_metrics(name: str, m: RouterMetrics):
    """Print a single router's metrics."""
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
            print(f"    {dim:25s}: perf={d['avg_performance']:.4f}  oracle={d['oracle_performance']:.4f}  gap={d['oracle_gap']:.4f}  acc={d['routing_accuracy']:.4f}  n={d['n_tasks']}")


def print_comparison_table(results: dict[str, RouterMetrics]):
    """Print a comparison table of all routers."""
    print(f"\n{'='*110}")
    print(f"{'Router':<25s} | {'Perf':>8s} | {'OracleGap':>10s} | {'Accuracy':>9s} | {'Strong%':>8s} | {'AvgTokens':>10s} | {'P/C Ratio':>10s}")
    print(f"{'-'*25}-+-{'-'*8}-+-{'-'*10}-+-{'-'*9}-+-{'-'*8}-+-{'-'*10}-+-{'-'*10}")

    for name, m in results.items():
        print(
            f"{name:<25s} | {m.avg_performance:>8.4f} | {m.oracle_gap:>10.4f} | "
            f"{m.routing_accuracy:>9.4f} | {m.strong_model_call_rate:>7.1%} | "
            f"{m.avg_total_tokens:>10.0f} | {m.perf_cost_ratio:>10.4f}"
        )

    print(f"{'='*110}")


def save_results(name: str, decisions: list[RoutingDecision], metrics: RouterMetrics, output_dir: Path):
    """Save router decisions and metrics to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / f"{name}_decisions.jsonl", "w") as f:
        for d in decisions:
            f.write(d.to_json() + "\n")

    with open(output_dir / f"{name}_metrics.json", "w") as f:
        json.dump(metrics.to_dict(), f, indent=2, ensure_ascii=False)


def prepare_finetune_data(dm: DataManager):
    """Generate training data for fine-tuning a routing model."""
    from src.routing.prompts import build_zero_shot_prompt

    output_dir = PROJECT_ROOT / "data" / "routing" / "finetune"
    output_dir.mkdir(parents=True, exist_ok=True)

    records = []
    skipped = 0
    for task_id in dm.train:
        scores = {m: dm.get_score(task_id, m) for m in BACKEND_MODELS}
        if len(set(scores.values())) <= 1:
            skipped += 1
            continue

        task = dm.get_task(task_id)
        if not task:
            continue

        best_model = dm.get_oracle_model(task_id)
        prompt = build_zero_shot_prompt(task)

        records.append({
            "input": prompt,
            "output": best_model,
            "task_id": task_id,
            "dimension": task.get("dimension", "unknown"),
            "difficulty": task.get("difficulty", "unknown"),
            "all_scores": scores,
        })

    output_path = output_dir / "training_data.jsonl"
    with open(output_path, "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Also generate val data for eval during training
    val_records = []
    for task_id in dm.val:
        scores = {m: dm.get_score(task_id, m) for m in BACKEND_MODELS}
        if len(set(scores.values())) <= 1:
            continue
        task = dm.get_task(task_id)
        if not task:
            continue
        best_model = dm.get_oracle_model(task_id)
        prompt = build_zero_shot_prompt(task)
        val_records.append({
            "input": prompt,
            "output": best_model,
            "task_id": task_id,
            "dimension": task.get("dimension", "unknown"),
            "difficulty": task.get("difficulty", "unknown"),
            "all_scores": scores,
        })

    val_path = output_dir / "val_data.jsonl"
    with open(val_path, "w") as f:
        for r in val_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nFine-tuning data generated:")
    print(f"  Total train tasks: {len(dm.train)}")
    print(f"  Skipped (tied scores): {skipped}")
    print(f"  Training examples: {len(records)}")
    print(f"  Validation examples: {len(val_records)}")
    print(f"  Saved to: {output_path}")
    print(f"  Val saved to: {val_path}")

    from collections import Counter
    dist = Counter(r["output"] for r in records)
    print(f"  Label distribution: {dict(dist)}")


def _run_and_eval(
    name: str,
    decisions: list[RoutingDecision],
    evaluator: RouterEvaluator,
    split: str,
    save: bool,
    output_dir: Path,
    all_results: dict[str, RouterMetrics],
):
    """Evaluate decisions and save results."""
    m = evaluator.evaluate(decisions, split)
    all_results[name] = m
    print_metrics(name, m)
    if save:
        save_results(name, decisions, m, output_dir)


async def main():
    args = parse_args()
    cfg = load_routing_config(args.config)
    save = not args.no_save

    print("Loading data...")
    dm = DataManager()
    dm.load()
    print(f"  Loaded {len(dm.oracle_labels)} tasks ({len(BACKEND_MODELS)}-model)")
    print(f"  Train: {len(dm.train)}, Val: {len(dm.val)}, Test: {len(dm.test)}")

    if args.prepare_finetune:
        prepare_finetune_data(dm)
        return

    # Get tasks for the requested split
    split_ids = dm.get_split(args.split)
    tasks = [t for tid in split_ids if (t := dm.get_task(tid)) is not None]
    print(f"  Evaluating on {args.split} split: {len(tasks)} tasks")
    if args.limit > 0:
        print(f"  Limiting to {args.limit} tasks")

    evaluator = RouterEvaluator(dm)
    output_dir = PROJECT_ROOT / "data" / "routing" / "results"
    all_results: dict[str, RouterMetrics] = {}

    # Determine which routers to run
    router_names = [r.strip() for r in args.routers.split(",")]
    run_baselines = "baselines" in router_names or "all" in router_names
    run_llm_zero = "llm_zero_shot" in router_names or "all" in router_names
    run_llm_few = "llm_3shot" in router_names or "all" in router_names
    run_cascade = "cascade" in router_names or "all" in router_names

    # --- Baselines ---
    if run_baselines:
        print("\n--- Running Baseline Routers ---")
        try:
            # Random
            decisions = await run_router(RandomRouter(seed=42), tasks, args.limit)
            _run_and_eval("random", decisions, evaluator, args.split, save, output_dir, all_results)

            # Each backend model
            for model in BACKEND_MODELS:
                router = AlwaysBestRouter(best_model=model)
                decisions = await run_router(router, tasks, args.limit)
                _run_and_eval(router.name, decisions, evaluator, args.split, save, output_dir, all_results)

            # Dimension Best
            dim_map = dm.get_dimension_best_models()
            print(f"\n  Learned dimension map: {dim_map}")
            router = DimensionRouter(dimension_map=dim_map)
            decisions = await run_router(router, tasks, args.limit)
            _run_and_eval("dimension_best", decisions, evaluator, args.split, save, output_dir, all_results)
        except Exception as e:
            print(f"\n  ERROR in baselines: {e}")
            traceback.print_exc()

    # --- Cascade ---
    if run_cascade:
        print("\n--- Running Cascade Router ---")
        try:
            cascade_cfg = cfg.get("cascade", {})
            router = CascadeRouter(
                data_manager=dm,
                strong_model=cascade_cfg.get("strong_model", "claude-opus-4-6"),
                upgrade_hard=cascade_cfg.get("upgrade_hard", True),
            )
            decisions = await run_router(router, tasks, args.limit)
            _run_and_eval("cascade_heuristic", decisions, evaluator, args.split, save, output_dir, all_results)
        except Exception as e:
            print(f"\n  ERROR in cascade: {e}")
            traceback.print_exc()

    # --- LLM Routers ---
    if run_llm_zero:
        print("\n--- Running LLM Zero-Shot Router ---")
        try:
            start = time.monotonic()
            decisions = await run_llm_router(
                "llm_zero_shot", dm, tasks, args.limit, cfg,
                router_model_override=args.router_model,
                model_config_override=args.model_config,
            )
            elapsed = time.monotonic() - start
            _run_and_eval("llm_zero_shot", decisions, evaluator, args.split, save, output_dir, all_results)
            print(f"  Wall time: {elapsed:.1f}s")
        except Exception as e:
            print(f"\n  ERROR in llm_zero_shot: {e}")
            traceback.print_exc()

    if run_llm_few:
        print("\n--- Running LLM 3-Shot Router ---")
        try:
            start = time.monotonic()
            decisions = await run_llm_router(
                "llm_3shot", dm, tasks, args.limit, cfg,
                router_model_override=args.router_model,
                model_config_override=args.model_config,
            )
            elapsed = time.monotonic() - start
            _run_and_eval("llm_3shot", decisions, evaluator, args.split, save, output_dir, all_results)
            print(f"  Wall time: {elapsed:.1f}s")
        except Exception as e:
            print(f"\n  ERROR in llm_3shot: {e}")
            traceback.print_exc()

    # --- Comparison ---
    if args.compare or len(all_results) > 1:
        print_comparison_table(all_results)


if __name__ == "__main__":
    asyncio.run(main())
