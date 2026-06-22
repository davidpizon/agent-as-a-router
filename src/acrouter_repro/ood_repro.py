"""OOD reproduction: verify-and-escalate cascade and paper metrics."""

from __future__ import annotations

from pathlib import Path

from .constants import OOD_CHEAP_CHAIN, OOD_ESCALATE_TO, REWARD_COST_WEIGHT
from .io_utils import read_json, write_json, write_jsonl


class OODData:
    def __init__(self, matrix_path: Path):
        raw = read_json(matrix_path)
        self.ids: list[str] = raw["ids"]
        self.models: list[str] = raw["models"]
        self.matrix: dict = raw["matrix"]
        self.reward_oracle_value, self.reward_oracle_model = self._reward_oracle()

    def cell(self, task_id: str, model: str) -> dict:
        return self.matrix.get(task_id, {}).get(model, {})

    def resolved(self, task_id: str, model: str) -> float:
        return 1.0 if self.cell(task_id, model).get("resolved") else 0.0

    def apply_ok(self, task_id: str, model: str) -> float:
        return 1.0 if self.cell(task_id, model).get("apply_ok") else 0.0

    def cost(self, task_id: str, model: str) -> float:
        return float(self.cell(task_id, model).get("cost_usd", 0.0) or 0.0)

    def tokens(self, task_id: str, model: str) -> tuple[int, int]:
        cell = self.cell(task_id, model)
        return int(cell.get("in_tok", 0) or 0), int(cell.get("out_tok", 0) or 0)

    def _reward_oracle(self) -> tuple[dict[str, float], dict[str, str]]:
        values: dict[str, float] = {}
        models: dict[str, str] = {}
        for tid in self.ids:
            best_value = -1e9
            best_model = self.models[0]
            for model in self.models:
                reward = self.resolved(tid, model) - REWARD_COST_WEIGHT * self.cost(tid, model)
                if reward > best_value:
                    best_value = reward
                    best_model = model
            values[tid] = best_value
            models[tid] = best_model
        return values, models


def verify_and_escalate(
    data: OODData,
    k: int = 2,
    cheap_chain: list[str] | None = None,
    escalate_to: str = OOD_ESCALATE_TO,
) -> list[dict]:
    chain = cheap_chain or OOD_CHEAP_CHAIN
    rows: list[dict] = []
    for tid in data.ids:
        run: list[str] = []
        total_cost = 0.0
        cheap_apply_count = 0
        final_model = chain[-1]
        final_resolved = 0.0
        final_apply = 0.0

        for model in chain:
            run.append(model)
            total_cost += data.cost(tid, model)
            cheap_apply_count += int(data.apply_ok(tid, model) > 0)
            final_model = model
            final_resolved = data.resolved(tid, model)
            final_apply = data.apply_ok(tid, model)
            if final_resolved >= 1.0:
                break

        escalated = False
        if final_resolved < 1.0 and cheap_apply_count >= k:
            model = escalate_to
            run.append(model)
            total_cost += data.cost(tid, model)
            escalated = True
            if data.resolved(tid, model) > final_resolved:
                final_model = model
                final_resolved = data.resolved(tid, model)
                final_apply = data.apply_ok(tid, model)

        rows.append(
            {
                "task_id": tid,
                "chosen_model": final_model,
                "chain_run": run,
                "resolved": bool(final_resolved),
                "apply_ok": bool(final_apply),
                "cost_usd": round(total_cost, 6),
                "escalated": escalated,
                "n_steps": len(run),
                "applied_in_cheap": cheap_apply_count,
            }
        )
    return rows


def score_ood(data: OODData, rows: list[dict]) -> dict:
    n = len(rows)
    resolved = 0
    apply_ok = 0
    total_cost = 0.0
    cum_reg = 0.0
    correct = 0
    steps = 0
    escalations = 0
    total_in = 0
    total_out = 0

    for row in rows:
        tid = row["task_id"]
        model = row["chosen_model"]
        if "resolved" in row:
            perf = 1.0 if row["resolved"] else 0.0
        else:
            perf = data.resolved(tid, model)
        cost = float(row.get("cost_usd", data.cost(tid, model)) or 0.0)
        resolved += int(perf >= 1.0)
        if "apply_ok" in row:
            apply_ok += int(bool(row["apply_ok"]))
        else:
            apply_ok += int(bool(data.apply_ok(tid, model)))
        total_cost += cost
        cum_reg += data.reward_oracle_value[tid] - (perf - REWARD_COST_WEIGHT * cost)
        correct += int(model == data.reward_oracle_model[tid])
        steps += int(row.get("n_steps", 1))
        escalations += int(row.get("escalated", False))
        for run_model in row.get("chain_run", [model]):
            in_tok, out_tok = data.tokens(tid, run_model)
            total_in += in_tok
            total_out += out_tok

    avg_perf = resolved / n * 100 if n else 0.0
    return {
        "n": n,
        "AvgPerf%": round(avg_perf, 2),
        "CumReg": round(cum_reg, 1),
        "$Total": round(total_cost, 2),
        "Perf/$": round(avg_perf / total_cost, 2) if total_cost else float("inf"),
        "rAcc_reward_oracle": round(correct / n, 4) if n else 0.0,
        "Apply_ok%": round(apply_ok / n * 100, 2) if n else 0.0,
        "AvgSteps": round(steps / n, 2) if n else 0.0,
        "Escalations": escalations,
        "TotInTok": total_in,
        "TotOutTok": total_out,
    }


def run_ood(matrix_path: Path, output_dir: Path, k: int = 2) -> dict:
    data = OODData(matrix_path)
    decisions = verify_and_escalate(data, k=k)
    metrics = score_ood(data, decisions)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "ood_decisions.jsonl", decisions)
    write_json(output_dir / "ood_metrics.json", metrics)
    return {"metrics": metrics, "decisions": decisions}
