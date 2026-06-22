"""Train and evaluate RouteLLM baseline methods on CodeRouterBench.

Implements 3 methods from RouteLLM (Ong et al., ICLR 2025):
1. Matrix Factorization (MF) — CPU only, ~1 min
2. SW Ranking — CPU only, ~2 min (inference-time, no training)
3. BERT classifier — GPU required, ~30 min

Usage:
    # CPU only (MF + SW):
    python scripts/run_routellm_baselines.py

    # With GPU (all 3):
    python scripts/run_routellm_baselines.py --include-bert

    # Load pre-trained and evaluate only:
    python scripts/run_routellm_baselines.py --load-only
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.routing.routellm_baselines import MFRouter, BERTRouter, SWRankingRouter
from src.routing.data_manager import DataManager
from src.routing.evaluator import RouterEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def evaluate_router(router, dm, evaluator, split="test"):
    """Evaluate a router on the test split."""
    test_ids = getattr(dm, split)
    decisions = []
    t0 = time.time()

    for i, tid in enumerate(test_ids):
        task = dm.get_task(tid)
        if not task:
            continue
        d = await router.route(task)
        decisions.append(d)
        if (i + 1) % 500 == 0:
            logger.info(f"  [{router.name}] {i+1}/{len(test_ids)} routed")

    elapsed = time.time() - t0
    metrics = evaluator.evaluate(decisions, split=split)

    logger.info(f"  [{router.name}] Done in {elapsed:.1f}s")
    logger.info(f"  [{router.name}] AvgPerf={metrics.avg_performance:.4f} "
                f"Gap={metrics.oracle_gap_pct:.1f}% Acc={metrics.routing_accuracy:.4f}")

    return decisions, metrics


async def main():
    parser = argparse.ArgumentParser(description="Run RouteLLM baselines")
    parser.add_argument("--include-bert", action="store_true",
                        help="Include BERT classifier (requires GPU)")
    parser.add_argument("--load-only", action="store_true",
                        help="Load pre-trained models, skip training")
    parser.add_argument("--split", default="test")
    parser.add_argument("--save-dir", default="data/routing/trained_models")
    args = parser.parse_args()

    # Load data
    logger.info("Loading data...")
    dm = DataManager()
    dm.load()
    evaluator = RouterEvaluator(dm)
    logger.info(f"  train={len(dm.train)} val={len(dm.val)} test={len(dm.test)}")

    results = {}
    results_dir = "data/routing/results"
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(args.save_dir, exist_ok=True)

    # ── 1. Matrix Factorization ──
    logger.info("\n=== Matrix Factorization (MF) Router ===")
    mf = MFRouter(embed_dim=128, model_dim=64)
    if args.load_only:
        mf.load(args.save_dir)
    else:
        mf.train(dm)
        mf.save(args.save_dir)

    decisions, metrics = await evaluate_router(mf, dm, evaluator, args.split)
    with open(os.path.join(results_dir, "routellm_mf_decisions.jsonl"), "w") as f:
        for d in decisions:
            f.write(d.to_json() + "\n")
    with open(os.path.join(results_dir, "routellm_mf_metrics.json"), "w") as f:
        json.dump(metrics.to_dict(), f, indent=2, ensure_ascii=False, default=str)
    results["MF"] = metrics

    # ── 2. SW Ranking ──
    logger.info("\n=== Similarity-Weighted (SW) Ranking Router ===")
    sw = SWRankingRouter(gamma=10.0, top_k=50)
    if args.load_only:
        sw.load(args.save_dir)
    else:
        sw.train(dm)
        sw.save(args.save_dir)

    decisions, metrics = await evaluate_router(sw, dm, evaluator, args.split)
    with open(os.path.join(results_dir, "routellm_sw_decisions.jsonl"), "w") as f:
        for d in decisions:
            f.write(d.to_json() + "\n")
    with open(os.path.join(results_dir, "routellm_sw_metrics.json"), "w") as f:
        json.dump(metrics.to_dict(), f, indent=2, ensure_ascii=False, default=str)
    results["SW"] = metrics

    # ── 3. BERT Classifier (GPU) ──
    if args.include_bert:
        logger.info("\n=== BERT Classifier Router ===")
        bert = BERTRouter(model_name="bert-base-uncased", max_len=512)
        if args.load_only:
            bert.load(args.save_dir)
        else:
            bert.train(dm, epochs=3, batch_size=16, lr=1e-5)
            bert.save(args.save_dir)

        decisions, metrics = await evaluate_router(bert, dm, evaluator, args.split)
        with open(os.path.join(results_dir, "routellm_bert_decisions.jsonl"), "w") as f:
            for d in decisions:
                f.write(d.to_json() + "\n")
        with open(os.path.join(results_dir, "routellm_bert_metrics.json"), "w") as f:
            json.dump(metrics.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        results["BERT"] = metrics

    # ── Summary ──
    print("\n" + "=" * 70)
    print("RouteLLM Baselines Summary")
    print("=" * 70)
    print(f"{'Method':<20} {'AvgPerf':>8} {'Gap%':>7} {'RoutAcc':>8}")
    print("-" * 50)
    for name, m in results.items():
        print(f"  {name:<18} {m.avg_performance:>8.4f} {m.oracle_gap_pct:>6.1f}% {m.routing_accuracy:>8.4f}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
