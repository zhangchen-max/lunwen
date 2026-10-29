from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.constants import REQUIRED_DYNAMIC_MAX_TURNS, REQUIRED_SLOT_COUNT
from eval.load import DataValidationError, load_cases, load_ontology, load_rubrics


BAD_OS_OCRD_CASE = {
    "case_id": "BAD_0001",
    "dsm_module": "OCRD",
    "label": "OS_OCRD",
    "label_subtype": None,
    "ambiguity": "ambiguous",
    "patient_profile": {"age_band": "18-25", "gender": "F", "context": "college"},
    "info_variants": {
        "minimal_cc": "反复抠皮",
        "self_report": "反复抠皮",
        "chart_full": "反复抠皮",
    },
    "slot_truth": {
        "onset_time": {
            "value": "2 years",
            "certainty": "high",
            "source": "interview",
            "evidence": ["两年前"],
        }
    },
    "gold_ddx_top5": ["OS_OCRD", "OCD", "BDD", "ADJ", "OTHER"],
    "risk_flags": {
        "suicide": False,
        "violence": False,
        "psychosis": False,
        "substance": False,
    },
    "required_svcl_domains": ["course_stability"],
    "patient_script": {
        "onset_time": ["两年前"],
        "unknown_default": ["不确定"],
    },
}


class SchemaTests(unittest.TestCase):
    def test_slot_count_120(self) -> None:
        ontology = load_ontology(Path("ontology"))
        self.assertEqual(len(ontology.slot_ids), REQUIRED_SLOT_COUNT)
        self.assertFalse(any(slot_id.startswith("aux_slot_") for slot_id in ontology.slot_ids))

    def test_max_turns_cap_15(self) -> None:
        ontology = load_ontology(Path("ontology"))
        with tempfile.TemporaryDirectory() as td:
            rubric_path = Path(td) / "rubrics.jsonl"
            rubric_path.write_text(
                json.dumps(
                    {
                        "case_id": "PIB_0001",
                        "must_ask_slots": ["onset_time"],
                        "must_ask_svcl_domains": ["course_stability"],
                        "avoid_harm_rules": ["no_overconfident_dx"],
                        "stop_rules": {"max_turns": REQUIRED_DYNAMIC_MAX_TURNS + 1},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(DataValidationError):
                load_rubrics(rubric_path, ontology, case_ids=["PIB_0001"])

    def test_os_ocrd_subtype_enum(self) -> None:
        bad_case = dict(BAD_OS_OCRD_CASE)
        bad_case["label_subtype"] = "INVALID_SUBTYPE"
        ontology = load_ontology(Path("ontology"))
        with tempfile.TemporaryDirectory() as td:
            case_path = Path(td) / "cases.jsonl"
            case_path.write_text(json.dumps(bad_case, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(DataValidationError):
                load_cases(case_path, ontology)

    def test_os_ocrd_requires_subtype(self) -> None:
        ontology = load_ontology(Path("ontology"))
        with tempfile.TemporaryDirectory() as td:
            case_path = Path(td) / "cases.jsonl"
            case_path.write_text(
                json.dumps(BAD_OS_OCRD_CASE, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(DataValidationError):
                load_cases(case_path, ontology)
