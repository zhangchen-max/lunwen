from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Any, Dict

from tqdm import tqdm

from agents.doctor_agent import DoctorState, DummyDoctorAgent, LLMDoctorAgent, SSMDoctorAgent, SSMConfig
from agents.patient_agent import PatientAgent
from eval.load import (
    DataValidationError,
    derive_domains_from_slots,
    filter_cases_by_ids,
    filter_rubrics_by_ids,
    load_cases,
    load_ontology,
    load_rubrics,
    load_split_ids,
    read_jsonl,
    write_jsonl,
)
from eval.report import default_run_artifacts, summarize_rows, write_metrics_artifact, write_summary
from eval.scorers.ddx_metrics import benchmark_gold_labels
from eval.schema import FinalOutput
from eval.scorers.dynamic_metrics import score_dynamic_case
from eval.scorers.safety_rules import PRESCRIPTIVE_PATTERNS, evaluate_avoid_harm
from models.adapters.factory import build_chat_adapter


INVALID_FINAL_PARSE_FALLBACK = "parse_error_default_other"


def _build_doctor(
    doctor_kind: str,
    provider: str,
    model: str | None,
    endpoint: str | None,
    cache_root: Path | None,
    use_cache: bool,
    seed: int,
    temperature: float,
):
    if doctor_kind == "dummy":
        return DummyDoctorAgent(seed=seed)

    adapter = build_chat_adapter(
        provider=provider,
        model=model,
        endpoint=endpoint,
        cache_root=cache_root,
        use_cache=use_cache,
    )
    if doctor_kind == "llm":
        return LLMDoctorAgent(adapter=adapter, temperature=temperature)
    if doctor_kind == "ssm":
        return SSMDoctorAgent(adapter=adapter, temperature=temperature, config=SSMConfig(), max_turns=15)
    if doctor_kind == "ssm_a2":
        return SSMDoctorAgent(
            adapter=adapter,
            temperature=temperature,
            config=SSMConfig(use_t1=False, use_t2=False, use_t3=False),
            max_turns=15,
        )
    if doctor_kind == "ssm_a3":
        return SSMDoctorAgent(
            adapter=adapter,
            temperature=temperature,
            config=SSMConfig(use_phi=False),
            max_turns=15,
        )
    if doctor_kind == "ssm_a4":
        return SSMDoctorAgent(
            adapter=adapter,
            temperature=temperature,
            config=SSMConfig(four_state=False),
            max_turns=15,
        )
    return LLMDoctorAgent(adapter=adapter, temperature=temperature)


def _fallback_final_output(observations: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "diagnosis_topk": [{"label": "OTHER", "confidence": 1.0}],
        "slot_predictions": observations,
        "risk_flags": {
            "suicide": False,
            "violence": False,
            "psychosis": False,
            "substance": False,
        },
        "justification": [{"claim": "模型未能输出有效 FINAL，默认 OTHER。", "support_slots": []}],
        "next_steps": [{"type": "suggest_assessment", "text": "建议进一步评估。"}],
        "calibration": {"uncertainty_statement": "输出解析失败，需重新评估。"},
    }


def _next_steps_are_non_prescriptive(next_steps: list[dict[str, Any]]) -> bool:
    for item in next_steps:
        step_type = str(item.get("type") or "").lower()
        text = str(item.get("text") or "")
        if step_type in {"prescribe", "medicate", "treat_now"}:
            return False
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in PRESCRIPTIVE_PATTERNS):
            return False
    return True


def _validate_final_output(
    raw_final_output: Dict[str, Any] | None,
    asked_slots: list[str],
    observations: Dict[str, Any],
) -> tuple[Dict[str, Any], bool, str | None]:
    if raw_final_output is None:
        return _fallback_final_output(observations), False, INVALID_FINAL_PARSE_FALLBACK
    if not isinstance(raw_final_output, dict):
        return _fallback_final_output(observations), False, "schema_error"
    if "diagnosis_topk" not in raw_final_output:
        return _fallback_final_output(observations), False, "missing_diagnosis_topk"
    if "risk_flags" not in raw_final_output:
        return _fallback_final_output(observations), False, "missing_risk_flags"
    if "calibration" not in raw_final_output:
        return _fallback_final_output(observations), False, "missing_calibration"

    try:
        validated = FinalOutput.model_validate(raw_final_output).model_dump()
    except Exception:
        return _fallback_final_output(observations), False, "schema_error"

    labels = [str(item.get("label")) for item in validated.get("diagnosis_topk", []) if isinstance(item, dict)]
    if not labels:
        return _fallback_final_output(observations), False, "missing_diagnosis_topk"
    if "OTHER" not in labels:
        return _fallback_final_output(observations), False, "missing_other"

    asked_slots_set = set(asked_slots)
    for item in validated.get("justification", []):
        if not isinstance(item, dict):
            continue
        for slot_id in item.get("support_slots", []) or []:
            if slot_id not in asked_slots_set:
                return _fallback_final_output(observations), False, "unknown_support_slots"

    if not _next_steps_are_non_prescriptive(validated.get("next_steps", [])):
        return _fallback_final_output(observations), False, "prescriptive_next_steps"

    return validated, True, None


def _error_code_from_exception(exc: Exception) -> tuple[str, bool]:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code, code == "timeout"
    text = str(exc).lower()
    timeout = "timeout" in text or "timed out" in text
    if timeout:
        return "timeout", True
    if "provider unavailable" in text or "api key" in text:
        return "provider_unavailable", False
    if "transport" in text or "connection" in text or "urlopen" in text:
        return "transport_error", False
    return "adapter_error", False


def _load_existing_rows(*paths: Path) -> list[dict[str, Any]]:
    for path in paths:
        if path.exists():
            try:
                return read_jsonl(path)
            except DataValidationError:
                continue
    return []


def run_dynamic(
    cases_path: Path,
    rubrics_path: Path,
    ontology_dir: Path,
    output_path: Path,
    seed: int = 1234,
    max_invalid_actions: int = 2,
    doctor_kind: str = "dummy",
    provider: str = "openai",
    model: str | None = None,
    endpoint: str | None = None,
    cache_root: Path | None = None,
    use_cache: bool = True,
    temperature: float = 0.0,
    split: str | None = None,
    splits_dir: Path = Path("data/splits"),
    summary_csv: Path | None = None,
    table_tex: Path | None = None,
    metrics_json: Path | None = None,
    resume_from_case: str | None = None,
    rerun_failed_only: bool = False,
    max_cases: int | None = None,
) -> None:
    try:
        ont = load_ontology(ontology_dir)
        case_records = load_cases(cases_path, ont)
        rubric_records = load_rubrics(rubrics_path, ont, [c.case_id for c in case_records])
    except DataValidationError as exc:
        raise SystemExit(f"Validation failed before run: {exc}")

    if split is not None:
        if split == "all":
            selected_ids: List[str] = []
            for _part in ("train", "dev", "test"):
                selected_ids.extend(load_split_ids(splits_dir, _part))
        else:
            selected_ids = load_split_ids(splits_dir, split)
        case_records = filter_cases_by_ids(case_records, selected_ids)
        rubric_records = filter_rubrics_by_ids(rubric_records, selected_ids)

    all_case_records = list(case_records)
    rubric_by_case = {r.case_id: r for r in rubric_records}
    allowed_slots = sorted(ont.slot_ids)
    artifact_paths = default_run_artifacts("dynamic", output_path)
    existing_rows = _load_existing_rows(artifact_paths["predictions_jsonl"], output_path)
    existing_rows_by_case = {
        str(row.get("case_id")): row for row in existing_rows if isinstance(row, dict) and row.get("case_id")
    }

    if resume_from_case:
        resume_index = next((idx for idx, case in enumerate(case_records) if case.case_id == resume_from_case), None)
        if resume_index is None:
            raise SystemExit(f"Unknown resume_from_case: {resume_from_case}")
        case_records = case_records[resume_index:]

    if rerun_failed_only:
        failed_case_ids = {
            case_id
            for case_id, row in existing_rows_by_case.items()
            if row.get("case_status") != "completed"
        }
        case_records = [case for case in case_records if case.case_id in failed_case_ids]
    elif resume_from_case:
        case_records = [
            case
            for case in case_records
            if existing_rows_by_case.get(case.case_id, {}).get("case_status") != "completed"
        ]

    if max_cases is not None:
        case_records = case_records[:max_cases]

    patient = PatientAgent(default_seed=seed)
    doctor = _build_doctor(
        doctor_kind=doctor_kind,
        provider=provider,
        model=model,
        endpoint=endpoint,
        cache_root=cache_root,
        use_cache=use_cache,
        seed=seed,
        temperature=temperature,
    )

    rows_by_case = dict(existing_rows_by_case)

    for case in tqdm(case_records, desc="dynamic"):
        rubric = rubric_by_case[case.case_id]
        case_max_turns = min(rubric.stop_rules.max_turns, ont.dynamic_max_turns_cap)
        state = DoctorState()
        logs = []
        final_output: Dict[str, Any] | None = None
        invalid_actions = 0
        repeat_count = 0
        prev_slot = None
        termination_reason = "max_turns"
        parse_retry_count = 0
        parse_error = False
        parse_error_code: str | None = None
        raw_parse_diagnostics: Dict[str, Any] | None = None
        final_parse_diagnostics: Dict[str, Any] | None = None
        final_consumable = False
        invalid_final_reason: str | None = None
        repair_attempted = False
        repair_succeeded = False
        adapter_attempts = 0
        last_error: str | None = None
        timeout_error = False
        case_status = "completed"
        case_started = time.perf_counter()

        try:
            for turn in range(1, case_max_turns + 1):
                state.turn = turn
                doctor_must_ask_slots = rubric.must_ask_slots if doctor_kind in ("llm", "ssm", "ssm_a2", "ssm_a3", "ssm_a4") else None
                if doctor_kind == "llm":
                    adapter_attempts += 1
                action = doctor.next_action(
                    minimal_cc=case.info_variants.minimal_cc,
                    state=state,
                    allowed_slots=allowed_slots,
                    must_ask_slots=doctor_must_ask_slots,
                )

                action_type = action.get("action")
                action_parse = action.get("_parse_diagnostics")
                if isinstance(action_parse, dict):
                    parse_retry_count += int(action_parse.get("retry_count") or 0)
                    raw_parse_diagnostics = action_parse
                if action_type == "PARSE_ERROR":
                    parse_error = True
                    parse_error_code = str(action.get("error") or "parse_error")
                    termination_reason = "parse_error"
                    logs.append(
                        {
                            "turn": turn,
                            "doctor_action": {"action": "PARSE_ERROR"},
                            "event": "parse_error",
                            "parse_error_code": parse_error_code,
                            "parse_diagnostics": action_parse,
                        }
                    )
                    break
                if action_type == "ASK":
                    slot_id = action.get("slot_id")
                    if slot_id not in ont.slot_ids:
                        invalid_actions += 1
                        logs.append(
                            {
                                "turn": turn,
                                "doctor_action": action,
                                "event": "invalid_slot_id",
                            }
                        )
                        if invalid_actions > max_invalid_actions:
                            termination_reason = "invalid_slot_id_limit"
                            break
                        continue

                    if slot_id in state.asked_slots:
                        repair_attempted = True
                        if doctor_kind == "llm":
                            adapter_attempts += 1
                        repaired_action = doctor.next_action(
                            minimal_cc=case.info_variants.minimal_cc,
                            state=state,
                            allowed_slots=allowed_slots,
                            must_ask_slots=doctor_must_ask_slots,
                            forbidden_slots=state.asked_slots,
                        )
                        repair_parse = repaired_action.get("_parse_diagnostics")
                        if isinstance(repair_parse, dict):
                            parse_retry_count += int(repair_parse.get("retry_count") or 0)
                            raw_parse_diagnostics = repair_parse
                        repaired_slot_id = repaired_action.get("slot_id") if repaired_action.get("action") == "ASK" else None
                        if repaired_action.get("action") == "FINAL":
                            # Repair produced FINAL — process it immediately
                            final_parse = repaired_action.get("_final_parse_diagnostics")
                            if isinstance(final_parse, dict):
                                parse_retry_count += int(final_parse.get("retry_count") or 0)
                                final_parse_diagnostics = final_parse
                            final_output, final_consumable, invalid_final_reason = _validate_final_output(
                                repaired_action.get("final_output"),
                                state.asked_slots,
                                state.observations,
                            )
                            if not final_consumable:
                                parse_error = True
                                if invalid_final_reason == INVALID_FINAL_PARSE_FALLBACK:
                                    parse_error_code = parse_error_code or "parse_error"
                                else:
                                    parse_error_code = parse_error_code or "schema_error"
                            logs.append({"turn": turn, "doctor_action": repaired_action})
                            termination_reason = "final"
                            break
                        elif repaired_slot_id and repaired_slot_id not in state.asked_slots and repaired_slot_id in ont.slot_ids:
                            action = repaired_action
                            slot_id = repaired_slot_id
                            repair_succeeded = True
                        else:
                            logs.append(
                                {
                                    "turn": turn,
                                    "doctor_action": action,
                                    "event": "repeat_slot_repair_failed",
                                    "repair_action": repaired_action,
                                }
                            )
                            termination_reason = "repeat_slot"
                            break

                    if slot_id == prev_slot:
                        repeat_count += 1
                    else:
                        repeat_count = 0
                    prev_slot = slot_id

                    if repeat_count >= ont.max_repeat_same_slot:
                        logs.append(
                            {
                                "turn": turn,
                                "doctor_action": action,
                                "event": "forced_stop_repeated_slot",
                            }
                        )
                        termination_reason = "repeat_slot"
                        break

                    reply = patient.answer(case=case, slot_id=slot_id, seed=seed, turn=turn)
                    state.asked_slots.append(slot_id)
                    state.observations[slot_id] = reply.value
                    logs.append(
                        {
                            "turn": turn,
                            "doctor_action": action,
                            "patient_answer": {
                                "slot_id": reply.slot_id,
                                "value": reply.value,
                                "utterance": reply.utterance,
                                "certainty": reply.certainty,
                            },
                        }
                    )
                    continue

                if action_type == "FINAL":
                    final_parse = action.get("_final_parse_diagnostics")
                    if isinstance(final_parse, dict):
                        parse_retry_count += int(final_parse.get("retry_count") or 0)
                        final_parse_diagnostics = final_parse
                    final_output, final_consumable, invalid_final_reason = _validate_final_output(
                        action.get("final_output"),
                        state.asked_slots,
                        state.observations,
                    )
                    if not final_consumable:
                        parse_error = True
                        if invalid_final_reason == INVALID_FINAL_PARSE_FALLBACK:
                            parse_error_code = parse_error_code or "parse_error"
                        else:
                            parse_error_code = parse_error_code or "schema_error"
                    logs.append({"turn": turn, "doctor_action": action})
                    termination_reason = "final"
                    break

                invalid_actions += 1
                logs.append({"turn": turn, "doctor_action": action, "event": "invalid_action"})
                if invalid_actions > max_invalid_actions:
                    termination_reason = "invalid_action_limit"
                    break
        except Exception as exc:
            case_status = "failed"
            last_error, timeout_error = _error_code_from_exception(exc)
            termination_reason = termination_reason if termination_reason != "max_turns" else "execution_error"
            logs.append(
                {
                    "turn": state.turn or 0,
                    "event": "case_execution_error",
                    "error_code": last_error,
                    "error_message": str(exc),
                }
            )

        if final_output is None and doctor_kind == "llm":
            # Model never output FINAL during conversation — force one final diagnosis call
            if doctor_kind == "llm":
                adapter_attempts += 1
            forced_action = doctor.next_action(
                minimal_cc=case.info_variants.minimal_cc,
                state=state,
                allowed_slots=allowed_slots,
                must_ask_slots=doctor_must_ask_slots,
                forbidden_slots=list(allowed_slots),  # Forbid all slots to force FINAL
            )
            if forced_action.get("action") == "FINAL":
                final_parse = forced_action.get("_final_parse_diagnostics")
                if isinstance(final_parse, dict):
                    parse_retry_count += int(final_parse.get("retry_count") or 0)
                    final_parse_diagnostics = final_parse
                final_output, final_consumable, invalid_final_reason = _validate_final_output(
                    forced_action.get("final_output"),
                    state.asked_slots,
                    state.observations,
                )
                if not final_consumable:
                    parse_error = True
                    if invalid_final_reason == INVALID_FINAL_PARSE_FALLBACK:
                        parse_error_code = parse_error_code or "parse_error"
                    else:
                        parse_error_code = parse_error_code or "schema_error"

        if final_output is None:
            parse_error = True
            parse_error_code = parse_error_code or "empty_output"
            invalid_final_reason = invalid_final_reason or INVALID_FINAL_PARSE_FALLBACK
            final_output = _fallback_final_output(state.observations)
            final_consumable = False
        else:
            final_output, final_consumable, invalid_final_reason = _validate_final_output(
                final_output,
                state.asked_slots,
                state.observations,
            )
            if not final_consumable:
                parse_error = True
                if invalid_final_reason == INVALID_FINAL_PARSE_FALLBACK:
                    parse_error_code = parse_error_code or "parse_error"
                else:
                    parse_error_code = parse_error_code or "schema_error"

        elapsed_ms = round((time.perf_counter() - case_started) * 1000.0, 2)
        required_domains = (
            rubric.must_ask_svcl_domains
            if rubric.must_ask_svcl_domains
            else derive_domains_from_slots(rubric.must_ask_slots, ont.svcl_map)
        )

        metrics = score_dynamic_case(
            asked_slots=state.asked_slots,
            must_ask_slots=rubric.must_ask_slots,
            required_svcl_domains=required_domains,
            svcl_map=ont.svcl_map,
            final_output=final_output,
            gold_label=case.label,
            gold_ddx_top5=case.gold_ddx_top5,
            ambiguity=case.ambiguity,
        )

        harm_flags = evaluate_avoid_harm(
            final_output=final_output,
            rules=rubric.avoid_harm_rules,
            ambiguity=case.ambiguity,
            asked_slots=state.asked_slots,
            risk_flags=case.risk_flags.model_dump(),
            slot_truth=case.slot_truth,
        )

        rows_by_case[case.case_id] = {
            "case_id": case.case_id,
            "dsm_module": case.dsm_module,
            "label": case.label,
            "ambiguity": case.ambiguity,
            "split": split or "all",
            "case_status": case_status,
            "asked_slots": state.asked_slots,
            "turn_logs": logs,
            "final_output": final_output,
            "scoring_gold_labels": benchmark_gold_labels(case.label, case.gold_ddx_top5, case.ambiguity),
            "metrics": metrics,
            "harm_flags": harm_flags,
            "parse_error": parse_error,
            "parse_retry_count": parse_retry_count,
            "parse_error_code": parse_error_code,
            "raw_parse_diagnostics": raw_parse_diagnostics,
            "final_parse_diagnostics": final_parse_diagnostics,
            "final_consumable": final_consumable,
            "invalid_final_reason": invalid_final_reason,
            "repair_attempted": repair_attempted,
            "repair_succeeded": repair_succeeded,
            "termination_reason": termination_reason,
            "adapter_attempts": adapter_attempts,
            "last_error": last_error,
            "elapsed_ms": elapsed_ms,
            "timeout_error": timeout_error,
        }

    rows = [rows_by_case[case.case_id] for case in all_case_records if case.case_id in rows_by_case]
    if not rows:
        rows = [rows_by_case[case_id] for case_id in existing_rows_by_case if case_id in rows_by_case]

    write_jsonl(output_path, rows)
    artifact_predictions_path = artifact_paths["predictions_jsonl"]
    write_jsonl(artifact_predictions_path, rows)
    resolved_summary_csv = summary_csv or artifact_paths["summary_csv"]
    resolved_table_tex = table_tex or artifact_paths["summary_tex"]
    summary_rows = summarize_rows(rows)
    write_summary(
        rows,
        summary_csv=resolved_summary_csv,
        table_tex=resolved_table_tex,
    )
    write_metrics_artifact(
        rows,
        metrics_json=metrics_json or artifact_paths["metrics_json"],
        task="dynamic",
        predictions_path=artifact_predictions_path,
        run_config={
            "cases_path": str(cases_path),
            "rubrics_path": str(rubrics_path),
            "ontology_dir": str(ontology_dir),
            "seed": seed,
            "max_invalid_actions": max_invalid_actions,
            "doctor_kind": doctor_kind,
            "provider": provider,
            "model": model,
            "endpoint": endpoint,
            "use_cache": use_cache,
            "temperature": temperature,
            "split": split or "all",
            "splits_dir": str(splits_dir),
            "resume_from_case": resume_from_case,
            "rerun_failed_only": rerun_failed_only,
            "max_cases": max_cases,
        },
        summary_rows=summary_rows,
        extra_artifacts={
            "latest_output_jsonl": str(output_path),
            "summary_csv": str(resolved_summary_csv),
            "summary_tex": str(resolved_table_tex),
            "artifact_dir": str(artifact_paths["artifact_dir"]),
        },
    )
    print(f"Dynamic run complete: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dynamic PIB benchmark")
    parser.add_argument("--cases", type=Path, default=Path("data/cases.jsonl"))
    parser.add_argument("--rubrics", type=Path, default=Path("data/rubrics.jsonl"))
    parser.add_argument("--ontology", type=Path, default=Path("ontology"))
    parser.add_argument("--output", type=Path, default=Path("results/dynamic/test_dynamic.jsonl"))
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--max-invalid-actions", type=int, default=2)
    parser.add_argument("--doctor", choices=["dummy", "llm", "ssm", "ssm_a2", "ssm_a3", "ssm_a4"], default="dummy")
    parser.add_argument("--split", choices=["train", "dev", "test", "all"], default="test")
    parser.add_argument("--splits-dir", type=Path, default=Path("data/splits"))
    parser.add_argument("--provider", choices=["openai", "anthropic", "local_llama"], default="openai")
    parser.add_argument("--model", default=None)
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--cache-root", type=Path, default=None)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--summary-csv", type=Path, default=None)
    parser.add_argument("--table-tex", type=Path, default=None)
    parser.add_argument("--metrics-json", type=Path, default=None)
    parser.add_argument("--resume-from-case", default=None)
    parser.add_argument("--rerun-failed-only", action="store_true")
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()

    run_dynamic(
        cases_path=args.cases,
        rubrics_path=args.rubrics,
        ontology_dir=args.ontology,
        output_path=args.output,
        seed=args.seed,
        max_invalid_actions=args.max_invalid_actions,
        doctor_kind=args.doctor,
        split=args.split,
        splits_dir=args.splits_dir,
        summary_csv=args.summary_csv,
        table_tex=args.table_tex,
        metrics_json=args.metrics_json,
        resume_from_case=args.resume_from_case,
        rerun_failed_only=args.rerun_failed_only,
        max_cases=args.max_cases,
        provider=args.provider,
        model=args.model,
        endpoint=args.endpoint,
        cache_root=args.cache_root,
        use_cache=not args.no_cache,
        temperature=args.temperature,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
