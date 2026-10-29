from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from webapi import db
from webapi.models import RELEASE_STATUS_FROZEN, RELEASE_STATUS_PARTIAL

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_RELATIVE_PATH = Path("release/benchmark_manifest.json")
RELEASE_BUNDLE_PREFIX = "PIB-Benchmark-"
REPORT_FILES = {
    "pure_baselines": Path("results/reports/pure_baselines.csv"),
    "guided_llm_baselines": Path("results/reports/guided_llm_baselines.csv"),
    "deprecated_results": Path("results/reports/deprecated_results.json"),
}
PRIMARY_AUDITS = {
    "no_oracle": Path("results/audit/no_oracle_baselines.json"),
    "text_contamination": Path("results/audit/text_contamination_scan.json"),
}


class ReleaseAdapterError(Exception):
    code = "artifact_scan_failed"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ManifestMissingError(ReleaseAdapterError):
    code = "manifest_missing"


class ReleaseNotFoundError(ReleaseAdapterError):
    code = "release_not_found"


@dataclass(frozen=True)
class ReleaseRecord:
    release_id: str
    label: str
    status: str
    manifest_path: str
    bundle_path: str | None
    benchmark_version: str | None
    scoring_policy_version: str | None
    dataset_hash_sha256: str | None
    scoring_hash_sha256: str | None
    cases_sha256: str | None
    rubrics_sha256: str | None
    splits_sha256: str | None
    dataset_version: str | None
    baseline_reports: list[str]
    audit_reports: list[str]
    deprecated_results_path: str | None
    last_validated_job_id: str | None = None
    last_frozen_job_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


def repo_relative(path: Path, repo_root: Path) -> str:
    return str(path.relative_to(repo_root))


def normalize_release_id(raw_version: str | None) -> str | None:
    if not raw_version:
        return None
    return raw_version if raw_version.startswith("v") else f"v{raw_version}"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestMissingError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseAdapterError(f"Invalid JSON file: {path}") from exc


def read_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    return _read_json(repo_root / MANIFEST_RELATIVE_PATH)


def _safe_read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _bundle_dirs(repo_root: Path) -> list[Path]:
    release_root = repo_root / "release"
    if not release_root.exists():
        return []
    return sorted(
        path for path in release_root.iterdir() if path.is_dir() and path.name.startswith(RELEASE_BUNDLE_PREFIX)
    )


def _bundle_dir_by_release_id(repo_root: Path) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for bundle_dir in _bundle_dirs(repo_root):
        manifest_path = bundle_dir / "benchmark_manifest.json"
        manifest = _safe_read_optional_json(manifest_path)
        if not manifest:
            continue
        release_id = normalize_release_id(manifest.get("benchmark_version"))
        if isinstance(release_id, str) and release_id:
            mapping[release_id] = bundle_dir
    return mapping


def _collect_report_paths(repo_root: Path) -> tuple[dict[str, str | None], list[str], str | None]:
    report_map: dict[str, str | None] = {}
    baseline_reports: list[str] = []
    deprecated_results_path: str | None = None
    for key, relative_path in REPORT_FILES.items():
        full_path = repo_root / relative_path
        if full_path.exists():
            rel = repo_relative(full_path, repo_root)
            report_map[key] = rel
            if key == "deprecated_results":
                deprecated_results_path = rel
            else:
                baseline_reports.append(rel)
        else:
            report_map[key] = None
    return report_map, baseline_reports, deprecated_results_path


def _collect_audit_paths(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    audit_root = repo_root / "results" / "audit"
    other_paths: list[str] = []
    primary: dict[str, Any] = {}
    for key, relative_path in PRIMARY_AUDITS.items():
        full_path = repo_root / relative_path
        primary[key] = repo_relative(full_path, repo_root) if full_path.exists() else None
    if audit_root.exists():
        for full_path in sorted(audit_root.glob("*")):
            if not full_path.is_file():
                continue
            rel = repo_relative(full_path, repo_root)
            if rel not in primary.values():
                other_paths.append(rel)
    primary["other"] = other_paths
    audit_reports = [path for path in primary.values() if isinstance(path, str)] + other_paths
    return primary, audit_reports


def _manifest_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    hard_constraints = manifest.get("hard_constraints", {})
    return {
        "benchmark_version": manifest.get("benchmark_version"),
        "dataset_version": manifest.get("dataset_version"),
        "scoring_policy_version": manifest.get("scoring_policy_version"),
        "no_oracle_policy_version": manifest.get("no_oracle_policy_version"),
        "slot_count": hard_constraints.get("slot_count"),
        "dynamic_max_turns": hard_constraints.get("dynamic_max_turns_cap"),
        "os_ocrd_subtypes": hard_constraints.get("os_ocrd_subtypes"),
        "dataset_hash_sha256": manifest.get("dataset_hash_sha256"),
        "scoring_hash_sha256": manifest.get("scoring_hash_sha256"),
        "cases_sha256": manifest.get("cases_sha256"),
        "rubrics_sha256": manifest.get("rubrics_sha256"),
        "splits_sha256": manifest.get("splits_sha256"),
    }


def _release_status(bundle_missing: bool) -> str:
    return RELEASE_STATUS_PARTIAL if bundle_missing else RELEASE_STATUS_FROZEN


def _merge_registry_fields(repo_root: Path, record: ReleaseRecord) -> ReleaseRecord:
    registry_row = db.get_release(repo_root, record.release_id)
    if registry_row is None:
        return record
    return ReleaseRecord(
        **{
            **record.__dict__,
            "status": registry_row.status or record.status,
            "last_validated_job_id": registry_row.last_validated_job_id,
            "last_frozen_job_id": registry_row.last_frozen_job_id,
            "created_at": registry_row.created_at,
            "updated_at": registry_row.updated_at,
        }
    )


def _bundle_summary(bundle_dir: Path | None, repo_root: Path) -> tuple[dict[str, Any], bool]:
    if bundle_dir is None:
        return {"path": None, "files": []}, True
    files = []
    for file_path in sorted(bundle_dir.rglob("*")):
        if not file_path.is_file():
            continue
        files.append(
            {
                "name": file_path.name,
                "path": repo_relative(file_path, repo_root),
                "size": file_path.stat().st_size,
            }
        )
    return {
        "path": repo_relative(bundle_dir, repo_root) + "/",
        "files": files,
    }, False


def _build_release_record(repo_root: Path, manifest_path: Path, manifest: dict[str, Any]) -> ReleaseRecord:
    release_id = normalize_release_id(manifest.get("benchmark_version"))
    if not isinstance(release_id, str) or not release_id:
        raise ReleaseAdapterError("benchmark_version missing from manifest")
    bundle_by_release = _bundle_dir_by_release_id(repo_root)
    bundle_dir = bundle_by_release.get(release_id)
    _, bundle_missing = _bundle_summary(bundle_dir, repo_root)
    _, baseline_reports, deprecated_results_path = _collect_report_paths(repo_root)
    _, audit_reports = _collect_audit_paths(repo_root)
    record = ReleaseRecord(
        release_id=release_id,
        label=f"PIB Benchmark {release_id}",
        status=_release_status(bundle_missing),
        manifest_path=repo_relative(manifest_path, repo_root),
        bundle_path=(repo_relative(bundle_dir, repo_root) + "/") if bundle_dir else None,
        benchmark_version=manifest.get("benchmark_version"),
        dataset_version=manifest.get("dataset_version"),
        scoring_policy_version=manifest.get("scoring_policy_version"),
        dataset_hash_sha256=manifest.get("dataset_hash_sha256"),
        scoring_hash_sha256=manifest.get("scoring_hash_sha256"),
        cases_sha256=manifest.get("cases_sha256"),
        rubrics_sha256=manifest.get("rubrics_sha256"),
        splits_sha256=manifest.get("splits_sha256"),
        baseline_reports=baseline_reports,
        audit_reports=audit_reports,
        deprecated_results_path=deprecated_results_path,
    )
    return _merge_registry_fields(repo_root, record)


def sync_current_release_registry(
    repo_root: Path | None = None,
    *,
    last_validated_job_id: str | None = None,
    last_frozen_job_id: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    manifest_path = repo_root / MANIFEST_RELATIVE_PATH
    manifest = read_manifest(repo_root)
    record = _build_release_record(repo_root, manifest_path, manifest)
    db.upsert_release(
        repo_root,
        {
            "release_id": record.release_id,
            "label": record.label,
            "status": record.status,
            "manifest_path": record.manifest_path,
            "bundle_path": record.bundle_path,
            "benchmark_version": record.benchmark_version,
            "dataset_version": record.dataset_version,
            "scoring_policy_version": record.scoring_policy_version,
            "dataset_hash_sha256": record.dataset_hash_sha256,
            "scoring_hash_sha256": record.scoring_hash_sha256,
            "cases_sha256": record.cases_sha256,
            "rubrics_sha256": record.rubrics_sha256,
            "splits_sha256": record.splits_sha256,
        },
        last_validated_job_id=last_validated_job_id,
        last_frozen_job_id=last_frozen_job_id,
    )
    merged = _merge_registry_fields(repo_root, record)
    return merged.__dict__


def list_releases(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    manifest_path = repo_root / MANIFEST_RELATIVE_PATH
    manifest = read_manifest(repo_root)
    sync_current_release_registry(repo_root)
    record = _build_release_record(repo_root, manifest_path, manifest)
    return {
        "items": [record.__dict__],
    }


def get_release_detail(release_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    manifest_path = repo_root / MANIFEST_RELATIVE_PATH
    manifest = read_manifest(repo_root)
    current_release_id = normalize_release_id(manifest.get("benchmark_version"))
    if release_id != current_release_id:
        bundle_manifest = None
        for bundle_dir in _bundle_dirs(repo_root):
            manifest_candidate = _safe_read_optional_json(bundle_dir / "benchmark_manifest.json")
            if manifest_candidate and normalize_release_id(manifest_candidate.get("benchmark_version")) == release_id:
                bundle_manifest = manifest_candidate
                break
        if bundle_manifest is None:
            raise ReleaseNotFoundError(f"Unknown release_id: {release_id}")
        manifest = bundle_manifest

    sync_current_release_registry(repo_root)
    record = _build_release_record(repo_root, manifest_path, manifest)
    bundle_by_release = _bundle_dir_by_release_id(repo_root)
    bundle_dir = bundle_by_release.get(release_id)
    reports, _, _ = _collect_report_paths(repo_root)
    audits, _ = _collect_audit_paths(repo_root)
    bundle, partial = _bundle_summary(bundle_dir, repo_root)

    detail = {
        "release_id": release_id,
        "label": record.label,
        "status": record.status,
        "registry": {
            "last_validated_job_id": record.last_validated_job_id,
            "last_frozen_job_id": record.last_frozen_job_id,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        },
        "manifest": _manifest_summary(manifest),
        "bundle": bundle,
        "reports": reports,
        "audits": audits,
    }
    if partial:
        detail["partial"] = True
        detail["state"] = "partial"
    else:
        detail["state"] = "success"
    return detail
