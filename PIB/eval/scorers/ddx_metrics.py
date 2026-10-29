from __future__ import annotations

from typing import Dict, Sequence


def strict_topk_coverage(pred_labels: Sequence[str], gold_label: str) -> Dict[str, float]:
    top1 = pred_labels[:1]
    top3 = pred_labels[:3]
    top5 = pred_labels[:5]
    return {
        "strict_top1_acc": float(gold_label in top1),
        "strict_top3_cov": float(gold_label in top3),
        "strict_top5_cov": float(gold_label in top5),
    }


def benchmark_gold_labels(
    gold_label: str,
    gold_ddx_top5: Sequence[str],
    ambiguity: str,
) -> list[str]:
    if ambiguity == "ambiguous":
        ranked = [label for label in gold_ddx_top5 if isinstance(label, str)]
        if ranked:
            return ranked[:3]
    return [gold_label]


def benchmark_topk_coverage(
    pred_labels: Sequence[str],
    gold_label: str,
    gold_ddx_top5: Sequence[str],
    ambiguity: str,
) -> Dict[str, float]:
    accepted = set(benchmark_gold_labels(gold_label, gold_ddx_top5, ambiguity))
    top1 = pred_labels[:1]
    top3 = pred_labels[:3]
    top5 = pred_labels[:5]
    return {
        "top1_acc": float(any(label in accepted for label in top1)),
        "top3_cov": float(any(label in accepted for label in top3)),
        "top5_cov": float(any(label in accepted for label in top5)),
        "gold_accept_set_size": float(len(accepted)),
    }
