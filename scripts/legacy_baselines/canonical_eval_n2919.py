"""Strict n=2919 recompute for all router baselines.

Canonical n=2919 set = (canonical test split) ∩ (9 probing dims, excludes
dim10 agentic_programming).

For every router whose decisions cover this set, recompute:
  - AvgPerf
  - Oracle gap %
  - rAcc (lex tie-break: max perf > min cost > min tokens > tolerate)
  - Avg total tokens
  - Total $ cost
  - Perf/$
  - Strong-model call rate

Outputs a JSON with the canonical n=2919 numbers per router. This is the
single source of truth for paper tables.

Usage:
    python recompute_metrics_n2919.py --repo-root . --out metrics_n2919.json
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


DIMS_PROBING = [
    "code_generation", "algorithm", "bug_fixing", "code_completion",
    "code_refactoring", "data_science", "multi_language",
    "code_understanding", "test_generation",
]
MODELS = [
    "claude-opus-4-6", "claude-sonnet-4-6", "gpt-5.4", "Qwen3-Max",
    "qwen3.5-plus", "kimi-k2.5", "glm-5", "MiniMax-M2.7",
]

# Blended USD per total token (input+output mixed) — back-derived from
# Always-* baselines in the existing paper table so $Total reproduces:
#   always_opus  $34 / (691 tok * 2919 tasks) ≈ $16.86 / M
#   always_sonnet $25 / 2.328M ≈ $10.74 / M
#   always_gpt   $16.6 / 1.713M ≈ $9.69 / M
#   always_qwenmax $1.5 / 1.673M ≈ $0.90 / M
PRICE_PER_TOKEN = {
    "claude-opus-4-6":   16.86e-6,
    "claude-sonnet-4-6": 10.74e-6,
    "gpt-5.4":            9.69e-6,
    "Qwen3-Max":          0.90e-6,
    "qwen3.5-plus":       0.50e-6,
    "kimi-k2.5":          1.50e-6,
    "glm-5":              1.20e-6,
    "MiniMax-M2.7":       1.20e-6,
}


def build_canonical_2919(repo_root: Path) -> set:
    """canonical test ∩ 9 probing dims."""
    test_ids = set(json.load(open(repo_root / "data" / "routing" / "splits" / "test.json")))
    nine_dim_ids = set()
    for f in (repo_root / "data" / "processed").glob("*.jsonl"):
        if f.stem not in DIMS_PROBING:
            continue
        for line in open(f):
            d = json.loads(line)
            if d.get("task_id"):
                nine_dim_ids.add(d["task_id"])
    return test_ids & nine_dim_ids


def build_obs(repo_root: Path) -> dict:
    """obs[task_id][model] = {'perf', 'tokens', 'cost'}"""
    obs = defaultdict(dict)
    for m in MODELS:
        for dim in DIMS_PROBING:
            f = repo_root / "data" / "results" / m / f"{dim}.jsonl"
            if not f.exists():
                continue
            for line in open(f):
                d = json.loads(line)
                if d.get("score") is None:
                    continue
                tok = int((d.get("input_tokens") or 0)
                           + (d.get("output_tokens") or 0))
                obs[d["task_id"]][m] = {
                    "perf":   float(d["score"]),
                    "tokens": tok,
                    "cost":   tok * PRICE_PER_TOKEN.get(m, 1e-6),
                }
    return obs


def oracle_set(row, eps=1e-9) -> set:
    """Lex tie-break: max perf > min cost > min tokens > tolerate."""
    if not row:
        return set()
    max_p = max(o["perf"] for o in row.values())
    cands = {m for m, o in row.items() if abs(o["perf"] - max_p) < eps}
    if len(cands) > 1:
        min_c = min(row[m]["cost"] for m in cands)
        cands = {m for m in cands if abs(row[m]["cost"] - min_c) < eps}
    if len(cands) > 1:
        min_t = min(row[m]["tokens"] for m in cands)
        cands = {m for m in cands if row[m]["tokens"] == min_t}
    return cands


def compute(decisions_file: Path, canonical: set, obs: dict) -> dict | None:
    """Compute all paper metrics for a single router on the canonical n=2919."""
    if not decisions_file.exists():
        return None
    perfs = []
    costs = []
    tokens = []
    correct = 0
    n = 0
    chosen_models = []
    oracle_perfs = []
    cum_regret = 0.0
    for line in open(decisions_file):
        d = json.loads(line)
        tid = d.get("task_id")
        chosen = d.get("chosen_model") or d.get("selected_model")
        if tid not in canonical or not chosen:
            continue
        row = obs.get(tid)
        if not row or chosen not in row:
            continue
        rec = row[chosen]
        perfs.append(rec["perf"])
        costs.append(rec["cost"])
        tokens.append(rec["tokens"])
        chosen_models.append(chosen)
        # Oracle
        max_p = max(o["perf"] for o in row.values())
        oracle_perfs.append(max_p)
        cum_regret += max_p - rec["perf"]
        # rAcc
        if chosen in oracle_set(row):
            correct += 1
        n += 1
    if n == 0:
        return None
    avg_perf = sum(perfs) / n
    avg_oracle = sum(oracle_perfs) / n
    gap = avg_oracle - avg_perf
    gap_pct = gap / avg_oracle * 100 if avg_oracle > 0 else 0
    total_cost = sum(costs)
    avg_cost = total_cost / n if n else 0
    avg_tokens = sum(tokens) / n if n else 0
    perf_per_dollar = (avg_perf / avg_cost) if avg_cost > 0 else float("inf")
    rAcc = correct / n * 100
    # Strong-model rate (Opus, Sonnet, GPT count as "strong")
    strong = {"claude-opus-4-6", "claude-sonnet-4-6", "gpt-5.4"}
    strong_rate = sum(1 for m in chosen_models if m in strong) / n * 100
    # Model distribution
    from collections import Counter
    md = Counter(chosen_models)
    md_pct = {m: c / n for m, c in md.items()}
    return {
        "n": n,
        "avg_perf": round(avg_perf, 4),
        "oracle_perf": round(avg_oracle, 4),
        "gap_pct": round(gap_pct, 2),
        "rAcc_pct": round(rAcc, 2),
        "avg_tokens": round(avg_tokens, 1),
        "total_cost_usd": round(total_cost, 3),
        "avg_cost_usd": round(avg_cost, 6),
        "perf_per_dollar": round(perf_per_dollar, 2),
        "cumulative_regret": round(cum_regret, 2),
        "strong_model_rate_pct": round(strong_rate, 2),
        "model_distribution": {m: round(p, 4) for m, p in md_pct.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out", default="metrics_n2919.json")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    print(f"[1/3] Building canonical n=2919 set...")
    canonical = build_canonical_2919(root)
    print(f"  canonical n = {len(canonical)}")

    print(f"[2/3] Loading observation matrix...")
    obs = build_obs(root)
    print(f"  obs: {len(obs)} tasks, {sum(len(v) for v in obs.values())} cells")

    print(f"[3/3] Recomputing metrics for all routers on n={len(canonical)}...")
    out = {"canonical_n": len(canonical), "routers": {}}
    decisions_dir = root / "data" / "routing" / "results"

    for f in sorted(decisions_dir.glob("*_decisions.jsonl")):
        name = f.stem.replace("_decisions", "")
        m = compute(f, canonical, obs)
        if m is None:
            continue
        out["routers"][name] = m
        flag = "" if m["n"] == len(canonical) else f"  (only {m['n']}/{len(canonical)} covered)"
        print(f"  {name:<48} avg_perf={m['avg_perf']:.4f} rAcc={m['rAcc_pct']:5.1f}% gap={m['gap_pct']:.1f}%  n={m['n']}{flag}")

    out_path = root / args.out
    json.dump(out, open(out_path, "w"), indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
