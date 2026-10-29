from __future__ import annotations

from dataclasses import dataclass
from typing import Any


JOB_TYPE_VALIDATE_CURRENT = 'validate_current'
JOB_TYPE_FREEZE_CURRENT = 'freeze_current'
JOB_TYPE_RUN_STATIC = 'run_static'
JOB_TYPE_RUN_DYNAMIC = 'run_dynamic'
JOB_STATUS_QUEUED = 'queued'
JOB_STATUS_RUNNING = 'running'
JOB_STATUS_SUCCEEDED = 'succeeded'
JOB_STATUS_FAILED = 'failed'
TERMINAL_JOB_STATUSES = {JOB_STATUS_SUCCEEDED, JOB_STATUS_FAILED}
RELEASE_STATUS_FROZEN = 'frozen'
RELEASE_STATUS_PARTIAL = 'partial'
RELEASE_STATUS_MISSING = 'missing'
RUN_STATUS_QUEUED = 'queued'
RUN_STATUS_RUNNING = 'running'
RUN_STATUS_COMPLETED = 'completed'
RUN_STATUS_FAILED = 'failed'
RUN_TERMINAL_STATUSES = {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED}


@dataclass(frozen=True)
class ReleaseRegistryRow:
    release_id: str
    label: str
    status: str
    manifest_path: str | None
    bundle_path: str | None
    benchmark_version: str | None
    dataset_version: str | None
    scoring_policy_version: str | None
    dataset_hash_sha256: str | None
    scoring_hash_sha256: str | None
    cases_sha256: str | None
    rubrics_sha256: str | None
    splits_sha256: str | None
    last_validated_job_id: str | None
    last_frozen_job_id: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class JobRow:
    job_id: str
    job_type: str
    status: str
    target_release_id: str | None
    started_at: str | None
    finished_at: str | None
    exit_code: int | None
    stdout_path: str | None
    stderr_path: str | None
    result_json_path: str | None
    error_summary_json: str | None


@dataclass(frozen=True)
class RunRegistryRow:
    run_id: str
    release_id: str
    job_id: str
    run_type: str
    provider: str
    model_name: str
    split_name: str
    status: str
    config_json: str
    results_root: str | None
    metrics_path: str | None
    summary_path: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    error_summary_json: str | None


def error_payload(code: str, message: str, details: dict[str, Any] | None = None, retryable: bool = False) -> dict[str, Any]:
    return {
        'error': {
            'code': code,
            'message': message,
            'details': details,
            'retryable': retryable,
        }
    }
