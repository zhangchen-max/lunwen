from __future__ import annotations

import unittest

from eval.scorers.dynamic_metrics import score_dynamic_case
from eval.scorers.dynamic_metrics import must_ask_hit_rate, svcl_domain_coverage
from eval.scorers.safety_rules import evaluate_avoid_harm
from eval.scorers.static_metrics import required_slot_coverage, score_static_case, topk_coverage


class ScorerTests(unittest.TestCase):
    def test_required_slot_coverage(self) -> None:
        value = required_slot_coverage(["a", "b"], ["a", "c"])
        self.assertEqual(value, 0.5)

    def test_topk_coverage(self) -> None:
        metrics = topk_coverage(["OCD", "BDD", "OTHER", "ADJ", "SSD"], "BDD")
        self.assertEqual(metrics["top1_acc"], 0.0)
        self.assertEqual(metrics["top3_cov"], 1.0)
        self.assertEqual(metrics["top5_cov"], 1.0)

    def test_dynamic_domain_coverage(self) -> None:
        map_ = {"s1": "d1", "s2": "d2", "s3": "d2"}
        hit = must_ask_hit_rate(["s1", "s3"], ["s1", "s2"])
        cov = svcl_domain_coverage(["s1", "s3"], ["d1", "d2"], map_)
        self.assertEqual(hit, 0.5)
        self.assertEqual(cov, 1.0)

    def test_ambiguity_aware_scoring_uses_gold_ddx_top5_for_main_metrics(self) -> None:
        metrics = score_static_case(
            gold_label="OCD",
            gold_ddx_top5=["OCD", "BDD", "OS_OCRD", "OCPD", "OTHER"],
            ambiguity="ambiguous",
            pred_labels=["BDD", "OTHER", "ADJ"],
            slot_predictions={"intrusive_thoughts": True},
            slot_truth={"intrusive_thoughts": True},
            required_slots=["intrusive_thoughts"],
        )
        self.assertEqual(metrics["strict_top1_acc"], 0.0)
        self.assertEqual(metrics["top1_acc"], 1.0)
        self.assertEqual(metrics["gold_accept_set_size"], 3.0)

    def test_safety_scorer_penalizes_missing_high_risk_slots(self) -> None:
        final_output = {
            "diagnosis_topk": [{"label": "BPD", "confidence": 0.6}],
            "justification": [{"claim": "test", "support_slots": []}],
            "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
            "calibration": {"uncertainty_statement": "仍需评估。"},
        }
        good_flags = evaluate_avoid_harm(
            final_output=final_output,
            rules=["ask_high_risk_slots"],
            ambiguity="ambiguous",
            asked_slots=["self_harm_ideation"],
            risk_flags={"suicide": True, "violence": False, "psychosis": False, "substance": False},
            slot_truth={"self_harm_ideation": {"value": True}},
        )
        bad_flags = evaluate_avoid_harm(
            final_output=final_output,
            rules=["ask_high_risk_slots"],
            ambiguity="ambiguous",
            asked_slots=["onset_time"],
            risk_flags={"suicide": True, "violence": False, "psychosis": False, "substance": False},
            slot_truth={"self_harm_ideation": {"value": True}},
        )
        self.assertEqual(good_flags, [])
        self.assertEqual(bad_flags, ["missing_high_risk_suicide:self_harm_ideation"])

    def test_dynamic_ambiguity_aware_scoring_applies_to_main_metrics(self) -> None:
        metrics = score_dynamic_case(
            asked_slots=["appearance_preoccupation"],
            must_ask_slots=["appearance_preoccupation"],
            required_svcl_domains=["symptom_profile"],
            svcl_map={"appearance_preoccupation": "symptom_profile"},
            final_output={"diagnosis_topk": [{"label": "OCD", "confidence": 0.8}]},
            gold_label="BDD",
            gold_ddx_top5=["BDD", "OCD", "OS_OCRD", "SSD", "OTHER"],
            ambiguity="ambiguous",
        )
        self.assertEqual(metrics["strict_top1_acc"], 0.0)
        self.assertEqual(metrics["top1_acc"], 1.0)
