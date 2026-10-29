from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

from eval.constants import (
    BENCHMARK_VERSION,
    DATASET_VERSION,
    NO_ORACLE_POLICY_VERSION,
    REQUIRED_DYNAMIC_MAX_TURNS,
    REQUIRED_OS_OCRD_SUBTYPES,
    REQUIRED_SLOT_COUNT,
    SCORING_POLICY_VERSION,
)
from eval.load import load_cases, load_ontology, load_rubrics


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def combined_sha256(paths: Iterable[Path], root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item.relative_to(root))):
        rel = str(path.relative_to(root))
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def dataset_files(root: Path) -> list[Path]:
    return [
        root / "pib_config.yaml",
        root / "ontology" / "labels.yaml",
        root / "ontology" / "slots.yaml",
        root / "ontology" / "svcl_domains.yaml",
        root / "ontology" / "svcl_map.yaml",
        root / "data" / "cases.jsonl",
        root / "data" / "rubrics.jsonl",
        root / "data" / "splits" / "train_ids.txt",
        root / "data" / "splits" / "dev_ids.txt",
        root / "data" / "splits" / "test_ids.txt",
    ]


def scoring_files(root: Path) -> list[Path]:
    return [
        root / "eval" / "constants.py",
        root / "eval" / "risk.py",
        root / "eval" / "scorers" / "ddx_metrics.py",
        root / "eval" / "scorers" / "static_metrics.py",
        root / "eval" / "scorers" / "dynamic_metrics.py",
        root / "eval" / "scorers" / "safety_rules.py",
    ]


def build_manifest(root: Path) -> dict:
    ontology = load_ontology(root / "ontology")
    cases = load_cases(root / "data" / "cases.jsonl", ontology)
    rubrics = load_rubrics(root / "data" / "rubrics.jsonl", ontology, [case.case_id for case in cases])

    dataset_paths = dataset_files(root)
    scoring_paths = scoring_files(root)
    lockfile_path = root / "requirements.lock"
    cases_path = root / "data" / "cases.jsonl"
    rubrics_path = root / "data" / "rubrics.jsonl"
    split_paths = [
        root / "data" / "splits" / "train_ids.txt",
        root / "data" / "splits" / "dev_ids.txt",
        root / "data" / "splits" / "test_ids.txt",
    ]

    psychosis_positive = sum(case.risk_flags.psychosis for case in cases)
    substance_positive = sum(case.risk_flags.substance for case in cases)
    suicide_positive = sum(case.risk_flags.suicide for case in cases)
    violence_positive = sum(case.risk_flags.violence for case in cases)

    return {
        "benchmark_version": BENCHMARK_VERSION,
        "dataset_version": DATASET_VERSION,
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "no_oracle_policy_version": NO_ORACLE_POLICY_VERSION,
        "project_version": BENCHMARK_VERSION,
        "hard_constraints": {
            "slot_count": REQUIRED_SLOT_COUNT,
            "dynamic_max_turns_cap": REQUIRED_DYNAMIC_MAX_TURNS,
            "os_ocrd_subtypes": REQUIRED_OS_OCRD_SUBTYPES,
        },
        "dataset_hash_sha256": combined_sha256(dataset_paths, root),
        "scoring_hash_sha256": combined_sha256(scoring_paths, root),
        "lockfile_hash_sha256": file_sha256(lockfile_path),
        "cases_sha256": file_sha256(cases_path),
        "rubrics_sha256": file_sha256(rubrics_path),
        "splits_sha256": combined_sha256(split_paths, root),
        "dataset_files": [str(path.relative_to(root)) for path in dataset_paths],
        "dataset_file_hashes": {
            str(path.relative_to(root)): file_sha256(path) for path in dataset_paths
        },
        "scoring_files": [str(path.relative_to(root)) for path in scoring_paths],
        "scoring_file_hashes": {
            str(path.relative_to(root)): file_sha256(path) for path in scoring_paths
        },
        "lockfile": str(lockfile_path.relative_to(root)),
        "case_counts": {
            "cases": len(cases),
            "rubrics": len(rubrics),
            "psychosis_positive": psychosis_positive,
            "substance_positive": substance_positive,
            "suicide_positive": suicide_positive,
            "violence_positive": violence_positive,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze PIB benchmark release manifest")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("release/benchmark_manifest.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    payload = build_manifest(root)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        if not args.out.exists():
            print(f"Missing manifest: {args.out}")
            return 1
        current = args.out.read_text(encoding="utf-8")
        if current != serialized:
            print("Manifest drift detected")
            return 1
        print(f"Manifest OK: {args.out}")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(serialized, encoding="utf-8")
    print(f"Release manifest written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
