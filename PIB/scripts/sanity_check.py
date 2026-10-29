from __future__ import annotations

from pathlib import Path

from agents.doctor_agent import DoctorState, DummyDoctorAgent
from agents.patient_agent import PatientAgent
from eval.load import load_cases, load_ontology, load_rubrics
from eval.scorers.dynamic_metrics import score_dynamic_case


def main() -> None:
    ontology = load_ontology(Path("ontology"))
    assert not any(slot_id.startswith("aux_slot_") for slot_id in ontology.slot_ids)
    cases = load_cases(Path("data/cases.jsonl"), ontology)
    rubrics = load_rubrics(Path("data/rubrics.jsonl"), ontology, [c.case_id for c in cases])
    rubric_map = {r.case_id: r for r in rubrics}

    patient = PatientAgent(default_seed=1234)
    doctor = DummyDoctorAgent(seed=1234)
    allowed_slots = sorted(ontology.slot_ids)

    subset = cases[:3]
    for case in subset:
        rubric = rubric_map[case.case_id]
        state = DoctorState()
        final_output = None
        for turn in range(1, min(6, rubric.stop_rules.max_turns, ontology.dynamic_max_turns_cap) + 1):
            state.turn = turn
            action = doctor.next_action(
                minimal_cc=case.info_variants.minimal_cc,
                state=state,
                allowed_slots=allowed_slots,
                must_ask_slots=rubric.must_ask_slots,
            )
            if action.get("action") == "ASK":
                reply = patient.answer(case, action["slot_id"], seed=1234, turn=turn)
                state.asked_slots.append(reply.slot_id)
                state.observations[reply.slot_id] = reply.value
            else:
                final_output = action.get("final_output", {})
                break

        if final_output is None:
            final_output = {
                "diagnosis_topk": [{"label": "OTHER", "confidence": 1.0}],
                "slot_predictions": state.observations,
                "risk_flags": {
                    "suicide": False,
                    "violence": False,
                    "psychosis": False,
                    "substance": False,
                },
                "justification": [{"claim": "sanity fallback", "support_slots": []}],
                "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                "calibration": {"uncertainty_statement": "信息有限。"},
            }

        metrics = score_dynamic_case(
            asked_slots=state.asked_slots,
            must_ask_slots=rubric.must_ask_slots,
            required_svcl_domains=rubric.must_ask_svcl_domains,
            svcl_map=ontology.svcl_map,
            final_output=final_output,
            gold_label=case.label,
            gold_ddx_top5=case.gold_ddx_top5,
            ambiguity=case.ambiguity,
        )

        print(case.case_id, metrics)


if __name__ == "__main__":
    main()
