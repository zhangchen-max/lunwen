from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from eval.constants import (
    REQUIRED_DYNAMIC_MAX_TURNS,
    REQUIRED_OS_OCRD_SUBTYPES,
    REQUIRED_OS_OCRD_SUBTYPES_COUNT,
    REQUIRED_SLOT_COUNT,
)
from eval.risk import required_high_risk_slots
from eval.schema import CaseRecord, RubricRecord


class DataValidationError(ValueError):
    """Raised when dataset or ontology validation fails."""


@dataclass
class BenchmarkConfig:
    path: Path
    version: str
    slot_count: int
    dynamic_max_turns: int
    max_repeat_same_slot: int
    os_ocrd_subtypes: List[str]


@dataclass
class OntologyBundle:
    ontology_dir: Path
    labels: Dict[str, Dict[str, Any]]
    modules: Dict[str, List[str]]
    slot_defs: List[Dict[str, Any]]
    slot_ids: set[str]
    svcl_level_a: List[str]
    svcl_level_b: List[str]
    svcl_domain_set: set[str]
    svcl_map: Dict[str, str]
    config: BenchmarkConfig
    dynamic_max_turns_cap: int
    max_repeat_same_slot: int
    os_ocrd_subtypes: List[str]


@dataclass
class DatasetStats:
    num_cases: int
    num_rubrics: int
    module_counts: Dict[str, int]
    label_counts: Dict[str, int]
    ambiguity_counts: Dict[str, int]
    slot_coverage: Dict[str, int]
    required_svcl_coverage: Dict[str, int]


def read_id_list(path: Path) -> List[str]:
    if not path.exists():
        raise DataValidationError(f"Missing id list: {path}")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_split_ids(splits_dir: Path, split: str) -> List[str]:
    return read_id_list(splits_dir / f"{split}_ids.txt")


def filter_cases_by_ids(cases: Sequence[CaseRecord], selected_ids: Sequence[str]) -> List[CaseRecord]:
    id_set = set(selected_ids)
    return [case for case in cases if case.case_id in id_set]


def filter_rubrics_by_ids(rubrics: Sequence[RubricRecord], selected_ids: Sequence[str]) -> List[RubricRecord]:
    id_set = set(selected_ids)
    return [rubric for rubric in rubrics if rubric.case_id in id_set]


def audit_high_risk_rubric_coverage(
    cases: Sequence[CaseRecord],
    rubrics: Sequence[RubricRecord],
) -> List[Dict[str, Any]]:
    rubric_by_case = {rubric.case_id: rubric for rubric in rubrics}
    findings: List[Dict[str, Any]] = []

    for case in cases:
        rubric = rubric_by_case.get(case.case_id)
        if rubric is None:
            continue
        required = required_high_risk_slots(case.risk_flags.model_dump(), case.slot_truth)
        if not required:
            continue
        missing = {
            risk_name: [slot_id for slot_id in slots if slot_id not in rubric.must_ask_slots]
            for risk_name, slots in required.items()
        }
        missing = {risk_name: slots for risk_name, slots in missing.items() if slots}
        if missing:
            findings.append(
                {
                    "case_id": case.case_id,
                    "label": case.label,
                    "risk_flags": case.risk_flags.model_dump(),
                    "must_ask_slots": list(rubric.must_ask_slots),
                    "required_risk_slots": required,
                    "missing_risk_slots": missing,
                }
            )
    return findings


SLOT_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


def _read_yaml(path: Path) -> Any:
    """Read YAML-like config. Uses PyYAML if available, else expects JSON-compatible content."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise DataValidationError(
                f"Failed to parse {path}. Install pyyaml or provide JSON-compatible content."
            ) from exc


def _default_config_path(ontology_dir: Path) -> Path:
    return ontology_dir.parent / "pib_config.yaml"


def load_benchmark_config(config_path: Path) -> BenchmarkConfig:
    if not config_path.exists():
        raise DataValidationError(f"Missing benchmark config: {config_path}")

    cfg = _read_yaml(config_path)
    version = str(cfg.get("version", ""))
    slot_count = int(cfg.get("slot_count", 0))
    dynamic = cfg.get("dynamic", {})
    labels = cfg.get("labels", {})
    dynamic_max_turns = int(dynamic.get("max_turns", 0))
    max_repeat_same_slot = int(dynamic.get("max_repeat_same_slot", 0))
    os_ocrd_subtypes = list(labels.get("os_ocrd_subtypes", []))

    errors: List[str] = []
    if slot_count != REQUIRED_SLOT_COUNT:
        errors.append(
            f"pib_config.slot_count must be {REQUIRED_SLOT_COUNT}, got {slot_count}"
        )
    if dynamic_max_turns != REQUIRED_DYNAMIC_MAX_TURNS:
        errors.append(
            f"pib_config.dynamic.max_turns must be {REQUIRED_DYNAMIC_MAX_TURNS}, got {dynamic_max_turns}"
        )
    if max_repeat_same_slot <= 0:
        errors.append("pib_config.dynamic.max_repeat_same_slot must be > 0")
    if len(os_ocrd_subtypes) != REQUIRED_OS_OCRD_SUBTYPES_COUNT:
        errors.append(
            "pib_config.labels.os_ocrd_subtypes must contain exactly "
            f"{REQUIRED_OS_OCRD_SUBTYPES_COUNT} entries"
        )
    if os_ocrd_subtypes != REQUIRED_OS_OCRD_SUBTYPES:
        errors.append(
            "pib_config.labels.os_ocrd_subtypes must exactly equal "
            f"{REQUIRED_OS_OCRD_SUBTYPES}"
        )
    if len(set(os_ocrd_subtypes)) != len(os_ocrd_subtypes):
        errors.append("pib_config.labels.os_ocrd_subtypes contains duplicates")

    if errors:
        raise DataValidationError("\n".join(errors))

    return BenchmarkConfig(
        path=config_path,
        version=version,
        slot_count=slot_count,
        dynamic_max_turns=dynamic_max_turns,
        max_repeat_same_slot=max_repeat_same_slot,
        os_ocrd_subtypes=os_ocrd_subtypes,
    )


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise DataValidationError(f"Invalid JSONL at {path}:{i}: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_ontology(ontology_dir: Path, config_path: Path | None = None) -> OntologyBundle:
    config = load_benchmark_config(config_path or _default_config_path(ontology_dir))

    labels_cfg = _read_yaml(ontology_dir / "labels.yaml")
    svcl_cfg = _read_yaml(ontology_dir / "svcl_domains.yaml")
    slot_defs = _read_yaml(ontology_dir / "slots.yaml")
    svcl_map = _read_yaml(ontology_dir / "svcl_map.yaml")

    modules = labels_cfg.get("modules", {})
    labels = labels_cfg.get("labels", {})

    slot_ids: List[str] = []
    for slot in slot_defs:
        slot_id = slot.get("slot_id")
        if not slot_id:
            raise DataValidationError("ontology/slots.yaml contains slot without slot_id")
        if not SLOT_ID_PATTERN.fullmatch(slot_id):
            raise DataValidationError(
                f"ontology/slots.yaml contains invalid slot_id '{slot_id}': must match [a-z0-9_]+"
            )
        slot_ids.append(slot_id)

    if len(slot_ids) != len(set(slot_ids)):
        duplicates = sorted({x for x in slot_ids if slot_ids.count(x) > 1})
        raise DataValidationError(f"Duplicate slot_id in slots.yaml: {duplicates}")

    if len(slot_ids) != config.slot_count:
        raise DataValidationError(
            f"slot_count mismatch: expected {config.slot_count}, got {len(slot_ids)}"
        )

    level_a = list(svcl_cfg.get("level_a", []))
    level_b = list(svcl_cfg.get("level_b", []))
    domain_set = set(level_a) | set(level_b)

    invalid_map_slots = [slot for slot in svcl_map.keys() if slot not in set(slot_ids)]
    if invalid_map_slots:
        raise DataValidationError(f"svcl_map references unknown slots: {sorted(invalid_map_slots)}")

    invalid_map_domains = [d for d in svcl_map.values() if d not in domain_set]
    if invalid_map_domains:
        raise DataValidationError(
            f"svcl_map references unknown domains: {sorted(set(invalid_map_domains))}"
        )

    os_ocrd_label = labels.get("OS_OCRD")
    if not isinstance(os_ocrd_label, dict):
        raise DataValidationError("labels.yaml must define labels.OS_OCRD")

    if not bool(os_ocrd_label.get("require_subtype")):
        raise DataValidationError("labels.OS_OCRD.require_subtype must be true")

    allowed_subtypes = list(os_ocrd_label.get("allowed_subtypes", []))
    if allowed_subtypes != config.os_ocrd_subtypes:
        raise DataValidationError(
            "labels.OS_OCRD.allowed_subtypes must exactly match "
            f"pib_config.labels.os_ocrd_subtypes ({config.os_ocrd_subtypes})"
        )

    return OntologyBundle(
        ontology_dir=ontology_dir,
        labels=labels,
        modules=modules,
        slot_defs=slot_defs,
        slot_ids=set(slot_ids),
        svcl_level_a=level_a,
        svcl_level_b=level_b,
        svcl_domain_set=domain_set,
        svcl_map=svcl_map,
        config=config,
        dynamic_max_turns_cap=config.dynamic_max_turns,
        max_repeat_same_slot=config.max_repeat_same_slot,
        os_ocrd_subtypes=config.os_ocrd_subtypes,
    )


def _validate_case_against_ontology(case: CaseRecord, ontology: OntologyBundle) -> List[str]:
    errors: List[str] = []

    if case.label not in ontology.labels:
        errors.append(f"label '{case.label}' is not defined in labels.yaml")
    else:
        expected_module = ontology.labels[case.label].get("module")
        if expected_module != case.dsm_module:
            errors.append(
                f"dsm_module '{case.dsm_module}' mismatch with label '{case.label}' module '{expected_module}'"
            )

    invalid_domains = sorted(set(case.required_svcl_domains) - ontology.svcl_domain_set)
    if invalid_domains:
        errors.append(f"required_svcl_domains contains unknown domains: {invalid_domains}")

    unknown_slots = sorted(set(case.slot_truth.keys()) - ontology.slot_ids)
    if unknown_slots:
        errors.append(f"slot_truth contains unknown slot(s): {unknown_slots}")

    invalid_script_slots = sorted(
        set(k for k in case.patient_script.keys() if k != "unknown_default") - ontology.slot_ids
    )
    if invalid_script_slots:
        errors.append(f"patient_script contains unknown slot(s): {invalid_script_slots}")

    if case.label == "OS_OCRD":
        if not case.label_subtype:
            errors.append("label_subtype is required when label == OS_OCRD")
        elif case.label_subtype not in ontology.os_ocrd_subtypes:
            errors.append(
                "label_subtype must be one of "
                f"{ontology.os_ocrd_subtypes} when label == OS_OCRD"
            )

    return errors


def load_cases(cases_path: Path, ontology: OntologyBundle) -> List[CaseRecord]:
    raw_rows = read_jsonl(cases_path)
    seen_case_ids: set[str] = set()
    errors: List[str] = []
    cases: List[CaseRecord] = []

    for idx, row in enumerate(raw_rows, start=1):
        try:
            case = CaseRecord.model_validate(row)
        except Exception as exc:
            errors.append(f"[row {idx}] schema error: {exc}")
            continue

        if case.case_id in seen_case_ids:
            errors.append(f"[row {idx}] duplicated case_id: {case.case_id}")
            continue
        seen_case_ids.add(case.case_id)

        semantic_errors = _validate_case_against_ontology(case, ontology)
        for msg in semantic_errors:
            errors.append(f"[{case.case_id}] {msg}")

        cases.append(case)

    if errors:
        raise DataValidationError("\n".join(errors))

    return cases


def _validate_rubric_against_ontology(
    rubric: RubricRecord,
    ontology: OntologyBundle,
    case_id_set: set[str] | None,
) -> List[str]:
    errors: List[str] = []

    if case_id_set is not None and rubric.case_id not in case_id_set:
        errors.append(f"case_id '{rubric.case_id}' does not exist in cases")

    unknown_slots = sorted(set(rubric.must_ask_slots) - ontology.slot_ids)
    if unknown_slots:
        errors.append(f"must_ask_slots contains unknown slot(s): {unknown_slots}")

    if rubric.must_ask_svcl_domains:
        invalid_domains = sorted(set(rubric.must_ask_svcl_domains) - ontology.svcl_domain_set)
        if invalid_domains:
            errors.append(f"must_ask_svcl_domains contains unknown domain(s): {invalid_domains}")

    if rubric.stop_rules.max_turns > ontology.dynamic_max_turns_cap:
        errors.append(
            "stop_rules.max_turns exceeds global cap "
            f"{ontology.dynamic_max_turns_cap}: {rubric.stop_rules.max_turns}"
        )

    return errors


def load_rubrics(
    rubrics_path: Path,
    ontology: OntologyBundle,
    case_ids: Sequence[str] | None = None,
) -> List[RubricRecord]:
    raw_rows = read_jsonl(rubrics_path)
    seen_case_ids: set[str] = set()
    case_id_set = set(case_ids) if case_ids else None
    errors: List[str] = []
    rubrics: List[RubricRecord] = []

    for idx, row in enumerate(raw_rows, start=1):
        try:
            rubric = RubricRecord.model_validate(row)
        except Exception as exc:
            errors.append(f"[row {idx}] schema error: {exc}")
            continue

        if rubric.case_id in seen_case_ids:
            errors.append(f"[row {idx}] duplicated case_id: {rubric.case_id}")
            continue
        seen_case_ids.add(rubric.case_id)

        semantic_errors = _validate_rubric_against_ontology(rubric, ontology, case_id_set)
        for msg in semantic_errors:
            errors.append(f"[{rubric.case_id}] {msg}")

        rubrics.append(rubric)

    if case_id_set is not None:
        missing = sorted(case_id_set - seen_case_ids)
        if missing:
            errors.append(f"rubrics missing case_id(s): {missing}")

    if errors:
        raise DataValidationError("\n".join(errors))

    return rubrics


def derive_domains_from_slots(slots: Sequence[str], svcl_map: Dict[str, str]) -> List[str]:
    return sorted({svcl_map[s] for s in slots if s in svcl_map})


def build_stats(cases: Sequence[CaseRecord], rubrics: Sequence[RubricRecord]) -> DatasetStats:
    module_counts: Dict[str, int] = {}
    label_counts: Dict[str, int] = {}
    ambiguity_counts: Dict[str, int] = {}
    slot_coverage: Dict[str, int] = {}
    svcl_coverage: Dict[str, int] = {}

    for case in cases:
        module_counts[case.dsm_module] = module_counts.get(case.dsm_module, 0) + 1
        label_counts[case.label] = label_counts.get(case.label, 0) + 1
        ambiguity_counts[case.ambiguity] = ambiguity_counts.get(case.ambiguity, 0) + 1
        for slot_id in case.slot_truth:
            slot_coverage[slot_id] = slot_coverage.get(slot_id, 0) + 1
        for domain in case.required_svcl_domains:
            svcl_coverage[domain] = svcl_coverage.get(domain, 0) + 1

    return DatasetStats(
        num_cases=len(cases),
        num_rubrics=len(rubrics),
        module_counts=dict(sorted(module_counts.items())),
        label_counts=dict(sorted(label_counts.items())),
        ambiguity_counts=dict(sorted(ambiguity_counts.items())),
        slot_coverage=dict(sorted(slot_coverage.items())),
        required_svcl_coverage=dict(sorted(svcl_coverage.items())),
    )
