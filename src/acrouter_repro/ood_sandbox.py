"""OOD routing with an explicit sandbox verifier."""

from __future__ import annotations

from pathlib import Path

from .constants import OOD_CHEAP_CHAIN, OOD_ESCALATE_TO
from .io_utils import write_json, write_jsonl
from .ood_repro import OODData, score_ood
from .predictions import PatchStore
from .sandbox_verifier import PatchCandidate, VerificationResult


class MissingPatchVerifier:
    def verify(self, candidate: PatchCandidate) -> VerificationResult:
        return VerificationResult(
            task_id=candidate.task_id,
            model=candidate.model,
            patch_sha256=candidate.patch_sha256,
            verifier="missing-patch",
            error="empty_or_missing_patch",
        )


def _verify_candidate(task_id: str, model: str, patches: PatchStore, verifier) -> VerificationResult:
    patch = patches.patch(task_id, model)
    if not patch or not patch.strip():
        return MissingPatchVerifier().verify(PatchCandidate(task_id=task_id, model=model, patch=patch or ""))
    return verifier.verify(PatchCandidate(task_id=task_id, model=model, patch=patch))


def verify_and_escalate_with_sandbox(
    data: OODData,
    patches: PatchStore,
    verifier,
    k: int = 2,
    cheap_chain: list[str] | None = None,
    escalate_to: str = OOD_ESCALATE_TO,
    limit: int | None = None,
) -> list[dict]:
    chain = cheap_chain or OOD_CHEAP_CHAIN
    rows: list[dict] = []
    ids = data.ids[:limit] if limit else data.ids
    for tid in ids:
        run: list[str] = []
        verification: list[dict] = []
        total_cost = 0.0
        cheap_apply_count = 0
        final_model = chain[-1]
        final_result: VerificationResult | None = None

        for model in chain:
            run.append(model)
            total_cost += data.cost(tid, model)
            result = _verify_candidate(tid, model, patches, verifier)
            verification.append(result.to_dict())
            cheap_apply_count += int(result.apply_ok)
            final_model = model
            final_result = result
            if result.resolved:
                break

        escalated = False
        if final_result is not None and not final_result.resolved and cheap_apply_count >= k:
            model = escalate_to
            run.append(model)
            total_cost += data.cost(tid, model)
            escalated = True
            result = _verify_candidate(tid, model, patches, verifier)
            verification.append(result.to_dict())
            if result.resolved:
                final_model = model
                final_result = result

        resolved = bool(final_result.resolved) if final_result else False
        apply_ok = bool(final_result.apply_ok) if final_result else False
        rows.append(
            {
                "task_id": tid,
                "chosen_model": final_model,
                "chain_run": run,
                "resolved": resolved,
                "apply_ok": apply_ok,
                "cost_usd": round(total_cost, 6),
                "escalated": escalated,
                "n_steps": len(run),
                "applied_in_cheap": cheap_apply_count,
                "verification": verification,
            }
        )
    return rows


def run_ood_sandbox(
    matrix_path: Path,
    predictions_root: Path,
    output_dir: Path,
    verifier,
    k: int = 2,
    limit: int | None = None,
) -> dict:
    data = OODData(matrix_path)
    patches = PatchStore(predictions_root)
    decisions = verify_and_escalate_with_sandbox(data, patches, verifier, k=k, limit=limit)
    metrics = score_ood(data, decisions)
    metrics["verifier_mode"] = verifier.__class__.__name__
    metrics["decision_source"] = "sandbox_verifier"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "ood_sandbox_decisions.jsonl", decisions)
    write_json(output_dir / "ood_sandbox_metrics.json", metrics)
    write_jsonl(output_dir / "ood_decisions.jsonl", decisions)
    write_json(output_dir / "ood_metrics.json", metrics)
    return {"metrics": metrics, "decisions": decisions}
