from __future__ import annotations

import json
import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eval.run_static import (
    _normalize_diagnosis_topk,
    _normalize_slot_predictions,
    run_static,
)


class _FakeStaticAdapter:
    def complete(self, messages, temperature: float = 0.0) -> str:
        prompt = messages[-1]["content"]
        if "抽取结构化 slot" in prompt:
            return (
                '{"slot_predictions":{"intrusive_thoughts":true,'
                '"ritual_behavior_present":true,"not_a_slot":"ignore"}}'
            )
        return '{"diagnosis_topk":[{"label":"OCD","confidence":0.72},{"label":"OTHER","confidence":0.28}]}'


class StaticRunnerTests(unittest.TestCase):
    def test_normalize_slot_predictions_filters_unknown_slots(self) -> None:
        value = _normalize_slot_predictions(
            {"slot_predictions": {"intrusive_thoughts": True, "bad_slot": True}},
            {"intrusive_thoughts", "ritual_behavior_present"},
        )
        self.assertEqual(value, {"intrusive_thoughts": True})

    def test_normalize_diagnosis_topk_filters_invalid_and_dedupes(self) -> None:
        value = _normalize_diagnosis_topk(
            {
                "diagnosis_topk": [
                    {"label": "OCD", "confidence": 0.7},
                    {"label": "OCD", "confidence": 0.2},
                    {"label": "NOT_A_LABEL", "confidence": 0.1},
                    "OTHER",
                ]
            },
            {"OCD", "OTHER"},
        )
        self.assertEqual(value, ["OCD", "OTHER"])

    def test_run_static_llm_mode_uses_adapter_pipeline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        ontology_dir = repo_root / "ontology"

        case_record = {
            "case_id": "PIB_TEST_STATIC_0001",
            "dsm_module": "OCRD",
            "label": "OCD",
            "label_subtype": None,
            "ambiguity": "unambiguous",
            "patient_profile": {"age_band": "18-25", "gender": "F", "context": "college"},
            "info_variants": {
                "minimal_cc": "总是反复担心脏。",
                "self_report": "我有不想要的念头，总想洗手，影响学习。",
                "chart_full": "患者报告侵入性念头和反复洗手。",
            },
            "slot_truth": {
                "intrusive_thoughts": {
                    "value": True,
                    "certainty": "high",
                    "source": "interview",
                    "evidence": ["总有不想要的念头。"],
                },
                "ritual_behavior_present": {
                    "value": True,
                    "certainty": "high",
                    "source": "interview",
                    "evidence": ["会反复洗手。"],
                },
            },
            "gold_ddx_top5": ["OCD", "OCPD", "BDD", "SSD", "OTHER"],
            "risk_flags": {"suicide": False, "violence": False, "psychosis": False, "substance": False},
            "required_svcl_domains": ["cog_emotion_process", "symptom_profile"],
            "patient_script": {
                "intrusive_thoughts": ["总有不想要的念头。"],
                "ritual_behavior_present": ["会反复洗手。"],
                "unknown_default": ["不太确定。"],
            },
        }
        rubric_record = {
            "case_id": "PIB_TEST_STATIC_0001",
            "must_ask_slots": ["intrusive_thoughts", "ritual_behavior_present"],
            "must_ask_svcl_domains": ["cog_emotion_process", "symptom_profile"],
            "avoid_harm_rules": ["no_overconfident_dx"],
            "stop_rules": {"max_turns": 12},
        }

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cases_path = td_path / "cases.jsonl"
            rubrics_path = td_path / "rubrics.jsonl"
            output_path = td_path / "static.jsonl"
            summary_path = td_path / "summary_static.csv"
            stage_breakdown_path = td_path / "static_stage_breakdown.csv"
            stage_breakdown_tex_path = td_path / "tables_static_stage.tex"
            metrics_path = td_path / "metrics.json"
            splits_dir = td_path / "splits"
            splits_dir.mkdir()
            (splits_dir / "test_ids.txt").write_text("PIB_TEST_STATIC_0001\n", encoding="utf-8")
            cases_path.write_text(json.dumps(case_record, ensure_ascii=False) + "\n", encoding="utf-8")
            rubrics_path.write_text(json.dumps(rubric_record, ensure_ascii=False) + "\n", encoding="utf-8")

            with mock.patch("eval.run_static.build_chat_adapter", return_value=_FakeStaticAdapter()):
                run_static(
                    cases_path=cases_path,
                    rubrics_path=rubrics_path,
                    ontology_dir=ontology_dir,
                    output_path=output_path,
                    mode="llm",
                    provider="openai",
                    use_cache=False,
                    split="test",
                    splits_dir=splits_dir,
                    summary_csv=summary_path,
                    table_tex=td_path / "tables_static.tex",
                    stage_breakdown_csv=stage_breakdown_path,
                    stage_breakdown_tex=stage_breakdown_tex_path,
                    metrics_json=metrics_path,
                )

            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
            with summary_path.open("r", encoding="utf-8", newline="") as f:
                summary_rows = list(csv.DictReader(f))
            with stage_breakdown_path.open("r", encoding="utf-8", newline="") as f:
                stage_breakdown_rows = list(csv.DictReader(f))
            stage_breakdown_tex = stage_breakdown_tex_path.read_text(encoding="utf-8")
            artifact_predictions_exists = Path(metrics_payload["artifacts"]["predictions_jsonl"]).exists()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slot_predictions"]["intrusive_thoughts"], True)
        self.assertEqual(rows[0]["slot_predictions"]["ritual_behavior_present"], True)
        self.assertEqual(rows[0]["split"], "test")
        self.assertNotIn("not_a_slot", rows[0]["slot_predictions"])
        self.assertEqual(rows[0]["diagnosis_topk"][0], "OCD")
        self.assertFalse(rows[0]["slot_parse_error"])
        self.assertFalse(rows[0]["ddx_parse_error"])
        self.assertEqual(rows[0]["metrics"]["slot_stage_error_rate"], 0.0)
        self.assertEqual(rows[0]["metrics"]["ddx_stage_error_rate"], 0.0)
        self.assertEqual(rows[0]["metrics"]["slot_stage_success_rate"], 1.0)
        self.assertEqual(rows[0]["metrics"]["ddx_stage_success_rate"], 1.0)
        overall = next(row for row in summary_rows if row["slice"] == "overall" and row["slice_value"] == "all")
        self.assertIn("slot_stage_error_rate", overall)
        self.assertIn("ddx_stage_error_rate", overall)
        self.assertEqual(float(overall["slot_stage_error_rate"]), 0.0)
        self.assertEqual(float(overall["ddx_stage_error_rate"]), 0.0)
        input_variant_row = next(
            row for row in stage_breakdown_rows if row["slice"] == "input_variant" and row["slice_value"] == "self_report"
        )
        mode_row = next(row for row in stage_breakdown_rows if row["slice"] == "mode" and row["slice_value"] == "llm")
        self.assertEqual(float(input_variant_row["slot_stage_success_rate"]), 1.0)
        self.assertEqual(float(mode_row["ddx_stage_success_rate"]), 1.0)
        self.assertIn("\\begin{tabular}", stage_breakdown_tex)
        self.assertIn("slot_stage_error_rate", stage_breakdown_tex)
        self.assertEqual(metrics_payload["task"], "static")
        self.assertEqual(metrics_payload["n_cases"], 1)
        self.assertEqual(metrics_payload["run_config"]["split"], "test")
        self.assertTrue(artifact_predictions_exists)
