from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from eval.load import load_cases, load_ontology, load_rubrics, write_jsonl
from scripts.build_cases import build_records_from_csv


class BuildCasesTests(unittest.TestCase):
    def test_template_compiles_and_validates(self) -> None:
        template = Path("authoring/cases_template.csv")
        ontology = load_ontology(Path("ontology"))
        cases, rubrics = build_records_from_csv(template)

        self.assertGreaterEqual(len(cases), 1)
        self.assertEqual(len(cases), len(rubrics))

        with tempfile.TemporaryDirectory() as td:
            cases_path = Path(td) / "cases.jsonl"
            rubrics_path = Path(td) / "rubrics.jsonl"
            write_jsonl(cases_path, cases)
            write_jsonl(rubrics_path, rubrics)

            loaded_cases = load_cases(cases_path, ontology)
            loaded_rubrics = load_rubrics(rubrics_path, ontology, [case.case_id for case in loaded_cases])

        self.assertEqual(len(loaded_cases), len(cases))
        self.assertEqual(len(loaded_rubrics), len(rubrics))
