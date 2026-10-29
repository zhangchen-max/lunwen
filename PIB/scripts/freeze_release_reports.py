from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from eval.constants import BENCHMARK_VERSION, NO_ORACLE_POLICY_VERSION, SCORING_POLICY_VERSION


def _latest_run_dir(output_jsonl: Path) -> Path:
    artifact_root = output_jsonl.with_suffix("")
    runs = sorted(artifact_root.glob("run_*"))
    if not runs:
        raise SystemExit(f"No runs found under {artifact_root}")
    return runs[-1]


def _load_metrics(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _overall(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return metrics["summary"]["overall"]


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _deprecated_dummy_results() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    legacy_file = Path("results/dynamic/dummy_dynamic.jsonl")
    items.append(
        {
            "path": str(legacy_file),
            "kind": "legacy_output_jsonl",
            "deprecated_reason": "pre-no-oracle-fix dynamic dummy consumed rubric.must_ask_slots",
        }
    )
    for idx in range(1, 5):
        run_dir = Path("results/dynamic/test_dynamic") / f"run_{idx:03d}"
        items.append(
            {
                "path": str(run_dir),
                "kind": "run_artifact_dir",
                "deprecated_reason": "pre-no-oracle-fix dynamic dummy consumed rubric.must_ask_slots",
            }
        )
    return items


def _mark_deprecated(items: List[Dict[str, Any]]) -> None:
    note = (
        f"DEPRECATED for release candidate {BENCHMARK_VERSION}.\n"
        "Reason: pre-no-oracle-fix dynamic dummy consumed rubric.must_ask_slots and is not a valid pure baseline.\n"
        "Use results/dynamic/test_dynamic/run_005+ instead.\n"
    )
    for item in items:
        path = Path(item["path"])
        if path.is_dir():
            marker = path / "DEPRECATED.txt"
        else:
            marker = path.with_name(path.name + ".DEPRECATED.txt")
        marker.write_text(note, encoding="utf-8")
        item["deprecation_marker"] = str(marker)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze release baseline reports and deprecation registry")
    parser.add_argument("--static-output", type=Path, default=Path("results/static/test_static.jsonl"))
    parser.add_argument("--dynamic-output", type=Path, default=Path("results/dynamic/test_dynamic.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("results/reports"))
    args = parser.parse_args()

    static_run = _latest_run_dir(args.static_output)
    dynamic_run = _latest_run_dir(args.dynamic_output)
    static_metrics = _load_metrics(static_run / "metrics.json")
    dynamic_metrics = _load_metrics(dynamic_run / "metrics.json")

    pure_baselines = [
        {
            "baseline_group": "pure",
            "baseline_name": "static_heuristic",
            "task": "static",
            "status": "active",
            "oracle_policy": "no_oracle",
            "split": static_metrics["run_config"]["split"],
            "metrics_json": str(static_run / "metrics.json"),
            "predictions_jsonl": str(static_run / "predictions.jsonl"),
            "n_cases": static_metrics["n_cases"],
            "top1_acc": _overall(static_metrics).get("top1_acc"),
            "top5_cov": _overall(static_metrics).get("top5_cov"),
            "must_ask_hit_rate": _overall(static_metrics).get("must_ask_hit_rate"),
            "turns": _overall(static_metrics).get("turns"),
            "harm_flags_count": _overall(static_metrics).get("harm_flags_count"),
        },
        {
            "baseline_group": "pure",
            "baseline_name": "dynamic_dummy",
            "task": "dynamic",
            "status": "active",
            "oracle_policy": "no_oracle",
            "split": dynamic_metrics["run_config"]["split"],
            "metrics_json": str(dynamic_run / "metrics.json"),
            "predictions_jsonl": str(dynamic_run / "predictions.jsonl"),
            "n_cases": dynamic_metrics["n_cases"],
            "top1_acc": _overall(dynamic_metrics).get("top1_acc"),
            "top5_cov": _overall(dynamic_metrics).get("top5_cov"),
            "must_ask_hit_rate": _overall(dynamic_metrics).get("must_ask_hit_rate"),
            "turns": _overall(dynamic_metrics).get("turns"),
            "harm_flags_count": _overall(dynamic_metrics).get("harm_flags_count"),
        },
    ]

    guided_llm_baselines = [
        {
            "baseline_group": "guided_llm",
            "baseline_name": "static_llm_guided",
            "task": "static",
            "status": "reported_separately",
            "oracle_policy": "guided",
            "split": "test",
            "metrics_json": None,
            "predictions_jsonl": None,
            "note": "LLM baseline receives ontology-guided structured prompts and is excluded from the pure baseline main table.",
        },
        {
            "baseline_group": "guided_llm",
            "baseline_name": "dynamic_llm_guided",
            "task": "dynamic",
            "status": "reported_separately",
            "oracle_policy": "guided",
            "split": "test",
            "metrics_json": None,
            "predictions_jsonl": None,
            "note": "LLM baseline receives ontology-guided structured prompts and is excluded from the pure baseline main table.",
        },
    ]

    deprecated = _deprecated_dummy_results()
    _mark_deprecated(deprecated)

    payload = {
        "benchmark_version": BENCHMARK_VERSION,
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "no_oracle_policy_version": NO_ORACLE_POLICY_VERSION,
        "pure_baselines": pure_baselines,
        "guided_llm_baselines": guided_llm_baselines,
        "deprecated_results": deprecated,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "baseline_groups.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "deprecated_results.json").write_text(
        json.dumps(
            {
                "benchmark_version": BENCHMARK_VERSION,
                "deprecated_results": deprecated,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(args.out_dir / "pure_baselines.csv", pure_baselines)
    _write_csv(args.out_dir / "guided_llm_baselines.csv", guided_llm_baselines)
    print(f"Release baseline reports written to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
