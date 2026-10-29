from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote

from webapi import db

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = [Path('results'), Path('artifacts/jobs')]


class ArtifactIndexError(Exception):
    code = 'artifact_index_failed'

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ArtifactNotFoundError(Exception):
    code = 'artifact_not_found'

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ArtifactPathNotAllowedError(Exception):
    code = 'artifact_path_not_allowed'

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _item(kind: str, label: str, path: Path, repo_root: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        'kind': kind,
        'label': label,
        'path': str(path.relative_to(repo_root)),
        'size_bytes': path.stat().st_size if exists else 0,
        'exists': exists,
    }


def list_run_artifacts(run_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    run_row = db.get_run(repo_root, run_id)
    if run_row is None:
        raise KeyError(run_id)

    items: list[dict[str, Any]] = []
    if run_row.results_root:
        root = repo_root / run_row.results_root
        if root.exists():
            known = [
                ('metrics', 'metrics.json', root / 'metrics.json'),
                ('summary', 'summary.csv', root / 'summary.csv'),
                ('predictions', 'predictions.jsonl', root / 'predictions.jsonl'),
            ]
            for kind, label, path in known:
                if path.exists():
                    items.append(_item(kind, label, path, repo_root))

    job = db.get_job(repo_root, run_row.job_id)
    if job:
        for kind, label, key in [('log', 'stdout.log', 'stdout_path'), ('log', 'stderr.log', 'stderr_path')]:
            if job.get(key):
                path = repo_root / job[key]
                if path.exists():
                    items.append(_item(kind, label, path, repo_root))

    return {
        'run_id': run_id,
        'results_root': run_row.results_root,
        'items': items,
    }


def resolve_download_path(relative_path: str, repo_root: Path | None = None) -> Path:
    repo_root = repo_root or REPO_ROOT
    decoded = unquote(relative_path or '').strip()
    if not decoded:
        raise ArtifactPathNotAllowedError('artifact path is required')
    requested = Path(decoded)
    if requested.is_absolute() or '..' in requested.parts:
        raise ArtifactPathNotAllowedError('artifact path escapes allowed roots')

    resolved = (repo_root / requested).resolve()
    allowed = [(repo_root / root).resolve() for root in ALLOWED_ROOTS]
    if not any(resolved == root or root in resolved.parents for root in allowed):
        raise ArtifactPathNotAllowedError('artifact path is outside allowed roots')
    if not resolved.exists() or not resolved.is_file():
        raise ArtifactNotFoundError(f'Artifact not found: {decoded}')
    return resolved
