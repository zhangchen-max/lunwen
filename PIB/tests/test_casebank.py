from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from eval.load import audit_high_risk_rubric_coverage, load_cases, load_ontology, load_rubrics


class CasebankTests(unittest.TestCase):
    def test_casebank_has_pilot_scale_distribution(self) -> None:
        ontology = load_ontology(Path("ontology"))
        cases = load_cases(Path("data/cases.jsonl"), ontology)

        self.assertGreaterEqual(len(cases), 100)

        label_counts = Counter(case.label for case in cases)
        for label, count in label_counts.items():
            self.assertGreaterEqual(count, 10, msg=f"{label} has only {count} cases")

        ambiguity_ratio = sum(case.ambiguity == "ambiguous" for case in cases) / len(cases)
        self.assertGreaterEqual(ambiguity_ratio, 0.30)
        self.assertLessEqual(ambiguity_ratio, 0.45)

    def test_os_ocrd_subtypes_are_all_present(self) -> None:
        ontology = load_ontology(Path("ontology"))
        cases = load_cases(Path("data/cases.jsonl"), ontology)
        subtypes = {
            case.label_subtype
            for case in cases
            if case.label == "OS_OCRD" and case.label_subtype is not None
        }
        self.assertEqual(subtypes, set(ontology.os_ocrd_subtypes))

    def test_high_risk_cases_have_risk_slots_in_must_ask(self) -> None:
        ontology = load_ontology(Path("ontology"))
        cases = load_cases(Path("data/cases.jsonl"), ontology)
        rubrics = load_rubrics(Path("data/rubrics.jsonl"), ontology, [case.case_id for case in cases])
        findings = audit_high_risk_rubric_coverage(cases, rubrics)
        self.assertEqual(findings, [])

    def test_psychosis_and_substance_positive_samples_exist(self) -> None:
        ontology = load_ontology(Path("ontology"))
        cases = load_cases(Path("data/cases.jsonl"), ontology)
        psychosis_positive = sum(case.risk_flags.psychosis for case in cases)
        substance_positive = sum(case.risk_flags.substance for case in cases)
        self.assertGreaterEqual(psychosis_positive, 2)
        self.assertGreaterEqual(substance_positive, 2)
