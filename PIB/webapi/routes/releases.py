from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

from webapi.core_adapters import releases as releases_adapter
from webapi import jobs as release_jobs


ERROR_STATUS = {
    "release_not_found": HTTPStatus.NOT_FOUND,
    "manifest_missing": HTTPStatus.INTERNAL_SERVER_ERROR,
    "artifact_scan_failed": HTTPStatus.INTERNAL_SERVER_ERROR,
    "job_not_found": HTTPStatus.NOT_FOUND,
}


def error_payload(code: str, message: str, details: dict[str, Any] | None = None, retryable: bool = False) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "retryable": retryable,
        }
    }


def get_releases(repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, releases_adapter.list_releases(repo_root=repo_root)
    except releases_adapter.ReleaseAdapterError as exc:
        status = ERROR_STATUS.get(exc.code, HTTPStatus.INTERNAL_SERVER_ERROR)
        return status, error_payload(exc.code, exc.message, exc.details)


def get_release_detail(release_id: str, repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, releases_adapter.get_release_detail(release_id, repo_root=repo_root)
    except releases_adapter.ReleaseAdapterError as exc:
        status = ERROR_STATUS.get(exc.code, HTTPStatus.INTERNAL_SERVER_ERROR)
        return status, error_payload(exc.code, exc.message, exc.details)


def post_validate_current(repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.ACCEPTED, release_jobs.create_validate_current_job(repo_root or releases_adapter.REPO_ROOT)
    except releases_adapter.ReleaseAdapterError as exc:
        status = ERROR_STATUS.get(exc.code, HTTPStatus.INTERNAL_SERVER_ERROR)
        return status, error_payload(exc.code, exc.message, exc.details)


def post_freeze_current(repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.ACCEPTED, release_jobs.create_freeze_current_job(repo_root or releases_adapter.REPO_ROOT)
    except releases_adapter.ReleaseAdapterError as exc:
        status = ERROR_STATUS.get(exc.code, HTTPStatus.INTERNAL_SERVER_ERROR)
        return status, error_payload(exc.code, exc.message, exc.details)


def get_job(job_id: str, repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, release_jobs.get_job_status(repo_root or releases_adapter.REPO_ROOT, job_id)
    except KeyError:
        return HTTPStatus.NOT_FOUND, error_payload("job_not_found", f"Unknown job_id: {job_id}")
