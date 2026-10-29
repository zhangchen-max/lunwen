from __future__ import annotations

import argparse
from pathlib import Path

from eval.constants import (
    REQUIRED_DYNAMIC_MAX_TURNS,
    REQUIRED_OS_OCRD_SUBTYPES_COUNT,
    REQUIRED_SLOT_COUNT,
)
from eval.load import (
    DataValidationError,
    audit_high_risk_rubric_coverage,
    build_stats,
    load_cases,
    load_ontology,
    load_rubrics,
)


def _print_distribution(title: str, values: dict[str, int]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    for key, count in values.items():
        print(f"{key}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PIB ontology/cases/rubrics")
    parser.add_argument("--cases", type=Path, default=Path("data/cases.jsonl"))
    parser.add_argument("--rubrics", type=Path, default=Path("data/rubrics.jsonl"))
    parser.add_argument("--ontology", type=Path, default=Path("ontology"))
    parser.add_argument("--config", type=Path, default=Path("pib_config.yaml"))
    args = parser.parse_args()

    try:
        ont = load_ontology(args.ontology, config_path=args.config)
        case_records = load_cases(args.cases, ont)
        rubric_records = load_rubrics(args.rubrics, ont, [c.case_id for c in case_records])
    except DataValidationError as exc:
        print("Validation failed")
        print(exc)
        return 1

    high_risk_findings = audit_high_risk_rubric_coverage(case_records, rubric_records)
    if high_risk_findings:
        print("Validation failed")
        print("High-risk rubric coverage gaps detected:")
        for finding in high_risk_findings:
            print(
                f"- {finding['case_id']} {finding['label']} missing "
                f"{finding['missing_risk_slots']} from must_ask_slots"
            )
        return 1

    stats = build_stats(case_records, rubric_records)

    print("Validation passed")
    print("Hard constraints")
    print(f"- slot_count={REQUIRED_SLOT_COUNT}")
    print(f"- dynamic.max_turns_cap={REQUIRED_DYNAMIC_MAX_TURNS}")
    print(f"- os_ocrd_subtypes_count={REQUIRED_OS_OCRD_SUBTYPES_COUNT}")
    print(f"- config={ont.config.path}")
    print(f"Cases: {stats.num_cases}")
    print(f"Rubrics: {stats.num_rubrics}")
    print(f"Slots in ontology: {len(ont.slot_ids)}")
    print(f"SVCL domains: {len(ont.svcl_domain_set)}")

    _print_distribution("Module Distribution", stats.module_counts)
    _print_distribution("Label Distribution", stats.label_counts)
    _print_distribution("Ambiguity Distribution", stats.ambiguity_counts)
    _print_distribution("Required SVCL Coverage", stats.required_svcl_coverage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
