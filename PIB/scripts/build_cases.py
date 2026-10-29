from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from eval.load import (
    DataValidationError,
    audit_high_risk_rubric_coverage,
    load_cases,
    load_ontology,
    load_rubrics,
    write_jsonl,
)


def _parse_json_cell(row: Dict[str, str], key: str, row_num: int, default: Any = None) -> Any:
    raw = (row.get(key) or "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataValidationError(
            f"CSV row {row_num}: invalid JSON in column '{key}': {exc}"
        ) from exc


def _required_text(row: Dict[str, str], key: str, row_num: int) -> str:
    value = (row.get(key) or "").strip()
    if not value:
        raise DataValidationError(f"CSV row {row_num}: missing required column '{key}'")
    return value


def build_records_from_csv(template_csv: Path) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    cases: List[Dict[str, Any]] = []
    rubrics: List[Dict[str, Any]] = []

    with template_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue

            case_id = _required_text(row, "case_id", idx)
            dsm_module = _required_text(row, "dsm_module", idx)
            label = _required_text(row, "label", idx)

            slot_truth = _parse_json_cell(row, "slot_truth_json", idx, default={})
            if not isinstance(slot_truth, dict):
                raise DataValidationError(f"CSV row {idx}: slot_truth_json must be a JSON object")

            gold_ddx_top5 = _parse_json_cell(row, "gold_ddx_top5_json", idx, default=[])
            if not isinstance(gold_ddx_top5, list):
                raise DataValidationError(f"CSV row {idx}: gold_ddx_top5_json must be a JSON array")

            risk_flags = _parse_json_cell(
                row,
                "risk_flags_json",
                idx,
                default={"suicide": False, "violence": False, "psychosis": False, "substance": False},
            )
            required_svcl_domains = _parse_json_cell(row, "required_svcl_domains_json", idx, default=[])
            patient_script = _parse_json_cell(row, "patient_script_json", idx, default={})
            must_ask_slots = _parse_json_cell(row, "must_ask_slots_json", idx, default=[])
            must_ask_svcl_domains = _parse_json_cell(row, "must_ask_svcl_domains_json", idx, default=[])
            avoid_harm_rules = _parse_json_cell(row, "avoid_harm_rules_json", idx, default=[])

            if not isinstance(risk_flags, dict):
                raise DataValidationError(f"CSV row {idx}: risk_flags_json must be a JSON object")
            if not isinstance(required_svcl_domains, list):
                raise DataValidationError(
                    f"CSV row {idx}: required_svcl_domains_json must be a JSON array"
                )
            if not isinstance(patient_script, dict):
                raise DataValidationError(f"CSV row {idx}: patient_script_json must be a JSON object")
            if not isinstance(must_ask_slots, list):
                raise DataValidationError(f"CSV row {idx}: must_ask_slots_json must be a JSON array")
            if not isinstance(must_ask_svcl_domains, list):
                raise DataValidationError(
                    f"CSV row {idx}: must_ask_svcl_domains_json must be a JSON array"
                )
            if not isinstance(avoid_harm_rules, list):
                raise DataValidationError(
                    f"CSV row {idx}: avoid_harm_rules_json must be a JSON array"
                )

            max_turns_raw = (row.get("max_turns") or "").strip()
            max_turns = int(max_turns_raw) if max_turns_raw else None

            case = {
                "case_id": case_id,
                "dsm_module": dsm_module,
                "label": label,
                "label_subtype": (row.get("label_subtype") or "").strip() or None,
                "ambiguity": (row.get("ambiguity") or "ambiguous").strip() or "ambiguous",
                "patient_profile": {
                    "age_band": (row.get("age_band") or "").strip() or "unknown",
                    "gender": (row.get("gender") or "").strip() or "unknown",
                    "context": (row.get("context") or "").strip() or "unknown",
                },
                "info_variants": {
                    "minimal_cc": _required_text(row, "minimal_cc", idx),
                    "self_report": _required_text(row, "self_report", idx),
                    "chart_full": _required_text(row, "chart_full", idx),
                },
                "slot_truth": slot_truth,
                "gold_ddx_top5": gold_ddx_top5,
                "risk_flags": risk_flags,
                "required_svcl_domains": required_svcl_domains,
                "patient_script": patient_script,
            }
            rubric = {
                "case_id": case_id,
                "must_ask_slots": must_ask_slots,
                "must_ask_svcl_domains": must_ask_svcl_domains,
                "avoid_harm_rules": avoid_harm_rules,
                "stop_rules": {"max_turns": max_turns} if max_turns is not None else {},
            }

            cases.append(case)
            rubrics.append(rubric)

    if not cases:
        raise DataValidationError("No rows parsed from template CSV")

    return cases, rubrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile authoring CSV into cases/rubrics JSONL")
    parser.add_argument("--template", type=Path, default=Path("authoring/cases_template.csv"))
    parser.add_argument("--cases-out", type=Path, default=Path("data/cases.jsonl"))
    parser.add_argument("--rubrics-out", type=Path, default=Path("data/rubrics.jsonl"))
    parser.add_argument("--ontology", type=Path, default=Path("ontology"))
    parser.add_argument("--config", type=Path, default=Path("pib_config.yaml"))
    args = parser.parse_args()

    try:
        cases, rubrics = build_records_from_csv(args.template)

        tmp_cases = args.cases_out.with_suffix(args.cases_out.suffix + ".tmp")
        tmp_rubrics = args.rubrics_out.with_suffix(args.rubrics_out.suffix + ".tmp")

        write_jsonl(tmp_cases, cases)
        write_jsonl(tmp_rubrics, rubrics)

        ontology = load_ontology(args.ontology, config_path=args.config)
        loaded_cases = load_cases(tmp_cases, ontology)
        loaded_rubrics = load_rubrics(tmp_rubrics, ontology, case_ids=[c.case_id for c in loaded_cases])
        high_risk_findings = audit_high_risk_rubric_coverage(loaded_cases, loaded_rubrics)
        if high_risk_findings:
            raise DataValidationError(
                "High-risk rubric coverage gaps detected: "
                + "; ".join(
                    f"{finding['case_id']} missing {finding['missing_risk_slots']}"
                    for finding in high_risk_findings
                )
            )

        args.cases_out.parent.mkdir(parents=True, exist_ok=True)
        args.rubrics_out.parent.mkdir(parents=True, exist_ok=True)
        tmp_cases.replace(args.cases_out)
        tmp_rubrics.replace(args.rubrics_out)
    except DataValidationError as exc:
        print("Build failed")
        print(exc)
        return 1

    print(f"Build succeeded: {args.cases_out} ({len(cases)} cases)")
    print(f"Build succeeded: {args.rubrics_out} ({len(rubrics)} rubrics)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
