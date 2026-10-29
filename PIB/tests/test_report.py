from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.report import (
    default_run_artifacts,
    summarize_rows,
    summarize_static_stage_rows,
    write_metrics_artifact,
    write_static_stage_breakdown,
)


class ReportTests(unittest.TestCase):
    def test_static_summary_keeps_stage_error_columns_separate(self) -> None:
        rows = [
            {
                "case_id": "CASE_1",
                "dsm_module": "OCRD",
                "label": "OCD",
                "ambiguity": "unambiguous",
                "metrics": {
                    "top5_cov": 1.0,
                    "required_slot_coverage": 0.5,
                    "slot_stage_error_rate": 1.0,
                    "slot_stage_success_rate": 0.0,
                    "ddx_stage_error_rate": 0.0,
                    "ddx_stage_success_rate": 1.0,
                    "predicted_slot_count": 0.0,
                    "diagnosis_count": 5.0,
                },
                "harm_flags": [],
            },
            {
                "case_id": "CASE_2",
                "dsm_module": "OCRD",
                "label": "OCD",
                "ambiguity": "unambiguous",
                "metrics": {
                    "top5_cov": 1.0,
                    "required_slot_coverage": 1.0,
                    "slot_stage_error_rate": 0.0,
                    "slot_stage_success_rate": 1.0,
                    "ddx_stage_error_rate": 1.0,
                    "ddx_stage_success_rate": 0.0,
                    "predicted_slot_count": 3.0,
                    "diagnosis_count": 5.0,
                },
                "harm_flags": [],
            },
        ]

        summary_rows = summarize_rows(rows)
        overall = next(row for row in summary_rows if row["slice"] == "overall")

        self.assertEqual(overall["slot_stage_error_rate"], 0.5)
        self.assertEqual(overall["ddx_stage_error_rate"], 0.5)
        self.assertEqual(overall["slot_stage_success_rate"], 0.5)
        self.assertEqual(overall["ddx_stage_success_rate"], 0.5)
        self.assertEqual(overall["predicted_slot_count"], 1.5)
        self.assertEqual(overall["diagnosis_count"], 5.0)

    def test_static_stage_breakdown_includes_input_variant_and_mode_slices(self) -> None:
        rows = [
            {
                "case_id": "CASE_1",
                "dsm_module": "OCRD",
                "label": "OCD",
                "ambiguity": "ambiguous",
                "input_variant": "self_report",
                "mode": "llm",
                "metrics": {
                    "slot_stage_error_rate": 1.0,
                    "slot_stage_success_rate": 0.0,
                    "ddx_stage_error_rate": 0.0,
                    "ddx_stage_success_rate": 1.0,
                    "predicted_slot_count": 0.0,
                    "diagnosis_count": 5.0,
                    "top5_cov": 1.0,
                },
                "harm_flags": [],
            }
        ]

        summary_rows = summarize_static_stage_rows(rows)
        input_variant_row = next(
            row for row in summary_rows if row["slice"] == "input_variant" and row["slice_value"] == "self_report"
        )
        mode_row = next(row for row in summary_rows if row["slice"] == "mode" and row["slice_value"] == "llm")

        self.assertEqual(input_variant_row["slot_stage_error_rate"], 1.0)
        self.assertEqual(mode_row["ddx_stage_success_rate"], 1.0)

    def test_write_static_stage_breakdown_emits_tex_with_fixed_columns(self) -> None:
        rows = [
            {
                "case_id": "CASE_1",
                "dsm_module": "OCRD",
                "label": "OCD",
                "ambiguity": "ambiguous",
                "input_variant": "self_report",
                "mode": "llm",
                "metrics": {
                    "slot_stage_error_rate": 0.0,
                    "slot_stage_success_rate": 1.0,
                    "ddx_stage_error_rate": 1.0,
                    "ddx_stage_success_rate": 0.0,
                    "predicted_slot_count": 2.0,
                    "diagnosis_count": 5.0,
                    "top5_cov": 1.0,
                },
                "harm_flags": [],
            }
        ]

        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "static_stage_breakdown.csv"
            tex_path = Path(td) / "tables_static_stage.tex"
            write_static_stage_breakdown(rows, output_csv=csv_path, output_tex=tex_path)
            latex = tex_path.read_text(encoding="utf-8")

        self.assertIn("\\begin{tabular}", latex)
        self.assertIn("slice & slice_value & n & slot_stage_error_rate", latex)
        self.assertIn("input_variant & self_report", latex)

    def test_default_run_artifacts_allocates_new_run_directories(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output_path = Path(td) / "static.jsonl"
            first = default_run_artifacts("static", output_path)
            first["artifact_dir"].mkdir(parents=True, exist_ok=True)
            second = default_run_artifacts("static", output_path)

        self.assertTrue(str(first["artifact_dir"]).endswith("run_001"))
        self.assertTrue(str(second["artifact_dir"]).endswith("run_002"))

    def test_write_metrics_artifact_emits_canonical_metrics_json(self) -> None:
        rows = [
            {
                "case_id": "CASE_1",
                "dsm_module": "OCRD",
                "label": "OCD",
                "ambiguity": "unambiguous",
                "metrics": {"top5_cov": 1.0},
                "harm_flags": [],
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            metrics_path = Path(td) / "metrics.json"
            write_metrics_artifact(
                rows,
                metrics_json=metrics_path,
                task="static",
                predictions_path=Path(td) / "predictions.jsonl",
                run_config={"split": "test"},
                extra_artifacts={"summary_csv": str(Path(td) / "summary.csv")},
            )
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["task"], "static")
        self.assertEqual(payload["n_cases"], 1)
        self.assertIn("release", payload)
        self.assertIn("benchmark_version", payload["release"])
        self.assertIn("scoring_policy_version", payload["release"])
        self.assertEqual(payload["run_config"]["split"], "test")
        self.assertIn("predictions_jsonl", payload["artifacts"])
        self.assertIn("overall", payload["summary"])
