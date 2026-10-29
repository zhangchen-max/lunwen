from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List

from eval.constants import (
    BENCHMARK_VERSION,
    DATASET_VERSION,
    NO_ORACLE_POLICY_VERSION,
    REQUIRED_DYNAMIC_MAX_TURNS,
    REQUIRED_OS_OCRD_SUBTYPES_COUNT,
    REQUIRED_SLOT_COUNT,
    SCORING_POLICY_VERSION,
)
from eval.load import read_jsonl


REQUIRED_REPORT_COLUMNS = [
    "slot_count",
    "dynamic_max_turns",
    "os_ocrd_subtypes_count",
    "execution_success_rate",
    "must_ask_hit_rate",
    "svcl_coverage",
    "turns",
    "top5_cov",
    "harm_flags_count",
    "final_consumable_rate",
    "parse_error_rate",
    "invalid_final_rate",
    "timeout_count",
    "adapter_error_count",
    "slot_stage_error_rate",
    "slot_stage_success_rate",
    "ddx_stage_error_rate",
    "ddx_stage_success_rate",
    "predicted_slot_count",
    "diagnosis_count",
]

STATIC_STAGE_BREAKDOWN_COLUMNS = [
    "slot_stage_error_rate",
    "slot_stage_success_rate",
    "ddx_stage_error_rate",
    "ddx_stage_success_rate",
    "predicted_slot_count",
    "diagnosis_count",
    "required_slot_coverage",
    "slot_exact_match",
    "top1_acc",
    "top3_cov",
    "top5_cov",
]

SUM_REPORT_COLUMNS = {"timeout_count", "adapter_error_count"}


def _to_float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _flatten_result_row(row: Dict[str, Any]) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "case_id": row.get("case_id"),
        "dsm_module": row.get("dsm_module"),
        "label": row.get("label"),
        "ambiguity": row.get("ambiguity"),
        "input_variant": row.get("input_variant"),
        "mode": row.get("mode"),
        "slot_count": float(REQUIRED_SLOT_COUNT),
        "dynamic_max_turns": float(REQUIRED_DYNAMIC_MAX_TURNS),
        "os_ocrd_subtypes_count": float(REQUIRED_OS_OCRD_SUBTYPES_COUNT),
    }

    metrics = row.get("metrics", {})
    if isinstance(metrics, dict):
        for k, v in metrics.items():
            numeric = _to_float_or_none(v)
            if numeric is not None:
                rec[k] = numeric

    must_ask = _to_float_or_none(rec.get("must_ask_hit_rate"))
    svcl_cov = _to_float_or_none(rec.get("svcl_coverage"))
    if svcl_cov is None:
        svcl_cov = _to_float_or_none(rec.get("svcl_domain_coverage"))
    if svcl_cov is None:
        svcl_cov = _to_float_or_none(rec.get("required_slot_coverage"))
    turns = _to_float_or_none(rec.get("turns"))
    top5_cov = _to_float_or_none(rec.get("top5_cov"))

    harm_flags = row.get("harm_flags", [])
    harm_flags_count = float(len(harm_flags) if isinstance(harm_flags, list) else 0)
    parse_error = 1.0 if row.get("parse_error") else 0.0
    final_consumable = 1.0 if row.get("final_consumable") else 0.0
    invalid_final = 1.0 if row.get("invalid_final_reason") not in (None, "", "none") else 0.0
    execution_success = 1.0 if row.get("case_status", "completed") == "completed" else 0.0
    timeout_count = 1.0 if row.get("timeout_error") else 0.0
    adapter_error_count = 1.0 if row.get("last_error") and not row.get("timeout_error") else 0.0

    rec["execution_success_rate"] = execution_success
    rec["must_ask_hit_rate"] = must_ask
    rec["svcl_coverage"] = svcl_cov
    rec["turns"] = turns
    rec["top5_cov"] = top5_cov
    rec["harm_flags_count"] = harm_flags_count
    rec["final_consumable_rate"] = final_consumable
    rec["parse_error_rate"] = parse_error
    rec["invalid_final_rate"] = invalid_final
    rec["timeout_count"] = timeout_count
    rec["adapter_error_count"] = adapter_error_count

    # P0-2: 三列指标拆分，正面回应 R1-3 / R2-1 / R4-1（"baseline 0% 归因于 JSON 失败"）
    # Format Compliance = 1 - parse_error_rate
    pec = _to_float_or_none(rec.get("parse_error_rate"))
    rec["format_compliance"] = (1.0 - pec) if pec is not None else None
    # Dx-Correct|Valid: 仅在格式合规(final_consumable)样本上计 top1；非合规样本不写入该列，
    # 聚合时即自动只对合规样本求均值，从而分离"输出格式"与"诊断能力"两个维度。
    top1 = _to_float_or_none(rec.get("top1_acc"))
    if row.get("final_consumable"):
        rec["dx_correct_valid"] = top1
    # Dx-Correct unconstrained: 所有样本（含 JSON 解析失败但 fallback 仍给出诊断）计 top1，
    # 反映模型底层诊断能力，不因结构化输出失败而被错判为 0%。
    rec["dx_correct_unconstrained"] = top1

    return rec


def _numeric_keys(rows: List[Dict[str, Any]]) -> List[str]:
    blocked = {"case_id", "dsm_module", "label", "ambiguity"}
    keys = set(REQUIRED_REPORT_COLUMNS)
    for row in rows:
        for k, v in row.items():
            if k in blocked:
                continue
            if isinstance(v, (int, float)):
                keys.add(k)
    return sorted(keys)


def _mean_or_nan(values: List[float]) -> float:
    if not values:
        return float("nan")
    return float(mean(values))


def _summarize_group(rows: List[Dict[str, Any]], slice_name: str, slice_value: str) -> Dict[str, Any]:
    numeric = _numeric_keys(rows)
    rec: Dict[str, Any] = {
        "slice": slice_name,
        "slice_value": slice_value,
        "n": len(rows),
    }
    for key in numeric:
        vals = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]
        if key in SUM_REPORT_COLUMNS:
            rec[key] = float(sum(vals)) if vals else 0.0
        else:
            rec[key] = _mean_or_nan(vals)
    return rec


def summarize_rows(rows: Iterable[Dict[str, Any]], group_keys: List[str] | None = None) -> List[Dict[str, Any]]:
    flat = [_flatten_result_row(r) for r in rows]
    if not flat:
        return []

    summaries: List[Dict[str, Any]] = []
    summaries.append(_summarize_group(flat, "overall", "all"))

    for key in group_keys or ["dsm_module", "label", "ambiguity"]:
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for row in flat:
            value = str(row.get(key))
            buckets.setdefault(value, []).append(row)
        for value, part in sorted(buckets.items(), key=lambda x: x[0]):
            summaries.append(_summarize_group(part, key, value))

    return summaries


def summarize_static_stage_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary_rows = summarize_rows(
        rows,
        group_keys=["label", "ambiguity", "input_variant", "mode"],
    )
    stage_rows: List[Dict[str, Any]] = []
    for row in summary_rows:
        stage_row = {
            "slice": row["slice"],
            "slice_value": row["slice_value"],
            "n": row["n"],
        }
        for key in STATIC_STAGE_BREAKDOWN_COLUMNS:
            stage_row[key] = row.get(key, float("nan"))
        stage_rows.append(stage_row)
    return stage_rows


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted({k for row in rows for k in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_latex(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("% empty summary\n", encoding="utf-8")
        return

    if fieldnames is None:
        fieldnames = ["slice", "slice_value", "n"] + sorted(
            k for k in rows[0].keys() if k not in {"slice", "slice_value", "n"}
        )

    lines = [
        "\\begin{tabular}{" + "l" * len(fieldnames) + "}",
        "\\hline",
        " & ".join(fieldnames) + " \\\\",
        "\\hline",
    ]
    for row in rows:
        vals = []
        for key in fieldnames:
            v = row.get(key, "")
            if isinstance(v, float):
                vals.append(f"{v:.4f}")
            else:
                vals.append(str(v))
        lines.append(" & ".join(vals) + " \\\\")
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_artifact_dir(output_path: Path) -> Path:
    base_dir = output_path.with_suffix("")
    run_index = 1
    while (base_dir / f"run_{run_index:03d}").exists():
        run_index += 1
    return base_dir / f"run_{run_index:03d}"


def default_run_artifacts(task: str, output_path: Path) -> Dict[str, Path]:
    artifact_dir = default_artifact_dir(output_path)
    artifacts = {
        "artifact_dir": artifact_dir,
        "predictions_jsonl": artifact_dir / "predictions.jsonl",
        "summary_csv": artifact_dir / "summary.csv",
        "summary_tex": artifact_dir / "summary.tex",
        "metrics_json": artifact_dir / "metrics.json",
    }
    if task == "static":
        artifacts["stage_breakdown_csv"] = artifact_dir / "stage_breakdown.csv"
        artifacts["stage_breakdown_tex"] = artifact_dir / "stage_breakdown.tex"
    return artifacts


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {key: _sanitize_json(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    return value


def _group_summary_rows(summary_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, Any] = {}
    overall = next((row for row in summary_rows if row.get("slice") == "overall"), None)
    if overall is not None:
        grouped["overall"] = overall
    by_slice: Dict[str, Dict[str, Any]] = {}
    for row in summary_rows:
        slice_name = str(row.get("slice"))
        slice_value = str(row.get("slice_value"))
        if slice_name == "overall":
            continue
        by_slice.setdefault(slice_name, {})[slice_value] = row
    grouped["by_slice"] = by_slice
    return grouped


def _release_manifest() -> Dict[str, Any]:
    manifest_path = Path(__file__).resolve().parents[1] / "release" / "benchmark_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    payload["manifest_path"] = str(manifest_path)
    return payload


def write_summary(rows: Iterable[Dict[str, Any]], summary_csv: Path, table_tex: Path | None = None) -> None:
    summary_rows = summarize_rows(rows)
    _write_csv(summary_csv, summary_rows)
    if table_tex is not None:
        _write_latex(table_tex, summary_rows)
    return None


def write_static_stage_breakdown(
    rows: Iterable[Dict[str, Any]],
    output_csv: Path,
    output_tex: Path | None = None,
) -> None:
    stage_rows = summarize_static_stage_rows(rows)
    _write_csv(output_csv, stage_rows)
    if output_tex is not None:
        _write_latex(
            output_tex,
            stage_rows,
            fieldnames=["slice", "slice_value", "n"] + STATIC_STAGE_BREAKDOWN_COLUMNS,
        )


def write_metrics_artifact(
    rows: Iterable[Dict[str, Any]],
    metrics_json: Path,
    task: str,
    predictions_path: Path,
    run_config: Dict[str, Any],
    summary_rows: List[Dict[str, Any]] | None = None,
    stage_rows: List[Dict[str, Any]] | None = None,
    extra_artifacts: Dict[str, str] | None = None,
) -> None:
    rows = list(rows)
    summary_rows = summary_rows if summary_rows is not None else summarize_rows(rows)
    manifest = _release_manifest()
    payload: Dict[str, Any] = {
        "task": task,
        "n_cases": len(rows),
        "release": {
            "benchmark_version": BENCHMARK_VERSION,
            "dataset_version": DATASET_VERSION,
            "scoring_policy_version": SCORING_POLICY_VERSION,
            "no_oracle_policy_version": NO_ORACLE_POLICY_VERSION,
            "dataset_hash_sha256": manifest.get("dataset_hash_sha256"),
            "scoring_hash_sha256": manifest.get("scoring_hash_sha256"),
            "cases_sha256": manifest.get("cases_sha256"),
            "rubrics_sha256": manifest.get("rubrics_sha256"),
            "splits_sha256": manifest.get("splits_sha256"),
            "manifest_path": manifest.get("manifest_path"),
        },
        "run_config": run_config,
        "artifacts": {
            "predictions_jsonl": str(predictions_path),
            **(extra_artifacts or {}),
        },
        "summary": _group_summary_rows(summary_rows),
    }
    if stage_rows is not None:
        payload["static_stage_breakdown"] = _group_summary_rows(stage_rows)

    metrics_json.parent.mkdir(parents=True, exist_ok=True)
    metrics_json.write_text(
        json.dumps(_sanitize_json(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_summary_from_jsonl(input_jsonl: Path, summary_csv: Path, table_tex: Path | None = None) -> None:
    rows = read_jsonl(input_jsonl)
    write_summary(rows, summary_csv=summary_csv, table_tex=table_tex)


def write_static_stage_breakdown_from_jsonl(
    input_jsonl: Path,
    output_csv: Path,
    output_tex: Path | None = None,
) -> None:
    rows = read_jsonl(input_jsonl)
    write_static_stage_breakdown(rows, output_csv=output_csv, output_tex=output_tex)
