from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eval.run_dynamic import _validate_final_output, run_dynamic


class DynamicRunnerTests(unittest.TestCase):
    def _make_case(self, case_id: str, label: str = "OCD", minimal_cc: str | None = None) -> dict:
        cc = minimal_cc or f"{case_id} 主诉"
        gold_top5 = ["OCD", "BDD", "OS_OCRD", "OCPD", "OTHER"]
        if label == "BDD":
            gold_top5 = ["BDD", "OCD", "OS_OCRD", "SSD", "OTHER"]
        return {
            "case_id": case_id,
            "dsm_module": "OCRD",
            "label": label,
            "label_subtype": None,
            "ambiguity": "unambiguous",
            "patient_profile": {"age_band": "18-25", "gender": "F", "context": "college"},
            "info_variants": {
                "minimal_cc": cc,
                "self_report": f"{cc} self report",
                "chart_full": f"{cc} chart full",
            },
            "slot_truth": {
                "onset_time": {
                    "value": "3 months",
                    "certainty": "high",
                    "source": "interview",
                    "evidence": ["三个月前开始。"],
                },
                "intrusive_thoughts": {
                    "value": True,
                    "certainty": "high",
                    "source": "interview",
                    "evidence": ["脑子里总冒出不想要的念头。"],
                },
            },
            "gold_ddx_top5": gold_top5,
            "risk_flags": {"suicide": False, "violence": False, "psychosis": False, "substance": False},
            "required_svcl_domains": ["course_stability", "cog_emotion_process"],
            "patient_script": {
                "onset_time": ["三个月前开始。"],
                "intrusive_thoughts": ["脑子里总冒出不想要的念头。"],
                "unknown_default": ["不太确定。"],
            },
        }

    def _make_rubric(self, case_id: str) -> dict:
        return {
            "case_id": case_id,
            "must_ask_slots": ["onset_time", "intrusive_thoughts"],
            "must_ask_svcl_domains": ["course_stability", "cog_emotion_process"],
            "avoid_harm_rules": ["no_overconfident_dx"],
            "stop_rules": {"max_turns": 12},
        }

    def _existing_row(self, case: dict, *, status: str = "completed") -> dict:
        return {
            "case_id": case["case_id"],
            "dsm_module": case["dsm_module"],
            "label": case["label"],
            "ambiguity": case["ambiguity"],
            "split": "all",
            "case_status": status,
            "asked_slots": ["onset_time"],
            "turn_logs": [],
            "final_output": {
                "diagnosis_topk": [
                    {"label": case["label"], "confidence": 0.7},
                    {"label": "OTHER", "confidence": 0.3},
                ],
                "slot_predictions": {"onset_time": "3 months"},
                "risk_flags": {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                "justification": [{"claim": "obs", "support_slots": ["onset_time"]}],
                "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                "calibration": {"uncertainty_statement": "需进一步评估。"},
            },
            "scoring_gold_labels": [case["label"]],
            "metrics": {
                "must_ask_hit_rate": 0.5,
                "svcl_domain_coverage": 0.5,
                "svcl_coverage": 0.5,
                "turns": 1,
                "turns_to_hit_all_must_ask": None,
                "top1_acc": 1.0 if status == "completed" else 0.0,
                "top3_cov": 1.0 if status == "completed" else 0.0,
                "top5_cov": 1.0 if status == "completed" else 0.0,
                "strict_top1_acc": 1.0 if status == "completed" else 0.0,
                "strict_top3_cov": 1.0 if status == "completed" else 0.0,
                "strict_top5_cov": 1.0 if status == "completed" else 0.0,
                "gold_accept_set_size": 1.0,
            },
            "harm_flags": [],
            "parse_error": status != "completed",
            "parse_retry_count": 0,
            "parse_error_code": "timeout" if status != "completed" else None,
            "raw_parse_diagnostics": None,
            "final_parse_diagnostics": None,
            "final_consumable": status == "completed",
            "invalid_final_reason": None if status == "completed" else "schema_error",
            "repair_attempted": False,
            "repair_succeeded": False,
            "termination_reason": "final" if status == "completed" else "execution_error",
            "adapter_attempts": 1,
            "last_error": None if status == "completed" else "timeout",
            "elapsed_ms": 10.0,
            "timeout_error": status != "completed",
        }

    def test_run_dynamic_filters_to_test_split_and_writes_metrics_artifact(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        ontology_dir = repo_root / "ontology"

        case_test = {
            "case_id": "PIB_TEST_DYNAMIC_0001",
            "dsm_module": "OCRD",
            "label": "OCD",
            "label_subtype": None,
            "ambiguity": "unambiguous",
            "patient_profile": {"age_band": "18-25", "gender": "F", "context": "college"},
            "info_variants": {
                "minimal_cc": "总想洗手。",
                "self_report": "反复洗手和担心脏。",
                "chart_full": "污染担忧和洗手仪式。",
            },
            "slot_truth": {
                "onset_time": {
                    "value": "3 months",
                    "certainty": "high",
                    "source": "interview",
                    "evidence": ["三个月前开始。"],
                },
                "intrusive_thoughts": {
                    "value": True,
                    "certainty": "high",
                    "source": "interview",
                    "evidence": ["脑子里总冒出不想要的念头。"],
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
            "required_svcl_domains": ["course_stability", "cog_emotion_process", "symptom_profile"],
            "patient_script": {
                "onset_time": ["三个月前开始。"],
                "intrusive_thoughts": ["脑子里总冒出不想要的念头。"],
                "ritual_behavior_present": ["会反复洗手。"],
                "unknown_default": ["不太确定。"],
            },
        }
        case_train = {
            **case_test,
            "case_id": "PIB_TEST_DYNAMIC_0002",
            "label": "BDD",
            "gold_ddx_top5": ["BDD", "OCD", "OS_OCRD", "SSD", "OTHER"],
        }
        rubric_test = {
            "case_id": "PIB_TEST_DYNAMIC_0001",
            "must_ask_slots": ["onset_time", "intrusive_thoughts", "ritual_behavior_present"],
            "must_ask_svcl_domains": ["course_stability", "cog_emotion_process", "symptom_profile"],
            "avoid_harm_rules": ["no_overconfident_dx"],
            "stop_rules": {"max_turns": 12},
        }
        rubric_train = {**rubric_test, "case_id": "PIB_TEST_DYNAMIC_0002"}

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cases_path = td_path / "cases.jsonl"
            rubrics_path = td_path / "rubrics.jsonl"
            output_path = td_path / "dynamic.jsonl"
            metrics_path = td_path / "metrics.json"
            summary_path = td_path / "summary.csv"
            splits_dir = td_path / "splits"
            splits_dir.mkdir()
            (splits_dir / "test_ids.txt").write_text("PIB_TEST_DYNAMIC_0001\n", encoding="utf-8")
            cases_path.write_text(
                "\n".join(
                    [
                        json.dumps(case_test, ensure_ascii=False),
                        json.dumps(case_train, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rubrics_path.write_text(
                "\n".join(
                    [
                        json.dumps(rubric_test, ensure_ascii=False),
                        json.dumps(rubric_train, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            run_dynamic(
                cases_path=cases_path,
                rubrics_path=rubrics_path,
                ontology_dir=ontology_dir,
                output_path=output_path,
                doctor_kind="dummy",
                split="test",
                splits_dir=splits_dir,
                summary_csv=summary_path,
                metrics_json=metrics_path,
            )

            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
            artifact_predictions_exists = Path(metrics_payload["artifacts"]["predictions_jsonl"]).exists()
            summary_header = summary_path.read_text(encoding="utf-8").splitlines()[0]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["case_id"], "PIB_TEST_DYNAMIC_0001")
        self.assertEqual(rows[0]["split"], "test")
        self.assertEqual(metrics_payload["task"], "dynamic")
        self.assertEqual(metrics_payload["n_cases"], 1)
        self.assertEqual(metrics_payload["run_config"]["split"], "test")
        self.assertTrue(artifact_predictions_exists)
        self.assertIn("final_consumable_rate", summary_header)
        self.assertIn("parse_error_rate", summary_header)
        self.assertIn("invalid_final_rate", summary_header)

    def test_final_validator_rejects_missing_other(self) -> None:
        final_output, consumable, invalid_reason = _validate_final_output(
            {
                "diagnosis_topk": [{"label": "OCD", "confidence": 0.8}],
                "risk_flags": {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                "justification": [{"claim": "obs", "support_slots": ["onset_time"]}],
                "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                "calibration": {"uncertainty_statement": "需进一步评估。"},
            },
            asked_slots=["onset_time"],
            observations={"onset_time": "3 months"},
        )
        self.assertFalse(consumable)
        self.assertEqual(invalid_reason, "missing_other")
        self.assertEqual(final_output["diagnosis_topk"][0]["label"], "OTHER")

    def test_final_validator_rejects_unknown_support_slots(self) -> None:
        final_output, consumable, invalid_reason = _validate_final_output(
            {
                "diagnosis_topk": [
                    {"label": "OCD", "confidence": 0.6},
                    {"label": "OTHER", "confidence": 0.4},
                ],
                "risk_flags": {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                "justification": [{"claim": "obs", "support_slots": ["intrusive_thoughts"]}],
                "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                "calibration": {"uncertainty_statement": "需进一步评估。"},
            },
            asked_slots=["onset_time"],
            observations={"onset_time": "3 months"},
        )
        self.assertFalse(consumable)
        self.assertEqual(invalid_reason, "unknown_support_slots")
        self.assertEqual(final_output["diagnosis_topk"][0]["label"], "OTHER")

    def test_repeat_slot_guard_repairs_once(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        ontology_dir = repo_root / "ontology"

        case = {
            "case_id": "PIB_TEST_DYNAMIC_REPAIR_0001",
            "dsm_module": "OCRD",
            "label": "OCD",
            "label_subtype": None,
            "ambiguity": "unambiguous",
            "patient_profile": {"age_band": "18-25", "gender": "F", "context": "college"},
            "info_variants": {
                "minimal_cc": "总想洗手。",
                "self_report": "反复洗手和担心脏。",
                "chart_full": "污染担忧和洗手仪式。",
            },
            "slot_truth": {
                "onset_time": {
                    "value": "3 months",
                    "certainty": "high",
                    "source": "interview",
                    "evidence": ["三个月前开始。"],
                },
                "intrusive_thoughts": {
                    "value": True,
                    "certainty": "high",
                    "source": "interview",
                    "evidence": ["脑子里总冒出不想要的念头。"],
                },
            },
            "gold_ddx_top5": ["OCD", "BDD", "OS_OCRD", "OCPD", "OTHER"],
            "risk_flags": {"suicide": False, "violence": False, "psychosis": False, "substance": False},
            "required_svcl_domains": ["course_stability", "cog_emotion_process"],
            "patient_script": {
                "onset_time": ["三个月前开始。"],
                "intrusive_thoughts": ["脑子里总冒出不想要的念头。"],
                "unknown_default": ["不太确定。"],
            },
        }
        rubric = {
            "case_id": "PIB_TEST_DYNAMIC_REPAIR_0001",
            "must_ask_slots": ["onset_time", "intrusive_thoughts"],
            "must_ask_svcl_domains": ["course_stability", "cog_emotion_process"],
            "avoid_harm_rules": ["no_overconfident_dx"],
            "stop_rules": {"max_turns": 12},
        }

        class _RepairDoctor:
            def __init__(self) -> None:
                self.calls = 0

            def next_action(self, minimal_cc, state, allowed_slots, must_ask_slots=None, forbidden_slots=None):
                self.calls += 1
                forbidden = set(forbidden_slots or [])
                if self.calls == 1:
                    return {"action": "ASK", "slot_id": "onset_time"}
                if self.calls == 2 and not forbidden:
                    return {"action": "ASK", "slot_id": "onset_time"}
                if forbidden:
                    return {"action": "ASK", "slot_id": "intrusive_thoughts"}
                return {
                    "action": "FINAL",
                    "final_output": {
                        "diagnosis_topk": [
                            {"label": "OCD", "confidence": 0.7},
                            {"label": "OTHER", "confidence": 0.3},
                        ],
                        "slot_predictions": dict(state.observations),
                        "risk_flags": {
                            "suicide": False,
                            "violence": False,
                            "psychosis": False,
                            "substance": False,
                        },
                        "justification": [
                            {"claim": "obs", "support_slots": list(state.asked_slots)}
                        ],
                        "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                        "calibration": {"uncertainty_statement": "需进一步评估。"},
                    },
                }

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cases_path = td_path / "cases.jsonl"
            rubrics_path = td_path / "rubrics.jsonl"
            output_path = td_path / "dynamic.jsonl"
            cases_path.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")
            rubrics_path.write_text(json.dumps(rubric, ensure_ascii=False) + "\n", encoding="utf-8")

            with patch("eval.run_dynamic._build_doctor", return_value=_RepairDoctor()):
                run_dynamic(
                    cases_path=cases_path,
                    rubrics_path=rubrics_path,
                    ontology_dir=ontology_dir,
                    output_path=output_path,
                    doctor_kind="llm",
                    split=None,
                )

            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["repair_attempted"])
        self.assertTrue(rows[0]["repair_succeeded"])
        self.assertEqual(rows[0]["termination_reason"], "final")
        self.assertEqual(rows[0]["asked_slots"], ["onset_time", "intrusive_thoughts"])
        self.assertTrue(rows[0]["final_consumable"])

    def test_resume_skips_completed_cases(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        ontology_dir = repo_root / "ontology"
        case_a = self._make_case("PIB_TEST_DYNAMIC_RESUME_0001", minimal_cc="resume-a")
        case_b = self._make_case("PIB_TEST_DYNAMIC_RESUME_0002", label="BDD", minimal_cc="resume-b")
        rubric_a = self._make_rubric(case_a["case_id"])
        rubric_b = self._make_rubric(case_b["case_id"])

        class _FinalDoctor:
            def __init__(self) -> None:
                self.minimal_ccs: list[str] = []

            def next_action(self, minimal_cc, state, allowed_slots, must_ask_slots=None, forbidden_slots=None):
                self.minimal_ccs.append(minimal_cc)
                return {
                    "action": "FINAL",
                    "final_output": {
                        "diagnosis_topk": [
                            {"label": "BDD", "confidence": 0.7},
                            {"label": "OTHER", "confidence": 0.3},
                        ],
                        "slot_predictions": dict(state.observations),
                        "risk_flags": {
                            "suicide": False,
                            "violence": False,
                            "psychosis": False,
                            "substance": False,
                        },
                        "justification": [],
                        "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                        "calibration": {"uncertainty_statement": "需进一步评估。"},
                    },
                }

        doctor = _FinalDoctor()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cases_path = td_path / "cases.jsonl"
            rubrics_path = td_path / "rubrics.jsonl"
            output_path = td_path / "dynamic.jsonl"
            summary_path = td_path / "summary.csv"
            metrics_path = td_path / "metrics.json"
            cases_path.write_text(
                "\n".join([json.dumps(case_a, ensure_ascii=False), json.dumps(case_b, ensure_ascii=False)]) + "\n",
                encoding="utf-8",
            )
            rubrics_path.write_text(
                "\n".join([json.dumps(rubric_a, ensure_ascii=False), json.dumps(rubric_b, ensure_ascii=False)]) + "\n",
                encoding="utf-8",
            )
            output_path.write_text(json.dumps(self._existing_row(case_a), ensure_ascii=False) + "\n", encoding="utf-8")

            with patch("eval.run_dynamic._build_doctor", return_value=doctor):
                run_dynamic(
                    cases_path=cases_path,
                    rubrics_path=rubrics_path,
                    ontology_dir=ontology_dir,
                    output_path=output_path,
                    doctor_kind="llm",
                    split=None,
                    resume_from_case=case_a["case_id"],
                    summary_csv=summary_path,
                    metrics_json=metrics_path,
                )

            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual([row["case_id"] for row in rows], [case_a["case_id"], case_b["case_id"]])
        self.assertEqual(doctor.minimal_ccs, ["resume-b"])
        self.assertEqual(rows[0]["case_status"], "completed")
        self.assertEqual(rows[1]["case_status"], "completed")

    def test_rerun_failed_only(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        ontology_dir = repo_root / "ontology"
        case_a = self._make_case("PIB_TEST_DYNAMIC_RERUN_0001", minimal_cc="rerun-a")
        case_b = self._make_case("PIB_TEST_DYNAMIC_RERUN_0002", label="BDD", minimal_cc="rerun-b")
        rubric_a = self._make_rubric(case_a["case_id"])
        rubric_b = self._make_rubric(case_b["case_id"])

        class _FinalDoctor:
            def __init__(self) -> None:
                self.minimal_ccs: list[str] = []

            def next_action(self, minimal_cc, state, allowed_slots, must_ask_slots=None, forbidden_slots=None):
                self.minimal_ccs.append(minimal_cc)
                return {
                    "action": "FINAL",
                    "final_output": {
                        "diagnosis_topk": [
                            {"label": "BDD", "confidence": 0.7},
                            {"label": "OTHER", "confidence": 0.3},
                        ],
                        "slot_predictions": dict(state.observations),
                        "risk_flags": {
                            "suicide": False,
                            "violence": False,
                            "psychosis": False,
                            "substance": False,
                        },
                        "justification": [],
                        "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                        "calibration": {"uncertainty_statement": "需进一步评估。"},
                    },
                }

        doctor = _FinalDoctor()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cases_path = td_path / "cases.jsonl"
            rubrics_path = td_path / "rubrics.jsonl"
            output_path = td_path / "dynamic.jsonl"
            cases_path.write_text(
                "\n".join([json.dumps(case_a, ensure_ascii=False), json.dumps(case_b, ensure_ascii=False)]) + "\n",
                encoding="utf-8",
            )
            rubrics_path.write_text(
                "\n".join([json.dumps(rubric_a, ensure_ascii=False), json.dumps(rubric_b, ensure_ascii=False)]) + "\n",
                encoding="utf-8",
            )
            output_path.write_text(
                "\n".join(
                    [
                        json.dumps(self._existing_row(case_a, status="completed"), ensure_ascii=False),
                        json.dumps(self._existing_row(case_b, status="failed"), ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("eval.run_dynamic._build_doctor", return_value=doctor):
                run_dynamic(
                    cases_path=cases_path,
                    rubrics_path=rubrics_path,
                    ontology_dir=ontology_dir,
                    output_path=output_path,
                    doctor_kind="llm",
                    split=None,
                    rerun_failed_only=True,
                )

            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual([row["case_id"] for row in rows], [case_a["case_id"], case_b["case_id"]])
        self.assertEqual(doctor.minimal_ccs, ["rerun-b"])
        self.assertEqual(rows[0]["case_status"], "completed")
        self.assertEqual(rows[1]["case_status"], "completed")

    def test_timeout_marks_case_not_whole_run(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        ontology_dir = repo_root / "ontology"
        case_a = self._make_case("PIB_TEST_DYNAMIC_TIMEOUT_0001", minimal_cc="timeout-a")
        case_b = self._make_case("PIB_TEST_DYNAMIC_TIMEOUT_0002", label="BDD", minimal_cc="timeout-b")
        rubric_a = self._make_rubric(case_a["case_id"])
        rubric_b = self._make_rubric(case_b["case_id"])

        class _TimeoutError(RuntimeError):
            code = "timeout"

        class _TimeoutDoctor:
            def next_action(self, minimal_cc, state, allowed_slots, must_ask_slots=None, forbidden_slots=None):
                if minimal_cc == "timeout-b":
                    raise _TimeoutError("timed out")
                return {
                    "action": "FINAL",
                    "final_output": {
                        "diagnosis_topk": [
                            {"label": "OCD", "confidence": 0.7},
                            {"label": "OTHER", "confidence": 0.3},
                        ],
                        "slot_predictions": dict(state.observations),
                        "risk_flags": {
                            "suicide": False,
                            "violence": False,
                            "psychosis": False,
                            "substance": False,
                        },
                        "justification": [],
                        "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
                        "calibration": {"uncertainty_statement": "需进一步评估。"},
                    },
                }

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cases_path = td_path / "cases.jsonl"
            rubrics_path = td_path / "rubrics.jsonl"
            output_path = td_path / "dynamic.jsonl"
            summary_path = td_path / "summary.csv"
            metrics_path = td_path / "metrics.json"
            cases_path.write_text(
                "\n".join([json.dumps(case_a, ensure_ascii=False), json.dumps(case_b, ensure_ascii=False)]) + "\n",
                encoding="utf-8",
            )
            rubrics_path.write_text(
                "\n".join([json.dumps(rubric_a, ensure_ascii=False), json.dumps(rubric_b, ensure_ascii=False)]) + "\n",
                encoding="utf-8",
            )

            with patch("eval.run_dynamic._build_doctor", return_value=_TimeoutDoctor()):
                run_dynamic(
                    cases_path=cases_path,
                    rubrics_path=rubrics_path,
                    ontology_dir=ontology_dir,
                    output_path=output_path,
                    doctor_kind="llm",
                    split=None,
                    summary_csv=summary_path,
                    metrics_json=metrics_path,
                )

            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
            summary_header = summary_path.read_text(encoding="utf-8").splitlines()[0]

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["case_status"], "completed")
        self.assertEqual(rows[1]["case_status"], "failed")
        self.assertTrue(rows[1]["timeout_error"])
        self.assertEqual(rows[1]["last_error"], "timeout")
        self.assertEqual(metrics_payload["n_cases"], 2)
        self.assertIn("execution_success_rate", summary_header)
        self.assertIn("timeout_count", summary_header)
        self.assertIn("adapter_error_count", summary_header)

    def test_partial_summary_generation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        ontology_dir = repo_root / "ontology"
        case = self._make_case("PIB_TEST_DYNAMIC_PARTIAL_0001", minimal_cc="partial-a")
        rubric = self._make_rubric(case["case_id"])

        class _TimeoutError(RuntimeError):
            code = "timeout"

        class _FailDoctor:
            def next_action(self, minimal_cc, state, allowed_slots, must_ask_slots=None, forbidden_slots=None):
                raise _TimeoutError("timed out")

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cases_path = td_path / "cases.jsonl"
            rubrics_path = td_path / "rubrics.jsonl"
            output_path = td_path / "dynamic.jsonl"
            summary_path = td_path / "summary.csv"
            metrics_path = td_path / "metrics.json"
            cases_path.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")
            rubrics_path.write_text(json.dumps(rubric, ensure_ascii=False) + "\n", encoding="utf-8")

            with patch("eval.run_dynamic._build_doctor", return_value=_FailDoctor()):
                run_dynamic(
                    cases_path=cases_path,
                    rubrics_path=rubrics_path,
                    ontology_dir=ontology_dir,
                    output_path=output_path,
                    doctor_kind="llm",
                    split=None,
                    summary_csv=summary_path,
                    metrics_json=metrics_path,
                )

            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
            summary_exists = summary_path.exists()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["case_status"], "failed")
        self.assertTrue(summary_exists)
        self.assertEqual(metrics_payload["n_cases"], 1)
        self.assertEqual(metrics_payload["summary"]["overall"]["timeout_count"], 1.0)
