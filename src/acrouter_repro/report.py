"""Report rendering helpers."""

from __future__ import annotations

from pathlib import Path

from .io_utils import write_json


def render_summary(id_metrics: dict, ood_metrics: dict) -> str:
    if ood_metrics.get("decision_source") == "sandbox_verifier":
        ood_note = (
            "ID uses the configured clean policy shown in the table. OOD uses the k=2 "
            "verify-and-escalate cascade with an explicit sandbox verifier: "
            "MiniMax -> Kimi -> GPT-5.4 -> GLM-5, then Opus only when at "
            "least two cheap attempts produce apply_ok."
        )
    else:
        ood_note = (
            "ID uses the configured clean policy shown in the table. OOD uses the legacy "
            "oracle-matrix replay path for comparison."
        )
    return "\n".join(
        [
            "# ACRouter Unique Release Results",
            "",
            "| split | n | AvgPerf% | CumReg | $Total | Perf/$ | rAcc | extras |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
            (
                f"| ID | {id_metrics['n']} | {id_metrics['AvgPerf%']:.2f} | "
                f"{id_metrics['CumReg']:.1f} | {id_metrics['$Total']:.2f} | "
                f"{id_metrics['Perf/$']:.2f} | {id_metrics['rAcc_perf_oracle']:.4f} | "
                f"missing_score={id_metrics['missing_score']}, "
                f"policy={id_metrics.get('policy', '?')}, "
                f"tune={id_metrics.get('tune_split', '?')}, "
                f"eval={id_metrics.get('eval_split', '?')}, "
                f"leakage={id_metrics.get('leakage_risk', '?')} |"
            ),
            (
                f"| OOD | {ood_metrics['n']} | {ood_metrics['AvgPerf%']:.2f} | "
                f"{ood_metrics['CumReg']:.1f} | {ood_metrics['$Total']:.2f} | "
                f"{ood_metrics['Perf/$']:.2f} | {ood_metrics['rAcc_reward_oracle']:.4f} | "
                f"apply_ok={ood_metrics['Apply_ok%']:.2f}%, "
                f"escalations={ood_metrics['Escalations']}, "
                f"avg_steps={ood_metrics['AvgSteps']:.2f} |"
            ),
            "",
            ood_note,
            "",
        ]
    )


def write_summary(output_dir: Path, id_metrics: dict, ood_metrics: dict) -> str:
    summary = {"id": id_metrics, "ood": ood_metrics}
    write_json(output_dir / "summary.json", summary)
    text = render_summary(id_metrics, ood_metrics)
    (output_dir / "summary.md").write_text(text)
    return text
