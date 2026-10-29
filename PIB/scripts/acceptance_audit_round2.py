from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from eval.load import load_cases, load_ontology, load_rubrics, audit_high_risk_rubric_coverage
from eval.risk import required_high_risk_slots
from eval.run_static import heuristic_ddx, heuristic_slot_filling
from eval.scorers.ddx_metrics import benchmark_gold_labels
from eval.scorers.safety_rules import evaluate_avoid_harm
from eval.scorers.static_metrics import score_static_case


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_runs(base_dir: Path) -> list[Path]:
    runs = sorted(base_dir.glob("run_*"))
    return runs[-2:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate round-2 acceptance audit artifacts")
    parser.add_argument("--ontology", type=Path, default=Path("ontology"))
    parser.add_argument("--cases", type=Path, default=Path("data/cases.jsonl"))
    parser.add_argument("--rubrics", type=Path, default=Path("data/rubrics.jsonl"))
    parser.add_argument("--pre-patch-risk-audit", type=Path, default=Path("results/audit/pre_patch_risk_audit.json"))
    parser.add_argument("--static-output-root", type=Path, default=Path("results/static/test_static"))
    parser.add_argument("--dynamic-output-root", type=Path, default=Path("results/dynamic/test_dynamic"))
    parser.add_argument("--audit-dir", type=Path, default=Path("results/audit"))
    args = parser.parse_args()

    ontology = load_ontology(args.ontology)
    cases = load_cases(args.cases, ontology)
    rubrics = load_rubrics(args.rubrics, ontology, [case.case_id for case in cases])
    case_by_id = {case.case_id: case for case in cases}
    rubric_by_id = {rubric.case_id: rubric for rubric in rubrics}

    pre_patch_rows = json.loads(args.pre_patch_risk_audit.read_text(encoding="utf-8"))
    before_findings = []
    for row in pre_patch_rows:
        case = case_by_id[row["case_id"]]
        required = required_high_risk_slots(row.get("risk_flags", {}), case.slot_truth)
        missing = {
            risk_name: [slot_id for slot_id in slots if slot_id not in row.get("must_ask_slots", [])]
            for risk_name, slots in required.items()
        }
        missing = {risk_name: slots for risk_name, slots in missing.items() if slots}
        if missing:
            before_findings.append(
                {
                    "case_id": row["case_id"],
                    "label": row["label"],
                    "risk_flags": row.get("risk_flags", {}),
                    "before_must_ask_slots": row.get("must_ask_slots", []),
                    "required_risk_slots": required,
                    "missing_risk_slots": missing,
                }
            )

    after_findings = audit_high_risk_rubric_coverage(cases, rubrics)
    affected_case_ids = sorted({finding["case_id"] for finding in before_findings} | {finding["case_id"] for finding in after_findings})
    diff_rows = []
    for case_id in affected_case_ids:
        before = next((row for row in before_findings if row["case_id"] == case_id), None)
        after = next((row for row in after_findings if row["case_id"] == case_id), None)
        current_slots = list(rubric_by_id[case_id].must_ask_slots)
        before_slots = list(before["before_must_ask_slots"]) if before else current_slots
        diff_rows.append(
            {
                "case_id": case_id,
                "label": case_by_id[case_id].label,
                "required_risk_slots": before["required_risk_slots"] if before else after["required_risk_slots"],
                "before_must_ask_slots": before_slots,
                "after_must_ask_slots": current_slots,
                "added_slots": [slot for slot in current_slots if slot not in before_slots],
                "removed_slots": [slot for slot in before_slots if slot not in current_slots],
            }
        )

    high_risk_payload = {
        "suicide_positive_case_ids": sorted(case.case_id for case in cases if case.risk_flags.suicide),
        "violence_positive_case_ids": sorted(case.case_id for case in cases if case.risk_flags.violence),
        "before_missing_case_ids": [finding["case_id"] for finding in before_findings],
        "after_missing_case_ids": [finding["case_id"] for finding in after_findings],
        "before_findings": before_findings,
        "after_findings": after_findings,
        "diff_rows": diff_rows,
    }
    _write_json(args.audit_dir / "high_risk_rubric_before_after.json", high_risk_payload)
    _write_json(args.audit_dir / "post_patch_risk_audit.json", after_findings)

    diff_md = [
        "# High-Risk Rubric Diff",
        "",
        "## Before Missing Case IDs",
        ", ".join(high_risk_payload["before_missing_case_ids"]) or "(none)",
        "",
        "## After Missing Case IDs",
        ", ".join(high_risk_payload["after_missing_case_ids"]) or "(none)",
        "",
        "## Added Must-Ask Slots",
    ]
    diff_md.extend(
        f"- {row['case_id']} ({row['label']}): + {', '.join(row['added_slots']) if row['added_slots'] else '(none)'}"
        for row in diff_rows
    )
    (args.audit_dir / "high_risk_rubric_patch_diff.md").write_text("\n".join(diff_md) + "\n", encoding="utf-8")

    ambiguous_example = None
    for case in cases:
        if case.ambiguity != "ambiguous":
            continue
        slot_predictions = heuristic_slot_filling(case.info_variants.self_report)
        pred_labels = heuristic_ddx(slot_predictions)
        metrics = score_static_case(
            gold_label=case.label,
            gold_ddx_top5=case.gold_ddx_top5,
            ambiguity=case.ambiguity,
            pred_labels=pred_labels,
            slot_predictions=slot_predictions,
            slot_truth={slot_id: payload.value for slot_id, payload in case.slot_truth.items()},
            required_slots=rubric_by_id[case.case_id].must_ask_slots,
        )
        if metrics["top3_cov"] != metrics["strict_top3_cov"] or metrics["top5_cov"] != metrics["strict_top5_cov"]:
            ambiguous_example = {
                "case_id": case.case_id,
                "label": case.label,
                "ambiguity": case.ambiguity,
                "pred_labels": pred_labels,
                "gold_label": case.label,
                "gold_ddx_top5": case.gold_ddx_top5,
                "accepted_gold_labels": benchmark_gold_labels(case.label, case.gold_ddx_top5, case.ambiguity),
                "before_strict_metrics": {
                    "top1_acc": metrics["strict_top1_acc"],
                    "top3_cov": metrics["strict_top3_cov"],
                    "top5_cov": metrics["strict_top5_cov"],
                },
                "after_benchmark_metrics": {
                    "top1_acc": metrics["top1_acc"],
                    "top3_cov": metrics["top3_cov"],
                    "top5_cov": metrics["top5_cov"],
                    "gold_accept_set_size": metrics["gold_accept_set_size"],
                },
            }
            break
    _write_json(args.audit_dir / "ambiguity_scoring_example.json", ambiguous_example)

    risk_case = case_by_id["PIB_0041"]
    required = required_high_risk_slots(risk_case.risk_flags.model_dump(), risk_case.slot_truth)
    good_asked = list(rubric_by_id[risk_case.case_id].must_ask_slots)
    required_slots = {slot for slots in required.values() for slot in slots}
    bad_asked = [slot for slot in good_asked if slot not in required_slots]
    final_output = {
        "diagnosis_topk": [{"label": risk_case.label, "confidence": 0.7}],
        "slot_predictions": {},
        "risk_flags": risk_case.risk_flags.model_dump(),
        "justification": [{"claim": "需进一步评估风险。", "support_slots": []}],
        "next_steps": [{"type": "suggest_assessment", "text": "建议进一步面谈和风险评估。"}],
        "calibration": {"uncertainty_statement": "仍需进一步评估。"},
    }
    good_flags = evaluate_avoid_harm(
        final_output=final_output,
        rules=rubric_by_id[risk_case.case_id].avoid_harm_rules,
        ambiguity=risk_case.ambiguity,
        asked_slots=good_asked,
        risk_flags=risk_case.risk_flags.model_dump(),
        slot_truth=risk_case.slot_truth,
    )
    bad_flags = evaluate_avoid_harm(
        final_output=final_output,
        rules=rubric_by_id[risk_case.case_id].avoid_harm_rules,
        ambiguity=risk_case.ambiguity,
        asked_slots=bad_asked,
        risk_flags=risk_case.risk_flags.model_dump(),
        slot_truth=risk_case.slot_truth,
    )
    _write_json(
        args.audit_dir / "safety_high_risk_comparison.json",
        {
            "case_id": risk_case.case_id,
            "required_risk_slots": required,
            "good_case": {
                "asked_slots": good_asked,
                "harm_flags": good_flags,
                "harm_flags_count": len(good_flags),
            },
            "bad_case": {
                "asked_slots": bad_asked,
                "harm_flags": bad_flags,
                "harm_flags_count": len(bad_flags),
            },
        },
    )

    static_runs = _latest_runs(args.static_output_root)
    dynamic_runs = _latest_runs(args.dynamic_output_root)
    _write_json(
        args.audit_dir / "artifact_isolation.json",
        {
            "static_runs": [
                {
                    "run_dir": str(run_dir),
                    "predictions_jsonl": str(run_dir / "predictions.jsonl"),
                    "summary_csv": str(run_dir / "summary.csv"),
                    "metrics_json": str(run_dir / "metrics.json"),
                    "predictions_sha256": _sha256(run_dir / "predictions.jsonl"),
                    "summary_sha256": _sha256(run_dir / "summary.csv"),
                    "metrics_sha256": _sha256(run_dir / "metrics.json"),
                }
                for run_dir in static_runs
            ],
            "dynamic_runs": [
                {
                    "run_dir": str(run_dir),
                    "predictions_jsonl": str(run_dir / "predictions.jsonl"),
                    "summary_csv": str(run_dir / "summary.csv"),
                    "metrics_json": str(run_dir / "metrics.json"),
                    "predictions_sha256": _sha256(run_dir / "predictions.jsonl"),
                    "summary_sha256": _sha256(run_dir / "summary.csv"),
                    "metrics_sha256": _sha256(run_dir / "metrics.json"),
                }
                for run_dir in dynamic_runs
            ],
        },
    )

    latest_static_metrics = json.loads((static_runs[-1] / "metrics.json").read_text(encoding="utf-8"))
    latest_dynamic_metrics = json.loads((dynamic_runs[-1] / "metrics.json").read_text(encoding="utf-8"))
    _write_json(
        args.audit_dir / "summary_metric_samples.json",
        {
            "static_overall": latest_static_metrics["summary"]["overall"],
            "static_ambiguity_ambiguous": latest_static_metrics["summary"]["by_slice"]["ambiguity"]["ambiguous"],
            "dynamic_overall": latest_dynamic_metrics["summary"]["overall"],
            "dynamic_ambiguity_ambiguous": latest_dynamic_metrics["summary"]["by_slice"]["ambiguity"]["ambiguous"],
        },
    )

    for output_path in [Path("results/static/test_static.jsonl"), Path("results/dynamic/test_dynamic.jsonl")]:
        rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        _write_json(
            args.audit_dir / f"{output_path.stem}_split_audit.json",
            {
                "path": str(output_path),
                "n_rows": len(rows),
                "split_values": sorted({row.get("split") for row in rows}),
            },
        )

    print(f"Acceptance audit written to {args.audit_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
