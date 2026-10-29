from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from eval.constants import BENCHMARK_VERSION, DATASET_VERSION, SCORING_POLICY_VERSION
from eval.load import load_cases, load_ontology


def _label_tokens(label_code: str, labels: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
    tokens = [{"label": label_code, "token": label_code, "token_type": "label_code"}]
    name_cn = labels.get(label_code, {}).get("name_cn")
    if isinstance(name_cn, str) and name_cn:
        tokens.append({"label": label_code, "token": name_cn, "token_type": "label_name_cn"})
    return tokens


def _iter_case_texts(case) -> Iterable[tuple[str, str]]:
    yield "info_variants.minimal_cc", case.info_variants.minimal_cc
    yield "info_variants.self_report", case.info_variants.self_report
    yield "info_variants.chart_full", case.info_variants.chart_full
    for slot_id, utterances in case.patient_script.items():
        for idx, utterance in enumerate(utterances):
            yield f"patient_script.{slot_id}[{idx}]", utterance


def _contains_token(text: str, token: str, token_type: str) -> bool:
    if token_type == "label_code":
        return bool(re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE))
    return token in text


def scan_cases(cases, labels: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for case in cases:
        scan_labels = []
        for label_code in [case.label, *case.gold_ddx_top5]:
            if label_code not in scan_labels:
                scan_labels.append(label_code)
        tokens: List[Dict[str, str]] = []
        for label_code in scan_labels:
            tokens.extend(_label_tokens(label_code, labels))

        for field_path, text in _iter_case_texts(case):
            if not isinstance(text, str) or not text:
                continue
            field_hits = []
            for token_info in tokens:
                if _contains_token(text, token_info["token"], token_info["token_type"]):
                    field_hits.append(token_info)
            if field_hits:
                findings.append(
                    {
                        "case_id": case.case_id,
                        "field_path": field_path,
                        "text": text,
                        "hits": field_hits,
                    }
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan PIB texts for direct gold-label contamination")
    parser.add_argument("--cases", type=Path, default=Path("data/cases.jsonl"))
    parser.add_argument("--ontology", type=Path, default=Path("ontology"))
    parser.add_argument("--out", type=Path, default=Path("results/audit/text_contamination_scan.json"))
    args = parser.parse_args()

    ontology = load_ontology(args.ontology)
    cases = load_cases(args.cases, ontology)
    findings = scan_cases(cases, ontology.labels)
    payload = {
        "benchmark_version": BENCHMARK_VERSION,
        "dataset_version": DATASET_VERSION,
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "cases_path": str(args.cases),
        "ontology_dir": str(args.ontology),
        "scanned_fields": [
            "info_variants.minimal_cc",
            "info_variants.self_report",
            "info_variants.chart_full",
            "patient_script.*",
        ],
        "n_cases": len(cases),
        "contaminated_case_ids": sorted({finding["case_id"] for finding in findings}),
        "contaminated_case_count": len({finding["case_id"] for finding in findings}),
        "hit_count": len(findings),
        "findings": findings,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Text contamination scan written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
