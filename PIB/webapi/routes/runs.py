from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

from webapi import artifacts as artifact_service
from webapi import jobs as run_jobs
from webapi.core_adapters import releases as releases_adapter
from webapi.core_adapters import reports as reports_adapter
from webapi.core_adapters import runs as runs_adapter

ERROR_STATUS = {
    'release_not_found': HTTPStatus.NOT_FOUND,
    'invalid_run_type': HTTPStatus.BAD_REQUEST,
    'invalid_request': HTTPStatus.BAD_REQUEST,
    'run_job_create_failed': HTTPStatus.INTERNAL_SERVER_ERROR,
    'run_not_found': HTTPStatus.NOT_FOUND,
    'summary_projection_failed': HTTPStatus.INTERNAL_SERVER_ERROR,
    'artifact_index_failed': HTTPStatus.INTERNAL_SERVER_ERROR,
    'artifact_not_found': HTTPStatus.NOT_FOUND,
    'artifact_path_not_allowed': HTTPStatus.BAD_REQUEST,
}


def error_payload(code: str, message: str, details: dict[str, Any] | None = None, retryable: bool = False) -> dict[str, Any]:
    return {
        'error': {
            'code': code,
            'message': message,
            'details': details,
            'retryable': retryable,
        }
    }


def get_run_options(repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, runs_adapter.list_run_options(repo_root or releases_adapter.REPO_ROOT)
    except runs_adapter.RunAdapterError as exc:
        status = ERROR_STATUS.get(exc.code, HTTPStatus.INTERNAL_SERVER_ERROR)
        return status, error_payload(exc.code, exc.message, exc.details)


def post_run(payload: dict[str, Any], repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    repo_root = repo_root or releases_adapter.REPO_ROOT
    try:
        config = runs_adapter.normalize_create_run_request(payload, repo_root=repo_root)
        run = run_jobs.create_run_job(repo_root, config)
        return HTTPStatus.ACCEPTED, {
            'run_id': run['run_id'],
            'job_id': run['job_id'],
            'status': run['status'],
            'redirect_url': f"/runs/{run['run_id']}",
        }
    except runs_adapter.RunAdapterError as exc:
        status = ERROR_STATUS.get(exc.code, HTTPStatus.BAD_REQUEST)
        return status, error_payload(exc.code, exc.message, exc.details)
    except Exception as exc:  # pragma: no cover - defensive
        return HTTPStatus.INTERNAL_SERVER_ERROR, error_payload(
            'run_job_create_failed',
            f'Failed to create run job: {exc}',
            None,
        )


def get_run(run_id: str, repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, run_jobs.get_run_status(repo_root or releases_adapter.REPO_ROOT, run_id)
    except KeyError:
        return HTTPStatus.NOT_FOUND, error_payload('run_not_found', f'Unknown run_id: {run_id}')


def get_run_summary(run_id: str, repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, reports_adapter.build_run_summary_projection(run_id, repo_root or releases_adapter.REPO_ROOT)
    except KeyError:
        return HTTPStatus.NOT_FOUND, error_payload('run_not_found', f'Unknown run_id: {run_id}')
    except reports_adapter.SummaryProjectionError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, error_payload('summary_projection_failed', str(exc))


def get_run_artifacts(run_id: str, repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, artifact_service.list_run_artifacts(run_id, repo_root or releases_adapter.REPO_ROOT)
    except KeyError:
        return HTTPStatus.NOT_FOUND, error_payload('run_not_found', f'Unknown run_id: {run_id}')
    except artifact_service.ArtifactIndexError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, error_payload('artifact_index_failed', exc.message)
