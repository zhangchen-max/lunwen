from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

from webapi.core_adapters import releases as releases_adapter
from webapi.core_adapters import reports as reports_adapter

ERROR_STATUS = {
    'run_not_found': HTTPStatus.NOT_FOUND,
    'slice_projection_failed': HTTPStatus.INTERNAL_SERVER_ERROR,
    'case_list_projection_failed': HTTPStatus.INTERNAL_SERVER_ERROR,
    'run_not_ready': HTTPStatus.CONFLICT,
    'case_not_found': HTTPStatus.NOT_FOUND,
    'case_projection_failed': HTTPStatus.INTERNAL_SERVER_ERROR,
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


def get_run_slices(run_id: str, repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, reports_adapter.build_slices_summary(run_id, repo_root or releases_adapter.REPO_ROOT)
    except KeyError:
        return HTTPStatus.NOT_FOUND, error_payload('run_not_found', f'Unknown run_id: {run_id}')
    except reports_adapter.SliceProjectionError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, error_payload('slice_projection_failed', str(exc))


def get_run_cases(run_id: str, filters: dict[str, Any], repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, reports_adapter.list_cases_for_run(run_id, filters, repo_root or releases_adapter.REPO_ROOT)
    except KeyError:
        return HTTPStatus.NOT_FOUND, error_payload('run_not_found', f'Unknown run_id: {run_id}')
    except reports_adapter.CaseListProjectionError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, error_payload('case_list_projection_failed', str(exc))


def get_run_case_detail(run_id: str, case_id: str, repo_root: Path | None = None) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, reports_adapter.get_case_detail_for_run(run_id, case_id, repo_root or releases_adapter.REPO_ROOT)
    except KeyError:
        return HTTPStatus.NOT_FOUND, error_payload('run_not_found', f'Unknown run_id: {run_id}')
    except reports_adapter.RunNotReadyError:
        return HTTPStatus.CONFLICT, error_payload('run_not_ready', f'Run {run_id} is not ready for case detail projection')
    except reports_adapter.CaseNotFoundError:
        return HTTPStatus.NOT_FOUND, error_payload('case_not_found', f'Unknown case_id: {case_id}')
    except reports_adapter.CaseProjectionError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, error_payload('case_projection_failed', str(exc))
