from __future__ import annotations

import unittest
from pathlib import Path

from eval.load import load_cases, load_ontology
from scripts.text_contamination_scan import scan_cases


class TextContaminationTests(unittest.TestCase):
    def test_current_casebank_has_no_direct_gold_label_contamination(self) -> None:
        ontology = load_ontology(Path("ontology"))
        cases = load_cases(Path("data/cases.jsonl"), ontology)
        findings = scan_cases(cases, ontology.labels)
        self.assertEqual(findings, [])
