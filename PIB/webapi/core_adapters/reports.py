from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

from eval import load as eval_load
from webapi import db

REPO_ROOT = Path(__file__).resolve().parents[2]
PURE_BASELINES_PATH = Path('results/reports/pure_baselines.csv')
GUIDED_BASELINES_PATH = Path('results/reports/guided_llm_baselines.csv')
DEPRECATED_RESULTS_PATH = Path('results/reports/deprecated_results.json')

PREFERRED_METRIC_KEYS = [
    'execution_success_rate',
    'action_schema_valid_rate',
    'final_consumable_rate',
    'parse_error_rate',
    'invalid_final_rate',
    'parse_retry_count',
    'timeout_count',
    'bridge_failure_count',
    'adapter_error_count',
    'top1_acc',
    'top3_cov',
    'top5_cov',
    'must_ask_hit_rate',
    'svcl_coverage',
    'turns',
    'harm_flags_count',
    'oracle_final_top1_acc',
    'oracle_final_top3_cov',
    'oracle_final_top5_cov',
]

METRIC_LABELS = {
    'execution_success_rate': 'Execution Success Rate',
    'action_schema_valid_rate': 'Action Schema Valid Rate',
    'final_consumable_rate': 'Final Consumable Rate',
    'parse_error_rate': 'Parse Error Rate',
    'invalid_final_rate': 'Invalid Final Rate',
    'parse_retry_count': 'Parse Retry Count',
    'timeout_count': 'Timeout Count',
    'bridge_failure_count': 'Bridge Failure Count',
    'adapter_error_count': 'Adapter Error Count',
    'top1_acc': 'Top-1 Accuracy',
    'top3_cov': 'Top-3 Coverage',
    'top5_cov': 'Top-5 Coverage',
    'must_ask_hit_rate': 'Must-Ask Hit Rate',
    'svcl_coverage': 'SVCL Coverage',
    'turns': 'Turns',
    'harm_flags_count': 'Harm Flags Count',
    'strict_top1_acc': 'Strict Top-1 Accuracy',
    'strict_top5_cov': 'Strict Top-5 Coverage',
    'oracle_final_top1_acc': 'Oracle-Final Top-1 Accuracy',
    'oracle_final_top3_cov': 'Oracle-Final Top-3 Coverage',
    'oracle_final_top5_cov': 'Oracle-Final Top-5 Coverage',
}

FAILURE_BUCKETS = [
    'top1_wrong',
    'top3_miss',
    'must_ask_miss',
    'svcl_coverage_gap',
    'safety_flagged',
    'parse_or_execution_error',
]

PROTOCOL_FAILURE_BUCKETS = [
    'parse_error',
    'invalid_final',
    'repeat_slot',
    'invalid_slot_id',
    'timeout',
    'fallback_other',
]

FAILURE_SOURCES = [
    'bridge',
    'protocol',
    'capability',
    'clean',
]


class SummaryProjectionError(Exception):
    pass


class SliceProjectionError(Exception):
    pass


class CaseListProjectionError(Exception):
    pass


class CaseProjectionError(Exception):
    pass


class RunNotReadyError(Exception):
    pass


class CaseNotFoundError(Exception):
    pass


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None


def _safe_json_loads(payload: str | None) -> dict[str, Any] | None:
    if not payload:
        return None
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _safe_read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def _safe_read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return rows


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip() not in {'', '—'}:
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _metric_mean(values: Iterable[float | None]) -> float | None:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return None
    return float(fmean(numeric))


def _overall_metrics_from_payload(metrics_payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[tuple[str, float]] = []

    def collect(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                numeric = _to_float(value)
                if numeric is not None:
                    candidates.append((key, numeric))

    summary = metrics_payload.get('summary')
    if isinstance(summary, dict):
        overall = summary.get('overall')
        if isinstance(overall, dict):
            collect(overall)
    overall = metrics_payload.get('overall')
    if isinstance(overall, dict):
        collect(overall)
    metrics = metrics_payload.get('metrics')
    if isinstance(metrics, dict):
        collect(metrics)
    collect(metrics_payload)

    dedup: dict[str, float] = {}
    for key, numeric in candidates:
        dedup.setdefault(key, numeric)

    ordered_keys = [key for key in PREFERRED_METRIC_KEYS if key in dedup] + [
        key
        for key in dedup.keys()
        if key not in PREFERRED_METRIC_KEYS and key not in {'n', 'slot_count', 'dynamic_max_turns', 'os_ocrd_subtypes_count', 'gold_accept_set_size'}
    ]
    return [
        {
            'key': key,
            'label': METRIC_LABELS.get(key, key),
            'value': dedup[key],
            'unit': 'ratio' if any(token in key for token in ['acc', 'cov', 'rate']) else 'count',
        }
        for key in ordered_keys
    ]


def _metric_cards_from_mapping(metric_values: dict[str, float | int | None], ordered_keys: list[str] | None = None) -> list[dict[str, Any]]:
    keys = ordered_keys or list(metric_values.keys())
    cards: list[dict[str, Any]] = []
    for key in keys:
        if key not in metric_values:
            continue
        value = metric_values[key]
        numeric = _to_float(value)
        if numeric is None:
            continue
        cards.append(
            {
                'key': key,
                'label': METRIC_LABELS.get(key, key),
                'value': numeric,
                'unit': 'ratio' if any(token in key for token in ['acc', 'cov', 'rate']) else 'count',
            }
        )
    return cards


def _baseline_metric_row(current_metrics: dict[str, float], pure_row: dict[str, str] | None, guided_row: dict[str, str] | None) -> list[dict[str, Any]]:
    keys = list(current_metrics.keys())
    rows: list[dict[str, Any]] = []
    for key in keys:
        current_value = current_metrics[key]
        pure_value = _to_float(pure_row.get(key)) if pure_row else None
        guided_value = _to_float(guided_row.get(key)) if guided_row else None
        rows.append(
            {
                'metric_key': key,
                'current_value': current_value,
                'pure_baseline_value': pure_value,
                'guided_baseline_value': guided_value,
                'delta_vs_pure': (current_value - pure_value) if pure_value is not None else None,
                'delta_vs_guided': (current_value - guided_value) if guided_value is not None else None,
            }
        )
    return rows


def _pick_pure_baseline(run_row: db.RunRegistryRow, rows: list[dict[str, str]]) -> tuple[dict[str, str] | None, list[str]]:
    warnings: list[str] = []
    matched = [
        row for row in rows
        if row.get('task') == run_row.run_type and row.get('split') == run_row.split_name and row.get('status') == 'active'
    ]
    if not matched:
        warnings.append('No matching baseline row found for current run.')
        return None, warnings
    return matched[0], warnings


def _pick_guided_baseline(run_row: db.RunRegistryRow, rows: list[dict[str, str]]) -> tuple[dict[str, str] | None, list[str]]:
    warnings: list[str] = []
    exact = [
        row for row in rows
        if row.get('task') == run_row.run_type and row.get('status') == 'reported_separately'
    ]
    if not exact:
        warnings.append('No guided baseline row found for current run.')
        return None, warnings
    return exact[0], warnings


def _deprecated_warnings(repo_root: Path) -> list[str]:
    payload = _safe_read_json(repo_root / DEPRECATED_RESULTS_PATH)
    if not payload:
        return []
    deprecated = payload.get('deprecated_results', [])
    if not deprecated:
        return []
    return [f"{len(deprecated)} deprecated benchmark result artifacts are present and excluded from baseline matching."]


def _read_tail_text(path: Path | None, *, max_chars: int = 4000) -> str:
    if path is None or not path.exists():
        return ''
    try:
        return path.read_text(encoding='utf-8')[-max_chars:]
    except OSError:
        return ''


def _classify_bridge_failure(run_row: db.RunRegistryRow, repo_root: Path) -> dict[str, Any]:
    error_summary = _safe_json_loads(run_row.error_summary_json)
    if not error_summary:
        return {
            'bridge_failure': False,
            'timeout': False,
            'provider_unavailable': False,
            'transport_failure': False,
            'message': None,
        }

    stderr_path = error_summary.get('stderr_path')
    stdout_path = error_summary.get('stdout_path')
    stderr_tail = _read_tail_text(repo_root / stderr_path) if isinstance(stderr_path, str) else ''
    stdout_tail = _read_tail_text(repo_root / stdout_path) if isinstance(stdout_path, str) else ''
    text = '\n'.join(
        part for part in [
            str(error_summary.get('message', '')),
            stderr_tail,
            stdout_tail,
        ]
        if part
    ).lower()
    timeout = 'timeout' in text or 'timed out' in text
    provider_unavailable = any(token in text for token in ['api key', 'provider unavailable', '401', '403', 'connection refused'])
    transport_failure = any(token in text for token in ['httpconnection', 'transport', 'urlopen error', 'connection reset', 'connection aborted'])
    bridge_failure = timeout or provider_unavailable or transport_failure
    return {
        'bridge_failure': bridge_failure,
        'timeout': timeout,
        'provider_unavailable': provider_unavailable,
        'transport_failure': transport_failure,
        'message': error_summary.get('message'),
    }


def _load_release_casebank(repo_root: Path, split_name: str) -> tuple[list[Any], dict[str, Any], dict[str, Any], Any]:
    ontology = eval_load.load_ontology(repo_root / 'ontology', repo_root / 'pib_config.yaml')
    cases = eval_load.load_cases(repo_root / 'data' / 'cases.jsonl', ontology)
    split_ids = set(eval_load.load_split_ids(repo_root / 'data' / 'splits', split_name))
    case_by_id = {case.case_id: case for case in cases}
    rubrics = eval_load.load_rubrics(repo_root / 'data' / 'rubrics.jsonl', ontology, case_by_id.keys())
    rubric_by_id = {rubric.case_id: rubric for rubric in rubrics}
    return [case for case in cases if case.case_id in split_ids], case_by_id, rubric_by_id, ontology


def _find_prediction_rows(results_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    candidates: list[Path] = []
    direct = results_root / 'predictions.jsonl'
    if direct.exists():
        candidates.append(direct)
    for pattern in ('*predictions*.jsonl',):
        for path in sorted(results_root.glob(pattern)):
            if path not in candidates and path.is_file():
                candidates.append(path)
    if not candidates:
        warnings.append('prediction artifacts missing')
        return [], warnings
    for candidate in candidates:
        rows = _safe_read_jsonl(candidate)
        if rows:
            return rows, warnings
    warnings.append('prediction artifacts unreadable')
    return [], warnings


def _find_replay_rows(results_root: Path) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    for pattern in ('turn_logs.jsonl', '*turn*log*.jsonl', '*replay*.jsonl'):
        for path in sorted(results_root.glob(pattern)):
            if path not in candidates and path.is_file():
                candidates.append(path)
    for candidate in candidates:
        rows = _safe_read_jsonl(candidate)
        if rows:
            return rows
    return []


def _top5_hit(pred_labels: list[str], gold_label: str) -> bool:
    return gold_label in pred_labels[:5] if pred_labels else False


def _protocol_placeholder_final(final_output: Any) -> bool:
    if not isinstance(final_output, dict):
        return False
    justification = final_output.get('justification')
    if not isinstance(justification, list):
        return False
    for item in justification:
        if isinstance(item, dict) and '模型未能输出有效 FINAL' in str(item.get('claim', '')):
            return True
    return False


def _extract_replay_logs(row: dict[str, Any], replay_row: dict[str, Any] | None = None) -> list[dict[str, Any]] | None:
    candidate_logs = row.get('turn_logs')
    if isinstance(candidate_logs, list):
        return candidate_logs
    if isinstance(replay_row, dict):
        replay_logs = replay_row.get('turn_logs')
        if isinstance(replay_logs, list):
            return replay_logs
    return None


def _repeat_slot_count(replay_logs: list[dict[str, Any]] | None, termination_reason: Any) -> int:
    if isinstance(replay_logs, list) and replay_logs:
        seen: Counter[str] = Counter()
        repeated = 0
        for turn in replay_logs:
            if not isinstance(turn, dict):
                continue
            doctor_action = turn.get('doctor_action', {})
            if not isinstance(doctor_action, dict):
                continue
            slot_id = doctor_action.get('slot_id')
            if not isinstance(slot_id, str) or not slot_id:
                continue
            seen[slot_id] += 1
            if seen[slot_id] > 1:
                repeated += 1
        if repeated > 0:
            return repeated
    return 1 if termination_reason == 'repeat_slot' else 0


def _invalid_slot_count(termination_reason: Any) -> int:
    return 1 if termination_reason == 'invalid_slot_id_limit' else 0


def _fallback_other_reason(parse_error: bool, placeholder_final: bool) -> str:
    if parse_error and placeholder_final:
        return 'parse_error_default_other'
    if placeholder_final:
        return 'invalid_final_placeholder'
    return 'none'


def _adapter_latency_ms(row: dict[str, Any], run_row: db.RunRegistryRow) -> float | None:
    candidate_keys = (
        'adapter_latency_ms',
        'latency_ms',
        'request_latency_ms',
        'relay_latency_ms',
        'duration_ms',
    )
    for key in candidate_keys:
        numeric = _to_float(row.get(key))
        if numeric is not None:
            return numeric

    error_summary = _safe_json_loads(run_row.error_summary_json)
    if error_summary:
        for key in candidate_keys:
            numeric = _to_float(error_summary.get(key))
            if numeric is not None:
                return numeric
    return None


def _row_bridge_state(row: dict[str, Any], run_bridge_info: dict[str, Any], protocol_state: dict[str, Any]) -> dict[str, Any]:
    last_error = str(row.get('last_error') or '').lower()
    timeout_error = bool(
        row.get('timeout_error')
        or row.get('relay_timeout')
        or protocol_state.get('termination_reason') == 'timeout'
        or 'timed out' in last_error
        or 'timeout' in last_error
    )
    provider_unavailable = bool(
        row.get('provider_unavailable')
        or 'provider unavailable' in last_error
        or 'api key' in last_error
        or '401' in last_error
        or '403' in last_error
        or 'connection refused' in last_error
    )
    transport_failure = bool(
        row.get('transport_failure')
        or 'transport_error' in last_error
        or 'connection reset' in last_error
        or 'connection aborted' in last_error
        or 'transport' in last_error
    )
    adapter_error = bool(last_error) and not timeout_error and not provider_unavailable and not transport_failure
    bridge_failure = timeout_error or provider_unavailable or transport_failure or adapter_error
    return {
        'bridge_failure': bridge_failure,
        'timeout_error': timeout_error,
        'provider_unavailable': provider_unavailable,
        'transport_failure': transport_failure,
        'adapter_error': adapter_error,
        'run_bridge_info': run_bridge_info,
    }


def _row_protocol_state(row: dict[str, Any]) -> dict[str, Any]:
    parse_error = bool(row.get('parse_error') or row.get('slot_parse_error') or row.get('ddx_parse_error'))
    termination_reason = row.get('termination_reason')
    pred_labels = _diagnosis_topk_labels(row)
    final_output = row.get('final_output')
    placeholder_final = _protocol_placeholder_final(final_output)
    invalid_final_reason = row.get('invalid_final_reason')
    if invalid_final_reason in {None, '', 'none'}:
        invalid_final_reason = None

    parse_retry_raw = row.get('parse_retry_count')
    parse_retry_numeric = _to_float(parse_retry_raw)
    parse_retry_count = int(parse_retry_numeric) if parse_retry_numeric is not None else (1 if parse_error else 0)

    action_schema_valid_raw = row.get('action_schema_valid')
    if isinstance(action_schema_valid_raw, bool):
        action_schema_valid = action_schema_valid_raw
    else:
        action_schema_valid = not parse_error and termination_reason not in {'invalid_action_limit', 'invalid_slot_id_limit'}

    final_consumable_raw = row.get('final_consumable')
    if isinstance(final_consumable_raw, bool):
        final_consumable = final_consumable_raw
    else:
        final_consumable = bool(pred_labels) and not parse_error and not placeholder_final

    invalid_final = bool(invalid_final_reason) or (not final_consumable and not parse_error)
    protocol_failure = bool(
        parse_error
        or not action_schema_valid
        or invalid_final
        or termination_reason in {'repeat_slot', 'invalid_action_limit', 'invalid_slot_id_limit'}
    )
    return {
        'parse_error': parse_error,
        'parse_retry_count': parse_retry_count,
        'termination_reason': termination_reason,
        'action_schema_valid': action_schema_valid,
        'final_consumable': final_consumable,
        'protocol_failure': protocol_failure,
        'placeholder_final': placeholder_final,
        'invalid_final': invalid_final,
        'invalid_final_reason': invalid_final_reason,
    }


def _row_protocol_failure_buckets(
    protocol_state: dict[str, Any],
    bridge_state: dict[str, Any],
    fallback_other_reason: str,
) -> list[str]:
    buckets: list[str] = []
    if bridge_state.get('timeout_error'):
        buckets.append('timeout')
    if protocol_state.get('parse_error'):
        buckets.append('parse_error')
    if protocol_state.get('invalid_final'):
        buckets.append('invalid_final')
    termination_reason = protocol_state.get('termination_reason')
    if termination_reason == 'repeat_slot':
        buckets.append('repeat_slot')
    if termination_reason == 'invalid_slot_id_limit':
        buckets.append('invalid_slot_id')
    if fallback_other_reason != 'none':
        buckets.append('fallback_other')
    return buckets


def _oracle_final_labels(row: dict[str, Any], protocol_state: dict[str, Any]) -> list[str] | None:
    if not protocol_state.get('protocol_failure'):
        labels = _diagnosis_topk_labels(row)
        return labels or None
    top_level = row.get('diagnosis_topk')
    if isinstance(top_level, list):
        labels: list[str] = []
        for item in top_level:
            if isinstance(item, str):
                labels.append(item)
            elif isinstance(item, dict) and isinstance(item.get('label'), str):
                labels.append(item['label'])
        if labels:
            return labels
    return None


def _diagnosis_topk_labels(row: dict[str, Any]) -> list[str]:
    diagnosis_topk = row.get('diagnosis_topk')
    if isinstance(diagnosis_topk, list):
        labels: list[str] = []
        for item in diagnosis_topk:
            if isinstance(item, str):
                labels.append(item)
            elif isinstance(item, dict) and isinstance(item.get('label'), str):
                labels.append(item['label'])
        if labels:
            return labels
    final_output = row.get('final_output')
    if isinstance(final_output, dict):
        diagnosis_topk = final_output.get('diagnosis_topk', [])
        labels = []
        for item in diagnosis_topk:
            if isinstance(item, dict) and isinstance(item.get('label'), str):
                labels.append(item['label'])
            elif isinstance(item, str):
                labels.append(item)
        return labels
    return []


def _diagnosis_topk_detail(row: dict[str, Any]) -> list[dict[str, Any]]:
    diagnosis_topk = row.get('diagnosis_topk')
    items: list[dict[str, Any]] = []
    if isinstance(diagnosis_topk, list):
        for item in diagnosis_topk:
            if isinstance(item, str):
                items.append({'label': item, 'confidence': None})
            elif isinstance(item, dict) and isinstance(item.get('label'), str):
                items.append({'label': item['label'], 'confidence': item.get('confidence')})
    if items:
        return items
    final_output = row.get('final_output')
    if isinstance(final_output, dict):
        diagnosis_topk = final_output.get('diagnosis_topk', [])
        for item in diagnosis_topk:
            if isinstance(item, dict) and isinstance(item.get('label'), str):
                items.append({'label': item['label'], 'confidence': item.get('confidence')})
            elif isinstance(item, str):
                items.append({'label': item, 'confidence': None})
    return items


def _bool_from_metric(value: Any, threshold: float = 1.0) -> bool | None:
    numeric = _to_float(value)
    if numeric is None:
        return None
    return numeric >= threshold


def _row_failure_bucket_state(run_type: str, row: dict[str, Any], gold_label: str) -> dict[str, bool | str]:
    metrics = row.get('metrics', {}) if isinstance(row.get('metrics'), dict) else {}
    pred_labels = _diagnosis_topk_labels(row)
    harm_flags = row.get('harm_flags') or []
    parse_error = bool(row.get('parse_error') or row.get('slot_parse_error') or row.get('ddx_parse_error'))

    state: dict[str, bool | str] = {
        'top1_wrong': bool(pred_labels) and pred_labels[0] != gold_label,
        'top3_miss': bool(pred_labels) and gold_label not in pred_labels[:3],
        'safety_flagged': bool(harm_flags),
        'parse_or_execution_error': parse_error,
    }
    if run_type == 'dynamic':
        must_ask_value = _to_float(metrics.get('must_ask_hit_rate'))
        svcl_value = _to_float(metrics.get('svcl_coverage'))
        state['must_ask_miss'] = must_ask_value is not None and must_ask_value < 1.0
        state['svcl_coverage_gap'] = svcl_value is not None and svcl_value < 1.0
    else:
        state['must_ask_miss'] = 'not_applicable'
        state['svcl_coverage_gap'] = 'not_applicable'
    return state


def _active_failure_buckets(bucket_state: dict[str, bool | str]) -> list[str]:
    return [bucket for bucket in FAILURE_BUCKETS if bucket_state.get(bucket) is True]


def _asked_svcl_domains(row: dict[str, Any], ontology: Any) -> set[str]:
    asked = row.get('asked_slots') or []
    if not isinstance(asked, list):
        return set()
    return {ontology.svcl_map[slot_id] for slot_id in asked if slot_id in ontology.svcl_map}


def _build_case_projection_entries(run_row: db.RunRegistryRow, repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    warnings: list[str] = []
    selected_cases, case_by_id, rubric_by_id, ontology = _load_release_casebank(repo_root, run_row.split_name)
    selected_case_ids = {case.case_id for case in selected_cases}

    if not run_row.results_root:
        warnings.append('results_root missing for run')
        return [], {'case_count': len(selected_case_ids), 'completed_case_count': 0, 'case_by_id': case_by_id, 'rubric_by_id': rubric_by_id, 'ontology': ontology}, warnings

    results_root = repo_root / run_row.results_root
    if not results_root.exists():
        warnings.append('results_root does not exist on disk')
        return [], {'case_count': len(selected_case_ids), 'completed_case_count': 0, 'case_by_id': case_by_id, 'rubric_by_id': rubric_by_id, 'ontology': ontology}, warnings

    prediction_rows, prediction_warnings = _find_prediction_rows(results_root)
    warnings.extend(prediction_warnings)
    replay_rows = _find_replay_rows(results_root)
    replay_by_case = {row.get('case_id'): row for row in replay_rows if isinstance(row.get('case_id'), str)}

    bridge_info = _classify_bridge_failure(run_row, repo_root)
    entries: list[dict[str, Any]] = []
    for row in prediction_rows:
        case_id = row.get('case_id')
        if not isinstance(case_id, str) or case_id not in selected_case_ids:
            continue
        case = case_by_id.get(case_id)
        rubric = rubric_by_id.get(case_id)
        if case is None or rubric is None:
            continue
        metrics = row.get('metrics', {}) if isinstance(row.get('metrics'), dict) else {}
        pred_labels = _diagnosis_topk_labels(row)
        pred_top1 = pred_labels[0] if pred_labels else None
        top1_correct = pred_top1 == case.label if pred_top1 else False
        top3_hit = case.label in pred_labels[:3] if pred_labels else False
        top5_hit = _top5_hit(pred_labels, case.label)
        required_svcl_domains_count = len(case.required_svcl_domains)
        bucket_state = _row_failure_bucket_state(run_row.run_type, row, case.label)
        active_buckets = _active_failure_buckets(bucket_state)
        asked_domains = _asked_svcl_domains(row, ontology) if run_row.run_type == 'dynamic' else set()
        protocol_state = _row_protocol_state(row)
        bridge_state = _row_bridge_state(row, bridge_info, protocol_state)
        replay_logs = _extract_replay_logs(row, replay_by_case.get(case_id))
        repeat_slot_count = _repeat_slot_count(replay_logs, protocol_state['termination_reason'])
        invalid_slot_count = _invalid_slot_count(protocol_state['termination_reason'])
        fallback_other_reason = _fallback_other_reason(
            protocol_state['parse_error'],
            protocol_state['placeholder_final'],
        )
        adapter_latency_ms = _adapter_latency_ms(row, run_row)
        must_ask_value = _to_float(metrics.get('must_ask_hit_rate'))
        svcl_value = _to_float(metrics.get('svcl_coverage'))
        bridge_failure = bridge_state['bridge_failure']
        if bridge_failure:
            failure_source = 'bridge'
            capability_state = 'not_evaluable'
        elif protocol_state['protocol_failure']:
            failure_source = 'protocol'
            capability_state = 'not_evaluable'
        else:
            capability_failure = bool(
                (run_row.run_type == 'dynamic' and must_ask_value is not None and must_ask_value < 1.0)
                or (run_row.run_type == 'dynamic' and svcl_value is not None and svcl_value < 1.0)
                or not top3_hit
                or not top1_correct
            )
            capability_state = 'affected' if capability_failure else 'clean'
            failure_source = 'capability' if capability_failure else 'clean'
        oracle_labels = _oracle_final_labels(row, protocol_state)
        case_status = str(row.get('case_status') or 'completed')
        last_error = row.get('last_error')
        protocol_failure_buckets = _row_protocol_failure_buckets(protocol_state, bridge_state, fallback_other_reason)
        entries.append(
            {
                'case_id': case_id,
                'dsm_module': case.dsm_module,
                'label': case.label,
                'ambiguity': case.ambiguity,
                'required_svcl_domains_count': required_svcl_domains_count,
                'required_svcl_domains': list(case.required_svcl_domains),
                'pred_top1': pred_top1,
                'pred_labels': pred_labels,
                'prediction_row': row,
                'replay_row': replay_by_case.get(case_id),
                'gold_label': case.label,
                'gold_ddx_top5': list(case.gold_ddx_top5),
                'top1_correct': top1_correct,
                'top3_hit': top3_hit,
                'top5_hit': top5_hit,
                'must_ask_hit_rate': must_ask_value,
                'svcl_coverage': svcl_value,
                'metrics': metrics,
                'failure_bucket_state': bucket_state,
                'failure_buckets': active_buckets,
                'bridge_failure': bridge_failure,
                'adapter_error': bridge_state['adapter_error'],
                'timeout_affected': bridge_state['timeout_error'],
                'protocol_failure': protocol_state['protocol_failure'],
                'parse_affected': protocol_state['parse_error'],
                'action_schema_valid': protocol_state['action_schema_valid'],
                'final_consumable': protocol_state['final_consumable'],
                'invalid_final': protocol_state['invalid_final'],
                'invalid_final_reason': protocol_state['invalid_final_reason'],
                'parse_retry_count': protocol_state['parse_retry_count'],
                'termination_reason': protocol_state['termination_reason'],
                'repeat_slot_count': repeat_slot_count,
                'invalid_slot_count': invalid_slot_count,
                'fallback_other_reason': fallback_other_reason,
                'adapter_latency_ms': adapter_latency_ms,
                'timeout_error': bridge_state['timeout_error'],
                'case_status': case_status,
                'last_error': last_error,
                'failure_source': failure_source,
                'capability_state': capability_state,
                'oracle_final_labels': oracle_labels,
                'protocol_failure_buckets': protocol_failure_buckets,
                'risk_flags': case.risk_flags.model_dump(),
                'minimal_cc': case.info_variants.minimal_cc,
                'must_ask_slots': list(rubric.must_ask_slots),
                'avoid_harm_rules': list(rubric.avoid_harm_rules),
                'asked_svcl_domains': asked_domains,
                'personality_spectrum': case.dsm_module == 'PD',
                'risk_positive': any(case.risk_flags.model_dump().values()),
            }
        )

    totals = {
        'case_count': len(selected_case_ids),
        'completed_case_count': sum(1 for entry in entries if entry.get('case_status') == 'completed'),
        'case_by_id': case_by_id,
        'rubric_by_id': rubric_by_id,
        'ontology': ontology,
        'bridge_info': bridge_info,
    }
    return entries, totals, warnings


def _aggregate_case_entries(entries: list[dict[str, Any]]) -> dict[str, float | None]:
    return {
        'top1_acc': _metric_mean(1.0 if entry['top1_correct'] else 0.0 for entry in entries),
        'top3_cov': _metric_mean(1.0 if entry['top3_hit'] else 0.0 for entry in entries),
        'top5_cov': _metric_mean(1.0 if entry['top5_hit'] else 0.0 for entry in entries),
        'must_ask_hit_rate': _metric_mean(entry.get('must_ask_hit_rate') for entry in entries),
        'svcl_coverage': _metric_mean(entry.get('svcl_coverage') for entry in entries),
        'action_schema_valid_rate': _metric_mean(1.0 if entry.get('action_schema_valid') else 0.0 for entry in entries),
        'final_consumable_rate': _metric_mean(1.0 if entry.get('final_consumable') else 0.0 for entry in entries),
        'parse_error_rate': _metric_mean(1.0 if entry.get('parse_affected') else 0.0 for entry in entries),
        'invalid_final_rate': _metric_mean(1.0 if entry.get('invalid_final') else 0.0 for entry in entries),
    }


def _compute_oracle_final_metrics(entries: list[dict[str, Any]]) -> tuple[dict[str, float | None], dict[str, Any]]:
    usable = [entry for entry in entries if entry.get('oracle_final_labels')]
    if not usable:
        return {}, {'available_case_count': 0, 'warnings': ['No oracle-finalizable protocol failures found.']}

    top1 = _metric_mean(
        1.0 if entry['gold_label'] == entry['oracle_final_labels'][0] else 0.0
        for entry in usable
        if entry['oracle_final_labels']
    )
    top3 = _metric_mean(
        1.0 if entry['gold_label'] in entry['oracle_final_labels'][:3] else 0.0
        for entry in usable
    )
    top5 = _metric_mean(
        1.0 if entry['gold_label'] in entry['oracle_final_labels'][:5] else 0.0
        for entry in usable
    )
    return {
        'oracle_final_top1_acc': top1,
        'oracle_final_top3_cov': top3,
        'oracle_final_top5_cov': top5,
    }, {'available_case_count': len(usable), 'warnings': []}


def _compute_failure_attribution(entries: list[dict[str, Any]], totals: dict[str, Any]) -> dict[str, Any]:
    termination_histogram = Counter(
        entry['termination_reason'] or 'unknown'
        for entry in entries
    )
    failure_source_counts = Counter(entry.get('failure_source', 'clean') for entry in entries)
    bridge_info = totals.get('bridge_info', {})
    bridge_failure_count = sum(1 for entry in entries if entry.get('bridge_failure'))
    timeout_count = sum(1 for entry in entries if entry.get('timeout_affected'))
    adapter_error_count = sum(1 for entry in entries if entry.get('adapter_error'))
    if not entries:
        bridge_failure_count = 1 if bridge_info.get('bridge_failure') else 0
        timeout_count = 1 if bridge_info.get('timeout') else 0
    protocol_failure_count = sum(1 for entry in entries if entry.get('protocol_failure'))
    capability_failure_count = sum(1 for entry in entries if entry.get('capability_state') == 'affected')
    parse_retry_count = sum(int(entry.get('parse_retry_count', 0) or 0) for entry in entries)
    parse_error_rate = _metric_mean(1.0 if entry.get('parse_affected') else 0.0 for entry in entries)
    invalid_final_rate = _metric_mean(1.0 if entry.get('invalid_final') else 0.0 for entry in entries)
    execution_success_rate = None
    if totals.get('case_count'):
        execution_success_rate = float(totals['completed_case_count'] / totals['case_count'])
    return {
        'execution_success_rate': execution_success_rate,
        'timeout_count': timeout_count,
        'bridge_failure_count': bridge_failure_count,
        'adapter_error_count': adapter_error_count,
        'parse_retry_count': float(parse_retry_count),
        'parse_error_rate': parse_error_rate,
        'invalid_final_rate': invalid_final_rate,
        'termination_reason_histogram': dict(termination_histogram),
        'failure_source_counts': {
            source: int(failure_source_counts.get(source, 0))
            for source in FAILURE_SOURCES
        },
        'bridge': {
            'affected': bool(bridge_failure_count or bridge_info.get('bridge_failure')),
            'timeout': bool(timeout_count or bridge_info.get('timeout')),
            'provider_unavailable': bool(bridge_info.get('provider_unavailable')),
            'transport_failure': bool(bridge_info.get('transport_failure')),
            'message': bridge_info.get('message'),
        },
        'protocol_failure_count': protocol_failure_count,
        'capability_failure_count': capability_failure_count,
    }


def build_run_summary_projection(run_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    run_row = db.get_run(repo_root, run_id)
    if run_row is None:
        raise KeyError(run_id)

    if run_row.status in {'queued', 'running'}:
        return {
            'run_id': run_id,
            'status': run_row.status,
            'state': 'pending',
            'overall_metrics': [],
            'process_score': [],
            'compliance_score': [],
            'final_diagnosis_score': [],
            'baseline_compare': None,
            'failure_attribution': None,
            'supplemental': None,
            'summary_paths': {
                'metrics_path': run_row.metrics_path,
                'summary_path': run_row.summary_path,
            },
            'warnings': [],
        }

    if run_row.status == 'failed':
        return {
            'run_id': run_id,
            'status': run_row.status,
            'state': 'failed',
            'overall_metrics': [],
            'process_score': [],
            'compliance_score': [],
            'final_diagnosis_score': [],
            'baseline_compare': None,
            'failure_attribution': {
                **_compute_failure_attribution([], {'case_count': 0, 'completed_case_count': 0, 'bridge_info': _classify_bridge_failure(run_row, repo_root)}),
            },
            'supplemental': None,
            'summary_paths': {
                'metrics_path': run_row.metrics_path,
                'summary_path': run_row.summary_path,
            },
            'warnings': [],
            'error_summary': json.loads(run_row.error_summary_json) if run_row.error_summary_json else None,
        }

    warnings: list[str] = []
    metrics_payload = _safe_read_json(repo_root / run_row.metrics_path) if run_row.metrics_path else None
    if metrics_payload is None:
        raise SummaryProjectionError('metrics.json missing or invalid')

    payload_overall = _overall_metrics_from_payload(metrics_payload)
    if run_row.summary_path is None or not (repo_root / run_row.summary_path).exists():
        warnings.append('summary.csv missing')

    process_score: list[dict[str, Any]] = []
    compliance_score: list[dict[str, Any]] = []
    final_diagnosis_score: list[dict[str, Any]] = []
    failure_attribution: dict[str, Any] | None = None
    supplemental: dict[str, Any] | None = None
    overall_metrics: list[dict[str, Any]] = payload_overall

    if run_row.run_type == 'dynamic':
        try:
            entries, totals_bundle, projection_warnings = _build_case_projection_entries(run_row, repo_root)
            warnings.extend(projection_warnings)
            aggregated = _aggregate_case_entries(entries)
            payload_scalar = {item['key']: item['value'] for item in payload_overall if isinstance(item.get('value'), (int, float))}
            process_map = {
                'must_ask_hit_rate': aggregated.get('must_ask_hit_rate'),
                'svcl_coverage': aggregated.get('svcl_coverage'),
                'turns': payload_scalar.get('turns'),
            }
            attribution = _compute_failure_attribution(entries, totals_bundle)
            compliance_map = {
                'execution_success_rate': attribution.get('execution_success_rate'),
                'action_schema_valid_rate': aggregated.get('action_schema_valid_rate'),
                'final_consumable_rate': aggregated.get('final_consumable_rate'),
                'parse_error_rate': aggregated.get('parse_error_rate'),
                'invalid_final_rate': aggregated.get('invalid_final_rate'),
                'parse_retry_count': attribution.get('parse_retry_count'),
                'timeout_count': attribution.get('timeout_count'),
                'bridge_failure_count': attribution.get('bridge_failure_count'),
                'adapter_error_count': attribution.get('adapter_error_count'),
            }
            final_map = {
                'top1_acc': payload_scalar.get('top1_acc'),
                'top3_cov': payload_scalar.get('top3_cov'),
                'top5_cov': payload_scalar.get('top5_cov'),
                'strict_top1_acc': payload_scalar.get('strict_top1_acc'),
                'strict_top5_cov': payload_scalar.get('strict_top5_cov'),
            }
            oracle_map, oracle_meta = _compute_oracle_final_metrics(entries)
            process_score = _metric_cards_from_mapping(process_map, ['must_ask_hit_rate', 'svcl_coverage', 'turns'])
            compliance_score = _metric_cards_from_mapping(
                compliance_map,
                [
                    'execution_success_rate',
                    'action_schema_valid_rate',
                    'final_consumable_rate',
                    'parse_error_rate',
                    'invalid_final_rate',
                    'parse_retry_count',
                    'timeout_count',
                    'bridge_failure_count',
                    'adapter_error_count',
                ],
            )
            final_diagnosis_score = _metric_cards_from_mapping(
                final_map,
                ['top1_acc', 'top3_cov', 'top5_cov', 'strict_top1_acc', 'strict_top5_cov'],
            )
            supplemental = {
                'oracle_final_metrics': _metric_cards_from_mapping(
                    oracle_map,
                    ['oracle_final_top1_acc', 'oracle_final_top3_cov', 'oracle_final_top5_cov'],
                ),
                **oracle_meta,
            }
            failure_attribution = attribution
            overall_metrics = process_score + compliance_score + final_diagnosis_score + (supplemental['oracle_final_metrics'] if supplemental else [])
        except Exception as exc:  # pragma: no cover - best-effort
            warnings.append(f'failed to build dynamic attribution layer: {exc}')

    current_metrics = {item['key']: item['value'] for item in overall_metrics if isinstance(item.get('value'), (int, float))}

    pure_rows = _safe_read_csv(repo_root / PURE_BASELINES_PATH)
    guided_rows = _safe_read_csv(repo_root / GUIDED_BASELINES_PATH)
    pure_row, pure_warnings = _pick_pure_baseline(run_row, pure_rows)
    guided_row, guided_warnings = _pick_guided_baseline(run_row, guided_rows)
    baseline_warnings = pure_warnings + guided_warnings + _deprecated_warnings(repo_root)
    baseline_compare = {
        'metrics': _baseline_metric_row(current_metrics, pure_row, guided_row),
        'source_tables': {
            'pure_baselines_path': str(PURE_BASELINES_PATH) if (repo_root / PURE_BASELINES_PATH).exists() else None,
            'guided_llm_baselines_path': str(GUIDED_BASELINES_PATH) if (repo_root / GUIDED_BASELINES_PATH).exists() else None,
            'deprecated_results_path': str(DEPRECATED_RESULTS_PATH) if (repo_root / DEPRECATED_RESULTS_PATH).exists() else None,
        },
        'warnings': baseline_warnings,
    }

    state = 'ready'
    degradation_warnings = [
        warning for warning in baseline_warnings
        if warning.startswith('No matching baseline row found') or warning.startswith('No guided baseline row found')
    ]
    if warnings or degradation_warnings:
        state = 'partial'

    return {
        'run_id': run_id,
        'status': run_row.status,
        'state': state,
        'overall_metrics': overall_metrics,
        'process_score': process_score,
        'compliance_score': compliance_score,
        'final_diagnosis_score': final_diagnosis_score,
        'baseline_compare': baseline_compare,
        'failure_attribution': failure_attribution,
        'supplemental': supplemental,
        'summary_paths': {
            'metrics_path': run_row.metrics_path,
            'summary_path': run_row.summary_path,
        },
        'warnings': warnings,
    }


def build_slices_summary(run_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    run_row = db.get_run(repo_root, run_id)
    if run_row is None:
        raise KeyError(run_id)

    if run_row.status in {'queued', 'running'}:
        return {
            'run_id': run_id,
            'status': run_row.status,
            'state': 'pending',
            'totals': {'case_count': 0, 'completed_case_count': 0},
        'slices': {
            'by_module': [],
            'by_label': [],
            'by_ambiguity': [],
            'by_required_svcl_domains_count': [],
            'by_termination_reason': [],
            'by_failure_source': [],
            'by_failure_bucket': [],
            'by_risk_positive': [],
                'by_personality_spectrum': [],
                'by_timeout_affected': [],
                'by_parse_affected': [],
                'by_protocol_clean_only': [],
            },
            'warnings': [],
        }

    if run_row.status == 'failed':
        return {
            'run_id': run_id,
            'status': run_row.status,
            'state': 'failed',
            'totals': {'case_count': 0, 'completed_case_count': 0},
            'slices': {
                'by_module': [],
                'by_label': [],
                'by_ambiguity': [],
                'by_required_svcl_domains_count': [],
                'by_termination_reason': [],
                'by_failure_source': [],
                'by_failure_bucket': [],
                'by_risk_positive': [],
                'by_personality_spectrum': [],
                'by_timeout_affected': [],
                'by_parse_affected': [],
                'by_protocol_clean_only': [],
            },
            'warnings': [],
            'error_summary': json.loads(run_row.error_summary_json) if run_row.error_summary_json else None,
        }

    try:
        entries, totals_bundle, warnings = _build_case_projection_entries(run_row, repo_root)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        raise SliceProjectionError(str(exc)) from exc
    totals = {
        'case_count': totals_bundle['case_count'],
        'completed_case_count': totals_bundle['completed_case_count'],
    }

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        'by_module': defaultdict(list),
        'by_label': defaultdict(list),
        'by_ambiguity': defaultdict(list),
        'by_required_svcl_domains_count': defaultdict(list),
        'by_termination_reason': defaultdict(list),
        'by_failure_source': defaultdict(list),
        'by_risk_positive': defaultdict(list),
        'by_personality_spectrum': defaultdict(list),
        'by_timeout_affected': defaultdict(list),
        'by_parse_affected': defaultdict(list),
        'by_protocol_clean_only': defaultdict(list),
    }
    for entry in entries:
        grouped['by_module'][entry['dsm_module']].append(entry)
        grouped['by_label'][entry['label']].append(entry)
        grouped['by_ambiguity'][entry['ambiguity']].append(entry)
        key = str(entry['required_svcl_domains_count']) if entry['required_svcl_domains_count'] is not None else 'null'
        grouped['by_required_svcl_domains_count'][key].append(entry)
        grouped['by_termination_reason'][entry['termination_reason'] or 'unknown'].append(entry)
        grouped['by_failure_source'][entry['failure_source']].append(entry)
        grouped['by_risk_positive']['risk_positive' if entry['risk_positive'] else 'risk_negative'].append(entry)
        grouped['by_personality_spectrum']['personality_spectrum' if entry['personality_spectrum'] else 'non_personality_spectrum'].append(entry)
        grouped['by_timeout_affected']['timeout_affected' if entry['timeout_affected'] else 'timeout_unaffected'].append(entry)
        grouped['by_parse_affected']['parse_affected' if entry['parse_affected'] else 'parse_unaffected'].append(entry)
        grouped['by_protocol_clean_only']['clean' if not entry['protocol_failure'] else 'affected'].append(entry)

    slices = {
        'by_module': [
            {'key': key, 'label': key, 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_module'].items())
        ],
        'by_label': [
            {'key': key, 'label': key, 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_label'].items())
        ],
        'by_ambiguity': [
            {'key': key, 'label': key.capitalize(), 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_ambiguity'].items())
        ],
        'by_required_svcl_domains_count': [
            {
                'key': key,
                'label': f'{key} domains' if key != 'null' else 'Unknown',
                'case_count': len(rows),
                'metrics': _aggregate_case_entries(rows),
            }
            for key, rows in sorted(grouped['by_required_svcl_domains_count'].items(), key=lambda item: item[0])
        ],
        'by_termination_reason': [
            {'key': key, 'label': key.replace('_', ' '), 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_termination_reason'].items())
        ],
        'by_failure_source': [
            {'key': key, 'label': key.capitalize(), 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_failure_source'].items())
        ],
        'by_failure_bucket': [
            {
                'key': bucket,
                'label': bucket,
                'case_count': sum(1 for entry in entries if bucket in entry['failure_buckets']),
            }
            for bucket in FAILURE_BUCKETS
        ],
        'by_risk_positive': [
            {'key': key, 'label': key.replace('_', ' '), 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_risk_positive'].items())
        ],
        'by_personality_spectrum': [
            {'key': key, 'label': key.replace('_', ' '), 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_personality_spectrum'].items())
        ],
        'by_timeout_affected': [
            {'key': key, 'label': key.replace('_', ' '), 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_timeout_affected'].items())
        ],
        'by_parse_affected': [
            {'key': key, 'label': key.replace('_', ' '), 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_parse_affected'].items())
        ],
        'by_protocol_clean_only': [
            {'key': key, 'label': key, 'case_count': len(rows), 'metrics': _aggregate_case_entries(rows)}
            for key, rows in sorted(grouped['by_protocol_clean_only'].items())
        ],
    }

    state = 'ready'
    if warnings or totals['completed_case_count'] < totals['case_count']:
        state = 'partial'

    return {
        'run_id': run_id,
        'status': run_row.status,
        'state': state,
        'totals': totals,
        'slices': slices,
        'warnings': warnings,
    }


def list_cases_for_run(run_id: str, filters: dict[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    run_row = db.get_run(repo_root, run_id)
    if run_row is None:
        raise KeyError(run_id)

    if run_row.status in {'queued', 'running'}:
        return {
            'run_id': run_id,
            'state': 'pending',
            'filters': filters,
            'total': 0,
            'items': [],
            'warnings': [],
        }

    if run_row.status == 'failed':
        return {
            'run_id': run_id,
            'state': 'failed',
            'filters': filters,
            'total': 0,
            'items': [],
            'warnings': [],
            'error_summary': json.loads(run_row.error_summary_json) if run_row.error_summary_json else None,
        }

    try:
        entries, totals_bundle, warnings = _build_case_projection_entries(run_row, repo_root)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        raise CaseListProjectionError(str(exc)) from exc

    def keep(entry: dict[str, Any]) -> bool:
        if filters.get('module') and entry['dsm_module'] != filters['module']:
            return False
        if filters.get('label') and entry['label'] != filters['label']:
            return False
        if filters.get('ambiguity') and entry['ambiguity'] != filters['ambiguity']:
            return False
        if filters.get('required_svcl_domains_count') is not None:
            try:
                expected = int(filters['required_svcl_domains_count'])
            except (TypeError, ValueError):
                return False
            if entry['required_svcl_domains_count'] != expected:
                return False
        if filters.get('failure_bucket') and filters['failure_bucket'] not in entry['failure_buckets']:
            return False
        if filters.get('risk_positive') is not None:
            expected = str(filters['risk_positive']).lower() in {'1', 'true', 'yes', 'risk_positive'}
            if entry['risk_positive'] != expected:
                return False
        if filters.get('personality_spectrum') is not None:
            expected = str(filters['personality_spectrum']).lower() in {'1', 'true', 'yes', 'personality_spectrum'}
            if entry['personality_spectrum'] != expected:
                return False
        if filters.get('timeout_affected') is not None:
            expected = str(filters['timeout_affected']).lower() in {'1', 'true', 'yes', 'timeout_affected'}
            if entry['timeout_affected'] != expected:
                return False
        if filters.get('parse_affected') is not None:
            expected = str(filters['parse_affected']).lower() in {'1', 'true', 'yes', 'parse_affected'}
            if entry['parse_affected'] != expected:
                return False
        if filters.get('protocol_clean_only') is not None:
            expected_clean = str(filters['protocol_clean_only']).lower() in {'1', 'true', 'yes', 'clean'}
            if expected_clean == entry['protocol_failure']:
                return False
        if filters.get('failure_source') and entry['failure_source'] != filters['failure_source']:
            return False
        return True

    filtered = [entry for entry in entries if keep(entry)]
    limit = max(1, min(int(filters.get('limit', 50) or 50), 200))
    offset = max(0, int(filters.get('offset', 0) or 0))
    window = filtered[offset: offset + limit]

    items = [
        {
            'case_id': entry['case_id'],
            'dsm_module': entry['dsm_module'],
            'label': entry['label'],
            'ambiguity': entry['ambiguity'],
            'required_svcl_domains_count': entry['required_svcl_domains_count'],
            'pred_top1': entry['pred_top1'],
            'gold_label': entry['gold_label'],
            'top1_correct': entry['top1_correct'],
            'top3_hit': entry['top3_hit'],
            'must_ask_hit_rate': entry['must_ask_hit_rate'],
            'svcl_coverage': entry['svcl_coverage'],
            'failure_buckets': entry['failure_buckets'],
            'protocol_failure_buckets': entry['protocol_failure_buckets'],
            'failure_source': entry['failure_source'],
            'risk_flags': entry['risk_flags'],
            'termination_reason': entry['termination_reason'],
        }
        for entry in window
    ]

    state = 'ready'
    if warnings or totals_bundle['completed_case_count'] < totals_bundle['case_count']:
        state = 'partial'

    return {
        'run_id': run_id,
        'state': state,
        'filters': {
            'module': filters.get('module'),
            'label': filters.get('label'),
            'ambiguity': filters.get('ambiguity'),
            'required_svcl_domains_count': filters.get('required_svcl_domains_count'),
            'termination_reason': filters.get('termination_reason'),
            'failure_bucket': filters.get('failure_bucket'),
            'risk_positive': filters.get('risk_positive'),
            'personality_spectrum': filters.get('personality_spectrum'),
            'timeout_affected': filters.get('timeout_affected'),
            'parse_affected': filters.get('parse_affected'),
            'protocol_clean_only': filters.get('protocol_clean_only'),
            'failure_source': filters.get('failure_source'),
        },
        'total': len(filtered),
        'items': items,
        'warnings': warnings,
    }


def get_case_detail_for_run(run_id: str, case_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    run_row = db.get_run(repo_root, run_id)
    if run_row is None:
        raise KeyError(run_id)
    if run_row.status in {'queued', 'running'}:
        raise RunNotReadyError(run_id)

    try:
        entries, totals_bundle, warnings = _build_case_projection_entries(run_row, repo_root)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        raise CaseProjectionError(str(exc)) from exc
    case_by_id = totals_bundle['case_by_id']
    rubric_by_id = totals_bundle['rubric_by_id']
    ontology = totals_bundle['ontology']

    case = case_by_id.get(case_id)
    rubric = rubric_by_id.get(case_id)
    if case is None or rubric is None:
        raise CaseNotFoundError(case_id)

    entry = next((item for item in entries if item['case_id'] == case_id), None)
    if entry is None:
        return {
            'run_id': run_id,
            'case_id': case_id,
            'state': 'partial',
            'case_meta': {
                'dsm_module': case.dsm_module,
                'label': case.label,
                'ambiguity': case.ambiguity,
                'required_svcl_domains': list(case.required_svcl_domains),
                'must_ask_slots': list(rubric.must_ask_slots),
                'gold_label': case.label,
                'gold_ddx_top5': list(case.gold_ddx_top5),
                'risk_flags': case.risk_flags.model_dump(),
                'minimal_cc': case.info_variants.minimal_cc,
            },
            'run_output': None,
            'failure_analysis': {
                'failure_buckets': [],
                'missing_must_ask_slots': [],
                'missing_svcl_domains': [],
                'warnings': ['prediction row unavailable for this case'],
            },
            'dynamic_replay': {'available': False, 'turns': [], 'final_output': None},
            'warnings': warnings + ['prediction row unavailable for this case'],
        }

    asked_slots = entry['prediction_row'].get('asked_slots') if isinstance(entry['prediction_row'].get('asked_slots'), list) else []
    missing_must_ask_slots = [slot for slot in rubric.must_ask_slots if slot not in asked_slots] if run_row.run_type == 'dynamic' else []
    missing_svcl_domains = [
        domain for domain in case.required_svcl_domains
        if domain not in entry['asked_svcl_domains']
    ] if run_row.run_type == 'dynamic' else []

    replay_logs = _extract_replay_logs(entry['prediction_row'], entry.get('replay_row'))
    replay_available = isinstance(replay_logs, list) and len(replay_logs) > 0
    replay_warning: list[str] = []
    if not replay_available:
        replay_warning.append('Replay unavailable')

    turns = []
    if replay_available:
        for turn in replay_logs or []:
            doctor_action = turn.get('doctor_action', {}) if isinstance(turn, dict) else {}
            patient_answer = turn.get('patient_answer', {}) if isinstance(turn, dict) else {}
            turns.append(
                {
                    't': turn.get('turn'),
                    'doctor_slot_id': doctor_action.get('slot_id'),
                    'doctor_utterance': doctor_action.get('utterance'),
                    'patient_utterance': patient_answer.get('utterance'),
                }
            )

    state = 'ready'
    if warnings or replay_warning:
        state = 'partial'

    return {
        'run_id': run_id,
        'case_id': case_id,
        'state': state,
        'case_meta': {
            'dsm_module': case.dsm_module,
            'label': case.label,
            'ambiguity': case.ambiguity,
            'required_svcl_domains': list(case.required_svcl_domains),
            'must_ask_slots': list(rubric.must_ask_slots),
            'gold_label': case.label,
            'gold_ddx_top5': list(case.gold_ddx_top5),
            'risk_flags': case.risk_flags.model_dump(),
            'minimal_cc': case.info_variants.minimal_cc,
        },
        'run_output': {
            'pred_topk': _diagnosis_topk_detail(entry['prediction_row']),
            'top1_correct': entry['top1_correct'],
            'top3_hit': entry['top3_hit'],
            'must_ask_hit_rate': entry['must_ask_hit_rate'],
            'svcl_coverage': entry['svcl_coverage'],
            'safety_flags': entry['prediction_row'].get('harm_flags') or [],
            'action_schema_valid': entry['action_schema_valid'],
            'parse_error': entry['parse_affected'],
            'parse_retry_count': entry['parse_retry_count'],
            'repeat_slot_count': entry['repeat_slot_count'],
            'invalid_slot_count': entry['invalid_slot_count'],
            'final_consumable': entry['final_consumable'],
            'invalid_final_reason': entry['invalid_final_reason'],
            'termination_reason': entry['termination_reason'],
            'adapter_latency_ms': entry['adapter_latency_ms'],
            'timeout_error': entry['timeout_error'],
            'case_status': entry['case_status'],
            'last_error': entry['last_error'],
        },
        'failure_analysis': {
            'failure_buckets': entry['failure_buckets'],
            'protocol_failure_buckets': entry['protocol_failure_buckets'],
            'failure_source': entry['failure_source'],
            'failure_sources': {
                'bridge': 'affected' if entry['bridge_failure'] else 'clean',
                'protocol': 'affected' if entry['protocol_failure'] else 'clean',
                'capability': entry['capability_state'],
            },
            'missing_must_ask_slots': missing_must_ask_slots,
            'missing_svcl_domains': missing_svcl_domains,
            'fallback_other_reason': entry['fallback_other_reason'],
            'warnings': replay_warning,
        },
        'dynamic_replay': {
            'available': replay_available,
            'turns': turns,
            'final_output': entry['prediction_row'].get('final_output'),
        },
        'warnings': warnings + replay_warning,
    }
