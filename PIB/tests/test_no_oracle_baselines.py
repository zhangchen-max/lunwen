from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents.doctor_agent import DoctorState, DummyDoctorAgent
from eval.load import load_ontology
from eval.run_dynamic import run_dynamic
from eval.run_static import heuristic_ddx_context, heuristic_slot_context, run_static


FORBIDDEN_FIELDS = {
    "case.label",
    "gold_ddx_top5",
    "rubrics.must_ask_slots",
    "slot_truth",
    "risk_flags",
}


def _temp_case() -> dict:
    return {
        "case_id": "PIB_TEST_NO_ORACLE_0001",
        "dsm_module": "OCRD",
        "label": "OCD",
        "label_subtype": None,
        "ambiguity": "ambiguous",
        "patient_profile": {"age_band": "18-25", "gender": "F", "context": "college"},
        "info_variants": {
            "minimal_cc": "我总是担心手很脏。",
            "self_report": "我有反复的念头，总想洗手。",
            "chart_full": "反复洗手和侵入性念头明显。",
        },
        "slot_truth": {
            "intrusive_thoughts": {
                "value": True,
                "certainty": "high",
                "source": "interview",
                "evidence": ["总冒出不想要的念头。"],
            },
            "ritual_behavior_present": {
                "value": True,
                "certainty": "high",
                "source": "interview",
                "evidence": ["会反复洗手。"],
            },
        },
        "gold_ddx_top5": ["OCD", "BDD", "OS_OCRD", "OCPD", "OTHER"],
        "risk_flags": {"suicide": False, "violence": False, "psychosis": False, "substance": False},
        "required_svcl_domains": ["cog_emotion_process", "symptom_profile"],
        "patient_script": {
            "intrusive_thoughts": ["总冒出不想要的念头。"],
            "ritual_behavior_present": ["会反复洗手。"],
            "unknown_default": ["不太确定。"],
        },
    }


def _temp_rubric() -> dict:
    return {
        "case_id": "PIB_TEST_NO_ORACLE_0001",
        "must_ask_slots": ["intrusive_thoughts", "ritual_behavior_present"],
        "must_ask_svcl_domains": ["cog_emotion_process", "symptom_profile"],
        "avoid_harm_rules": ["no_overconfident_dx", "ask_high_risk_slots"],
        "stop_rules": {"max_turns": 12},
    }


class _CapturingDummyDoctor(DummyDoctorAgent):
    def __init__(self) -> None:
        super().__init__(seed=1234)
        self.contexts = []

    def next_action(self, minimal_cc, state, allowed_slots, must_ask_slots=None):
        context = self.visible_input_context(minimal_cc, state, allowed_slots)
        context["must_ask_slots"] = None if must_ask_slots is None else list(must_ask_slots)
        self.contexts.append(context)
        return {
            "action": "FINAL",
            "final_output": {
                "diagnosis_topk": [{"label": "OTHER", "confidence": 1.0}],
                "slot_predictions": {},
                "risk_flags": {
                    "suicide": False,
                    "violence": False,
                    "psychosis": False,
                    "substance": False,
                },
                "justification": [{"claim": "信息有限。", "support_slots": []}],
                "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                "calibration": {"uncertainty_statement": "仍需评估。"},
            },
        }


class NoOracleBaselineTests(unittest.TestCase):
    def test_static_heuristic_runtime_context_excludes_gold_and_rubric_fields(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        ontology_dir = repo_root / "ontology"
        captured = {}

        def _capture_slot_stage(text: str):
            captured["slot_stage"] = heuristic_slot_context(text)
            return {"intrusive_thoughts": True}

        def _capture_ddx_stage(slot_predictions):
            captured["ddx_stage"] = heuristic_ddx_context(slot_predictions)
            return ["OCD", "OTHER", "BDD", "ADJ", "SSD"]

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cases_path = td_path / "cases.jsonl"
            rubrics_path = td_path / "rubrics.jsonl"
            output_path = td_path / "static.jsonl"
            splits_dir = td_path / "splits"
            splits_dir.mkdir()
            (splits_dir / "test_ids.txt").write_text("PIB_TEST_NO_ORACLE_0001\n", encoding="utf-8")
            cases_path.write_text(json.dumps(_temp_case(), ensure_ascii=False) + "\n", encoding="utf-8")
            rubrics_path.write_text(json.dumps(_temp_rubric(), ensure_ascii=False) + "\n", encoding="utf-8")

            with mock.patch("eval.run_static.heuristic_slot_filling", side_effect=_capture_slot_stage), mock.patch(
                "eval.run_static.heuristic_ddx",
                side_effect=_capture_ddx_stage,
            ):
                run_static(
                    cases_path=cases_path,
                    rubrics_path=rubrics_path,
                    ontology_dir=ontology_dir,
                    output_path=output_path,
                    mode="heuristic",
                    split="test",
                    splits_dir=splits_dir,
                )

        self.assertEqual(set(captured["slot_stage"].keys()), {"text"})
        self.assertEqual(set(captured["ddx_stage"].keys()), {"slot_predictions"})
        for forbidden in FORBIDDEN_FIELDS:
            self.assertNotIn(forbidden, captured["slot_stage"])
            self.assertNotIn(forbidden, captured["ddx_stage"])

    def test_dynamic_dummy_runtime_context_excludes_gold_and_rubric_fields(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        ontology_dir = repo_root / "ontology"
        ontology = load_ontology(ontology_dir)
        capturing_dummy = _CapturingDummyDoctor()

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cases_path = td_path / "cases.jsonl"
            rubrics_path = td_path / "rubrics.jsonl"
            output_path = td_path / "dynamic.jsonl"
            splits_dir = td_path / "splits"
            splits_dir.mkdir()
            (splits_dir / "test_ids.txt").write_text("PIB_TEST_NO_ORACLE_0001\n", encoding="utf-8")
            cases_path.write_text(json.dumps(_temp_case(), ensure_ascii=False) + "\n", encoding="utf-8")
            rubrics_path.write_text(json.dumps(_temp_rubric(), ensure_ascii=False) + "\n", encoding="utf-8")

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

        self.assertGreaterEqual(len(capturing_dummy.contexts), 1)
        context = capturing_dummy.contexts[0]
        self.assertEqual(set(context.keys()), {"minimal_cc", "state", "allowed_slots", "must_ask_slots"})
        self.assertIsNone(context["must_ask_slots"])
        self.assertEqual(
            set(context["state"].keys()),
            {"asked_slots", "observations", "turn"},
        )
        self.assertEqual(context["allowed_slots"], sorted(ontology.slot_ids))
        self.assertGreater(len(context["allowed_slots"]), len(_temp_case()["slot_truth"]))
        self.assertIn("anger_outbursts", context["allowed_slots"])
        for forbidden in FORBIDDEN_FIELDS:
            self.assertNotIn(forbidden, context)
            self.assertNotIn(forbidden, context["state"])
