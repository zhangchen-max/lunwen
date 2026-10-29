from __future__ import annotations

from typing import Any, Dict, Sequence

from eval.scorers.ddx_metrics import benchmark_topk_coverage, strict_topk_coverage


def must_ask_hit_rate(asked_slots: Sequence[str], must_ask_slots: Sequence[str]) -> float:
    required = set(must_ask_slots)
    if not required:
        return 1.0
    asked = set(asked_slots)
    return len(required & asked) / len(required)


def svcl_domain_coverage(
    asked_slots: Sequence[str],
    required_svcl_domains: Sequence[str],
    svcl_map: Dict[str, str],
) -> float:
    required = set(required_svcl_domains)
    if not required:
        return 1.0
    asked_domains = {svcl_map[s] for s in asked_slots if s in svcl_map}
    return len(required & asked_domains) / len(required)


def turns_to_hit_all_must_ask(ask_sequence: Sequence[str], must_ask_slots: Sequence[str]) -> int | None:
    required = set(must_ask_slots)
    if not required:
        return 0
    seen: set[str] = set()
    for idx, slot in enumerate(ask_sequence, start=1):
        if slot in required:
            seen.add(slot)
        if seen == required:
            return idx
    return None


def dynamic_topk_coverage(final_output: Dict[str, Any], gold_label: str) -> Dict[str, float]:
    diag = final_output.get("diagnosis_topk", []) if isinstance(final_output, dict) else []
    pred_labels = [x.get("label") for x in diag if isinstance(x, dict) and "label" in x]
    return topk_coverage_from_labels(pred_labels, gold_label, [gold_label], "unambiguous")


def topk_coverage_from_labels(
    pred_labels: Sequence[str],
    gold_label: str,
    gold_ddx_top5: Sequence[str],
    ambiguity: str,
) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    metrics.update(strict_topk_coverage(pred_labels, gold_label))
    metrics.update(benchmark_topk_coverage(pred_labels, gold_label, gold_ddx_top5, ambiguity))
    return metrics


def score_dynamic_case(
    asked_slots: Sequence[str],
    must_ask_slots: Sequence[str],
    required_svcl_domains: Sequence[str],
    svcl_map: Dict[str, str],
    final_output: Dict[str, Any],
    gold_label: str,
    gold_ddx_top5: Sequence[str],
    ambiguity: str,
) -> Dict[str, Any]:
    svcl_cov = svcl_domain_coverage(asked_slots, required_svcl_domains, svcl_map)
    metrics: Dict[str, Any] = {
        "must_ask_hit_rate": must_ask_hit_rate(asked_slots, must_ask_slots),
        "svcl_domain_coverage": svcl_cov,
        "svcl_coverage": svcl_cov,
        "turns": len(asked_slots),
        "turns_to_hit_all_must_ask": turns_to_hit_all_must_ask(asked_slots, must_ask_slots),
    }
    diag = final_output.get("diagnosis_topk", []) if isinstance(final_output, dict) else []
    pred_labels = [x.get("label") for x in diag if isinstance(x, dict) and "label" in x]
    metrics.update(topk_coverage_from_labels(pred_labels, gold_label, gold_ddx_top5, ambiguity))
    return metrics
