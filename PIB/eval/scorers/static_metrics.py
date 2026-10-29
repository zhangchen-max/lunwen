from __future__ import annotations

from typing import Any, Dict, Iterable, Sequence

from eval.scorers.ddx_metrics import benchmark_topk_coverage, strict_topk_coverage


def required_slot_coverage(pred_slots: Iterable[str], required_slots: Sequence[str]) -> float:
    required = set(required_slots)
    if not required:
        return 1.0
    predicted = set(pred_slots)
    return len(required & predicted) / len(required)


def topk_coverage(pred_labels: Sequence[str], gold_label: str) -> Dict[str, float]:
    top1 = pred_labels[:1]
    top3 = pred_labels[:3]
    top5 = pred_labels[:5]
    return {
        "top1_acc": float(gold_label in top1),
        "top3_cov": float(gold_label in top3),
        "top5_cov": float(gold_label in top5),
    }


def exact_match_accuracy(
    slot_predictions: Dict[str, Any],
    slot_truth: Dict[str, Any],
    target_slots: Sequence[str] | None = None,
) -> float:
    slots = list(target_slots) if target_slots else list(slot_truth.keys())
    if not slots:
        return 1.0
    hit = 0
    for slot_id in slots:
        if slot_id not in slot_truth:
            continue
        if slot_predictions.get(slot_id) == slot_truth[slot_id]:
            hit += 1
    return hit / len(slots)


def score_static_case(
    gold_label: str,
    gold_ddx_top5: Sequence[str],
    ambiguity: str,
    pred_labels: Sequence[str],
    slot_predictions: Dict[str, Any],
    slot_truth: Dict[str, Any],
    required_slots: Sequence[str],
) -> Dict[str, float]:
    metrics = {
        "required_slot_coverage": required_slot_coverage(slot_predictions.keys(), required_slots),
        "slot_exact_match": exact_match_accuracy(slot_predictions, slot_truth, required_slots),
    }
    metrics.update(strict_topk_coverage(pred_labels, gold_label))
    metrics.update(benchmark_topk_coverage(pred_labels, gold_label, gold_ddx_top5, ambiguity))
    return metrics
