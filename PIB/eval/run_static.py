from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from tqdm import tqdm

from agents.doctor_agent import ALL_LABELS
from eval.load import (
    DataValidationError,
    filter_cases_by_ids,
    filter_rubrics_by_ids,
    load_cases,
    load_ontology,
    load_rubrics,
    load_split_ids,
    write_jsonl,
)
from eval.report import (
    default_run_artifacts,
    summarize_rows,
    summarize_static_stage_rows,
    write_metrics_artifact,
    write_static_stage_breakdown,
    write_summary,
)
from eval.scorers.ddx_metrics import benchmark_gold_labels
from eval.scorers.static_metrics import score_static_case
from models.adapters.factory import build_chat_adapter
from models.parsing import JsonParseError, parse_with_retry


def _truth_value_map(case) -> Dict[str, Any]:
    return {k: v.value for k, v in case.slot_truth.items()}


def heuristic_slot_filling(text: str) -> Dict[str, Any]:
    pred: Dict[str, Any] = {}

    if re.search(r"洗手|仪式|反复", text):
        pred["ritual_behavior_present"] = True
    if re.search(r"不想要.*念头|侵入|停不下来", text):
        pred["intrusive_thoughts"] = True
    if re.search(r"外貌|鼻子|脸|难看", text):
        pred["appearance_preoccupation"] = True
    if re.search(r"月经|经前|周期", text):
        pred["menstrual_cycle_link"] = "clear_link"
    if re.search(r"暴怒|发火|愤怒爆发", text):
        pred["anger_outbursts"] = True
    if re.search(r"自伤|伤害自己", text):
        pred["self_harm_ideation"] = True
    if re.search(r"完美|秩序", text):
        pred["perfectionism_trait"] = True
        pred["longstanding_pattern"] = True
    if re.search(r"丧失|离世|去世", text):
        pred["loss_event_present"] = True
    if re.search(r"压力|应激|换岗", text):
        pred["stressor_present"] = True
    if re.search(r"身体|腹痛|疲劳|不适", text):
        pred["somatic_symptom_distress"] = "moderate"
    if re.search(r"影响|受损|效率", text):
        pred.setdefault("impairment_work", "moderate")

    return pred


def heuristic_slot_context(text: str) -> Dict[str, Any]:
    return {"text": text}


def heuristic_ddx(slot_predictions: Dict[str, Any]) -> List[str]:
    if slot_predictions.get("menstrual_cycle_link") == "clear_link":
        return ["PMDD", "BPD", "ADJ", "IED", "OTHER"]
    if slot_predictions.get("appearance_preoccupation") is True:
        return ["BDD", "OCD", "OS_OCRD", "SSD", "OTHER"]
    if slot_predictions.get("intrusive_thoughts") is True and slot_predictions.get("ritual_behavior_present") is True:
        return ["OCD", "OCPD", "BDD", "SSD", "OTHER"]
    if slot_predictions.get("somatic_symptom_distress") in {"moderate", "severe"}:
        return ["SSD", "ADJ", "PMDD", "OCD", "OTHER"]
    if slot_predictions.get("loss_event_present") is True:
        return ["PGD", "ADJ", "BPD", "PMDD", "OTHER"]
    if slot_predictions.get("stressor_present") is True:
        return ["ADJ", "SSD", "PGD", "PMDD", "OTHER"]
    if slot_predictions.get("anger_outbursts") is True:
        return ["IED", "BPD", "ADJ", "PMDD", "OTHER"]
    if slot_predictions.get("self_harm_ideation") is True:
        return ["BPD", "IED", "ADJ", "PMDD", "OTHER"]
    if slot_predictions.get("perfectionism_trait") is True:
        return ["OCPD", "OCD", "ADJ", "BDD", "OTHER"]
    return ["OTHER", "ADJ", "SSD", "PMDD", "OCD"]


def heuristic_ddx_context(slot_predictions: Dict[str, Any]) -> Dict[str, Any]:
    return {"slot_predictions": dict(slot_predictions)}


def _normalize_slot_predictions(raw: Dict[str, Any], allowed_slots: set[str]) -> Dict[str, Any]:
    payload = raw.get("slot_predictions", raw)
    if not isinstance(payload, dict):
        raise JsonParseError("slot_predictions must be a JSON object")
    return {
        str(slot_id): value
        for slot_id, value in payload.items()
        if isinstance(slot_id, str) and slot_id in allowed_slots
    }


def _normalize_diagnosis_topk(raw: Dict[str, Any], allowed_labels: set[str]) -> List[str]:
    payload = raw.get("diagnosis_topk")
    if not isinstance(payload, list):
        raise JsonParseError("diagnosis_topk must be a JSON list")

    labels: List[str] = []
    for item in payload:
        if isinstance(item, dict):
            label = item.get("label")
        else:
            label = item
        if isinstance(label, str) and label in allowed_labels and label not in labels:
            labels.append(label)

    if not labels:
        raise JsonParseError("diagnosis_topk must contain at least one valid label")
    return labels[:5]


def _call_llm_json(adapter, system_prompt: str, user_prompt: str, temperature: float) -> Dict[str, Any]:
    def _call(prompt: str) -> str:
        return adapter.complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )

    return parse_with_retry(_call, user_prompt, max_retries=2)


def _build_slot_prompt(text: str, allowed_slots: List[str]) -> str:
    return (
        "任务：从输入文本抽取结构化 slot。只输出 JSON 对象，结构为 "
        '{"slot_predictions":{"slot_id":"value"}}。\n'
        f"输入文本:\n{text}\n"
        f"允许的 slot_id 列表:\n{json.dumps(allowed_slots, ensure_ascii=False)}\n"
        "不要输出任何非 JSON 文本。"
    )


def _build_ddx_prompt(slot_predictions: Dict[str, Any], allowed_labels: List[str]) -> str:
    return (
        "任务：基于已抽取 slots 给出鉴别诊断 top-k。只输出 JSON，结构为 "
        '{"diagnosis_topk":[{"label":"OCD","confidence":0.6}]}。\n'
        f"slot_predictions:\n{json.dumps(slot_predictions, ensure_ascii=False, sort_keys=True)}\n"
        f"允许的标签:\n{json.dumps(allowed_labels, ensure_ascii=False)}\n"
        "必须包含 OTHER。不要输出任何非 JSON 文本。"
    )


def run_static(
    cases_path: Path,
    rubrics_path: Path,
    ontology_dir: Path,
    output_path: Path,
    input_variant: str = "self_report",
    oracle_slots: bool = False,
    mode: str = "heuristic",
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
    stage_breakdown_csv: Path | None = None,
    stage_breakdown_tex: Path | None = None,
    metrics_json: Path | None = None,
) -> None:
    try:
        ont = load_ontology(ontology_dir)
        case_records = load_cases(cases_path, ont)
        rubric_records = load_rubrics(rubrics_path, ont, [c.case_id for c in case_records])
    except DataValidationError as exc:
        raise SystemExit(f"Validation failed before run: {exc}")

    if split is not None:
        selected_ids = load_split_ids(splits_dir, split)
        case_records = filter_cases_by_ids(case_records, selected_ids)
        rubric_records = filter_rubrics_by_ids(rubric_records, selected_ids)

    rubric_by_case = {r.case_id: r for r in rubric_records}
    allowed_slots = sorted(ont.slot_ids)
    allowed_slot_set = set(allowed_slots)
    allowed_labels = [label for label in ALL_LABELS if label in ont.labels]
    allowed_label_set = set(allowed_labels)
    artifact_paths = default_run_artifacts("static", output_path)
    adapter = None
    if mode == "llm":
        adapter = build_chat_adapter(
            provider=provider,
            model=model,
            endpoint=endpoint,
            cache_root=cache_root,
            use_cache=use_cache,
        )
    rows = []

    for case in tqdm(case_records, desc="static"):
        text = getattr(case.info_variants, input_variant)
        truth_values = _truth_value_map(case)
        slot_parse_error = False
        ddx_parse_error = False

        if oracle_slots:
            slot_predictions = truth_values.copy()
        elif mode == "llm":
            try:
                raw_slot_output = _call_llm_json(
                    adapter=adapter,
                    system_prompt="你是精神科诊断访谈助手，只能输出 JSON。",
                    user_prompt=_build_slot_prompt(text, allowed_slots),
                    temperature=temperature,
                )
                slot_predictions = _normalize_slot_predictions(raw_slot_output, allowed_slot_set)
            except Exception:
                slot_parse_error = True
                slot_predictions = {}
        else:
            slot_predictions = heuristic_slot_filling(heuristic_slot_context(text)["text"])

        if mode == "llm":
            try:
                raw_ddx_output = _call_llm_json(
                    adapter=adapter,
                    system_prompt="你是精神科诊断访谈助手，只能输出 JSON。",
                    user_prompt=_build_ddx_prompt(slot_predictions, allowed_labels),
                    temperature=temperature,
                )
                pred_labels = _normalize_diagnosis_topk(raw_ddx_output, allowed_label_set)
            except Exception:
                ddx_parse_error = True
                pred_labels = heuristic_ddx(slot_predictions)
        else:
            pred_labels = heuristic_ddx(heuristic_ddx_context(slot_predictions)["slot_predictions"])
        required_slots = rubric_by_case[case.case_id].must_ask_slots

        metrics = score_static_case(
            gold_label=case.label,
            gold_ddx_top5=case.gold_ddx_top5,
            ambiguity=case.ambiguity,
            pred_labels=pred_labels,
            slot_predictions=slot_predictions,
            slot_truth=truth_values,
            required_slots=required_slots,
        )
        metrics.update(
            {
                "slot_stage_error_rate": float(slot_parse_error),
                "slot_stage_success_rate": float(not slot_parse_error),
                "ddx_stage_error_rate": float(ddx_parse_error),
                "ddx_stage_success_rate": float(not ddx_parse_error),
                "predicted_slot_count": float(len(slot_predictions)),
                "diagnosis_count": float(len(pred_labels)),
            }
        )

        rows.append(
            {
                "case_id": case.case_id,
                "dsm_module": case.dsm_module,
                "label": case.label,
                "ambiguity": case.ambiguity,
                "input_variant": input_variant,
                "split": split or "all",
                "slot_predictions": slot_predictions,
                "diagnosis_topk": pred_labels,
                "scoring_gold_labels": benchmark_gold_labels(case.label, case.gold_ddx_top5, case.ambiguity),
                "metrics": metrics,
                "harm_flags": [],
                "slot_parse_error": slot_parse_error,
                "ddx_parse_error": ddx_parse_error,
                "mode": mode,
            }
        )

    write_jsonl(output_path, rows)
    artifact_predictions_path = artifact_paths["predictions_jsonl"]
    write_jsonl(artifact_predictions_path, rows)
    resolved_summary_csv = summary_csv or artifact_paths["summary_csv"]
    resolved_table_tex = table_tex or artifact_paths["summary_tex"]
    resolved_stage_breakdown_csv = stage_breakdown_csv or artifact_paths["stage_breakdown_csv"]
    resolved_stage_breakdown_tex = stage_breakdown_tex or artifact_paths["stage_breakdown_tex"]

    summary_rows = summarize_rows(rows)
    stage_rows = summarize_static_stage_rows(rows)
    write_summary(
        rows,
        summary_csv=resolved_summary_csv,
        table_tex=resolved_table_tex,
    )
    write_static_stage_breakdown(
        rows,
        output_csv=resolved_stage_breakdown_csv,
        output_tex=resolved_stage_breakdown_tex,
    )
    write_metrics_artifact(
        rows,
        metrics_json=metrics_json or artifact_paths["metrics_json"],
        task="static",
        predictions_path=artifact_predictions_path,
        run_config={
            "cases_path": str(cases_path),
            "rubrics_path": str(rubrics_path),
            "ontology_dir": str(ontology_dir),
            "input_variant": input_variant,
            "oracle_slots": oracle_slots,
            "mode": mode,
            "provider": provider,
            "model": model,
            "endpoint": endpoint,
            "use_cache": use_cache,
            "temperature": temperature,
            "split": split or "all",
            "splits_dir": str(splits_dir),
        },
        summary_rows=summary_rows,
        stage_rows=stage_rows,
        extra_artifacts={
            "latest_output_jsonl": str(output_path),
            "summary_csv": str(resolved_summary_csv),
            "summary_tex": str(resolved_table_tex),
            "stage_breakdown_csv": str(resolved_stage_breakdown_csv),
            "stage_breakdown_tex": str(resolved_stage_breakdown_tex),
            "artifact_dir": str(artifact_paths["artifact_dir"]),
        },
    )
    print(f"Static run complete: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run static PIB benchmark")
    parser.add_argument("--cases", type=Path, default=Path("data/cases.jsonl"))
    parser.add_argument("--rubrics", type=Path, default=Path("data/rubrics.jsonl"))
    parser.add_argument("--ontology", type=Path, default=Path("ontology"))
    parser.add_argument("--output", type=Path, default=Path("results/static/test_static.jsonl"))
    parser.add_argument("--input-variant", type=str, default="self_report")
    parser.add_argument("--oracle-slots", action="store_true")
    parser.add_argument("--mode", choices=["heuristic", "llm"], default="heuristic")
    parser.add_argument("--split", choices=["train", "dev", "test"], default="test")
    parser.add_argument("--splits-dir", type=Path, default=Path("data/splits"))
    parser.add_argument("--provider", choices=["openai", "anthropic", "local_llama"], default="openai")
    parser.add_argument("--model", default=None)
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--cache-root", type=Path, default=None)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--summary-csv", type=Path, default=None)
    parser.add_argument("--table-tex", type=Path, default=None)
    parser.add_argument("--stage-breakdown-csv", type=Path, default=None)
    parser.add_argument("--stage-breakdown-tex", type=Path, default=None)
    parser.add_argument("--metrics-json", type=Path, default=None)
    args = parser.parse_args()

    run_static(
        cases_path=args.cases,
        rubrics_path=args.rubrics,
        ontology_dir=args.ontology,
        output_path=args.output,
        input_variant=args.input_variant,
        oracle_slots=args.oracle_slots,
        mode=args.mode,
        split=args.split,
        splits_dir=args.splits_dir,
        summary_csv=args.summary_csv,
        table_tex=args.table_tex,
        stage_breakdown_csv=args.stage_breakdown_csv,
        stage_breakdown_tex=args.stage_breakdown_tex,
        metrics_json=args.metrics_json,
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
