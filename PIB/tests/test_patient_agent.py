from __future__ import annotations

import unittest
from pathlib import Path

from agents.patient_agent import PatientAgent
from eval.load import load_cases, load_ontology


class PatientAgentTests(unittest.TestCase):
    def test_patient_agent_deterministic_reply(self) -> None:
        ontology = load_ontology(Path("ontology"))
        cases = load_cases(Path("data/cases.jsonl"), ontology)
        case = cases[0]

        agent = PatientAgent(default_seed=1234)
        r1 = agent.answer(case, "onset_time", seed=1234, turn=1)
        r2 = agent.answer(case, "onset_time", seed=1234, turn=1)

        self.assertEqual(r1.utterance, r2.utterance)
        self.assertEqual(r1.value, r2.value)
