from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

from agents.doctor_agent import DoctorState, DummyDoctorAgent
from eval.load import load_ontology
from eval.run_dynamic import run_dynamic
from eval.run_static import heuristic_ddx_context, heuristic_slot_context


FORBIDDEN_FIELDS = [
    "case.label",
    "gold_ddx_top5",
    "rubrics.must_ask_slots",
    "slot_truth",
    "risk_flags",
]


def _latest_run_dir(output_jsonl: Path) -> Path:
    artifact_root = output_jsonl.with_suffix("")
    runs = sorted(artifact_root.glob("run_*"))
    if not runs:
        raise SystemExit(f"No artifact runs found under {artifact_root}")
    return runs[-1]


def _label_breakdown(metrics_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    by_label = payload["summary"]["by_slice"].get("label", {})
    rows = []
    for label, metrics in sorted(by_label.items()):
        rows.append(
            {
                "label": label,
                "n": metrics.get("n"),
                "must_ask_hit_rate": metrics.get("must_ask_hit_rate"),
                "turns": metrics.get("turns"),
                "harm_flags_count": metrics.get("harm_flags_count"),
            }
        )
    return rows


class _CapturingDummyDoctor(DummyDoctorAgent):
    def __init__(self) -> None:
        super().__init__(seed=1234, max_asks_before_final=0)
        self.allowed_slots_snapshots: list[dict[str, Any]] = []

    def next_action(self, minimal_cc, state, allowed_slots, must_ask_slots=None):
        self.allowed_slots_snapshots.append(
            {
                "turn": state.turn,
                "allowed_slots": list(allowed_slots),
                "must_ask_slots": None if must_ask_slots is None else list(must_ask_slots),
            }
        )
        return {
            "action": "FINAL",
            "final_output": {
                "diagnosis_topk": [{"label": "OTHER", "confidence": 1.0}],
                "slot_predictions": dict(state.observations),
                "risk_flags": {
                    "suicide": False,
                    "violence": False,
                    "psychosis": False,
                    "substance": False,
                },
                "justification": [{"claim": "审计 allowed_slots。", "support_slots": []}],
                "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                "calibration": {"uncertainty_statement": "审计路径。"},
            },
        }


def _audit_allowed_slots(
    cases_path: Path,
    rubrics_path: Path,
    ontology_dir: Path,
    splits_dir: Path,
) -> dict[str, Any]:
    ontology = load_ontology(ontology_dir)
    expected = sorted(ontology.slot_ids)
    capturing_dummy = _CapturingDummyDoctor()
    with tempfile.TemporaryDirectory() as td:
        output_path = Path(td) / "allowed_slots_audit.jsonl"
        with mock.patch("eval.run_dynamic._build_doctor", return_value=capturing_dummy):
            run_dynamic(
                cases_path=cases_path,
                rubrics_path=rubrics_path,
                ontology_dir=ontology_dir,
                output_path=output_path,
                doctor_kind="dummy",
                split="test",
                splits_dir=splits_dir,
            )
    unique_lengths = sorted({len(item["allowed_slots"]) for item in capturing_dummy.allowed_slots_snapshots})
    unique_match_flags = sorted(
        {item["allowed_slots"] == expected for item in capturing_dummy.allowed_slots_snapshots}
    )
    return {
        "expected_slot_count": len(expected),
        "captured_slot_count_set": unique_lengths,
        "captured_contexts": len(capturing_dummy.allowed_slots_snapshots),
        "matches_global_ontology_for_all_contexts": all(unique_match_flags),
        "case_specific_cropping_detected": not all(unique_match_flags),
        "sample_slots": expected[:10],
        "non_case_specific_example_slots": [
            slot_id for slot_id in ["anger_outbursts", "transient_paranoia_stress_related", "substance_misuse"] if slot_id in expected
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit no-oracle baseline visibility and per-label metrics")
    parser.add_argument("--cases", type=Path, default=Path("data/cases.jsonl"))
    parser.add_argument("--rubrics", type=Path, default=Path("data/rubrics.jsonl"))
    parser.add_argument("--ontology", type=Path, default=Path("ontology"))
    parser.add_argument("--splits-dir", type=Path, default=Path("data/splits"))
    parser.add_argument("--static-output", type=Path, default=Path("results/static/test_static.jsonl"))
    parser.add_argument("--dynamic-output", type=Path, default=Path("results/dynamic/test_dynamic.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("results/audit/no_oracle_baselines.json"))
    args = parser.parse_args()

    dummy = DummyDoctorAgent(seed=1234)
    static_slot_context = heuristic_slot_context("示例主诉")
    static_ddx_context = heuristic_ddx_context({"intrusive_thoughts": True})
    dynamic_context = dummy.visible_input_context(
        minimal_cc="示例主诉",
        state=DoctorState(),
        allowed_slots=["onset_time", "intrusive_thoughts", "ritual_behavior_present"],
    )

    static_run = _latest_run_dir(args.static_output)
    dynamic_run = _latest_run_dir(args.dynamic_output)

    payload = {
        "forbidden_fields": FORBIDDEN_FIELDS,
        "static_heuristic_visible_inputs": {
            "slot_stage_fields": sorted(static_slot_context.keys()),
            "ddx_stage_fields": sorted(static_ddx_context.keys()),
        },
        "dynamic_dummy_visible_inputs": {
            "fields": sorted(dynamic_context.keys()),
            "state_fields": sorted(dynamic_context["state"].keys()),
        },
        "allowed_slots_audit": _audit_allowed_slots(
            cases_path=args.cases,
            rubrics_path=args.rubrics,
            ontology_dir=args.ontology,
            splits_dir=args.splits_dir,
        ),
        "static_heuristic_test_split_per_label": _label_breakdown(static_run / "metrics.json"),
        "dynamic_dummy_test_split_per_label": _label_breakdown(dynamic_run / "metrics.json"),
        "historical_explanation": (
            "Earlier dummy baseline implementations reached must_ask_hit_rate=1.0 because the runner passed "
            "rubric.must_ask_slots into DummyDoctorAgent and the agent asked those slots first. "
            "The current no-oracle path removes that input; any remaining performance is attributable to the "
            "dummy's fixed complaint-to-slot heuristic and the template regularity of the synthetic casebank."
        ),
        "artifact_paths": {
            "static_metrics_json": str(static_run / "metrics.json"),
            "dynamic_metrics_json": str(dynamic_run / "metrics.json"),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"No-oracle audit written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
