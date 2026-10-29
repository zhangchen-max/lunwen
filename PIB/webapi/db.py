from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from webapi.models import ReleaseRegistryRow, RunRegistryRow

ARTIFACTS_DIR = Path('artifacts')
DB_PATH = ARTIFACTS_DIR / 'state.sqlite3'
JOBS_DIR = ARTIFACTS_DIR / 'jobs'


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def ensure_artifacts_layout(repo_root: Path) -> None:
    (repo_root / ARTIFACTS_DIR).mkdir(parents=True, exist_ok=True)
    (repo_root / JOBS_DIR).mkdir(parents=True, exist_ok=True)


def db_path(repo_root: Path) -> Path:
    return repo_root / DB_PATH


def job_dir(repo_root: Path, job_id: str) -> Path:
    return repo_root / JOBS_DIR / job_id


def connect(repo_root: Path) -> sqlite3.Connection:
    ensure_artifacts_layout(repo_root)
    conn = sqlite3.connect(db_path(repo_root))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(repo_root: Path) -> None:
    with connect(repo_root) as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS release_registry (
                release_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                status TEXT NOT NULL,
                manifest_path TEXT,
                bundle_path TEXT,
                benchmark_version TEXT,
                dataset_version TEXT,
                scoring_policy_version TEXT,
                dataset_hash_sha256 TEXT,
                scoring_hash_sha256 TEXT,
                cases_sha256 TEXT,
                rubrics_sha256 TEXT,
                splits_sha256 TEXT,
                last_validated_job_id TEXT NULL,
                last_frozen_job_id TEXT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                target_release_id TEXT NULL,
                started_at TEXT NULL,
                finished_at TEXT NULL,
                exit_code INTEGER NULL,
                stdout_path TEXT NULL,
                stderr_path TEXT NULL,
                result_json_path TEXT NULL,
                error_summary_json TEXT NULL
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS run_registry (
                run_id TEXT PRIMARY KEY,
                release_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                run_type TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                split_name TEXT NOT NULL,
                status TEXT NOT NULL,
                config_json TEXT NOT NULL,
                results_root TEXT NULL,
                metrics_path TEXT NULL,
                summary_path TEXT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT NULL,
                finished_at TEXT NULL,
                error_summary_json TEXT NULL
            )
            '''
        )
        conn.commit()


def upsert_release(repo_root: Path, release: dict[str, Any], *, last_validated_job_id: str | None = None, last_frozen_job_id: str | None = None) -> None:
    init_db(repo_root)
    now = utc_now_iso()
    existing = get_release(repo_root, release['release_id'])
    created_at = existing.created_at if existing else now
    with connect(repo_root) as conn:
        conn.execute(
            '''
            INSERT INTO release_registry (
                release_id, label, status, manifest_path, bundle_path,
                benchmark_version, dataset_version, scoring_policy_version,
                dataset_hash_sha256, scoring_hash_sha256, cases_sha256,
                rubrics_sha256, splits_sha256, last_validated_job_id,
                last_frozen_job_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(release_id) DO UPDATE SET
                label=excluded.label,
                status=excluded.status,
                manifest_path=excluded.manifest_path,
                bundle_path=excluded.bundle_path,
                benchmark_version=excluded.benchmark_version,
                dataset_version=excluded.dataset_version,
                scoring_policy_version=excluded.scoring_policy_version,
                dataset_hash_sha256=excluded.dataset_hash_sha256,
                scoring_hash_sha256=excluded.scoring_hash_sha256,
                cases_sha256=excluded.cases_sha256,
                rubrics_sha256=excluded.rubrics_sha256,
                splits_sha256=excluded.splits_sha256,
                last_validated_job_id=COALESCE(excluded.last_validated_job_id, release_registry.last_validated_job_id),
                last_frozen_job_id=COALESCE(excluded.last_frozen_job_id, release_registry.last_frozen_job_id),
                updated_at=excluded.updated_at
            ''',
            (
                release['release_id'],
                release['label'],
                release['status'],
                release.get('manifest_path'),
                release.get('bundle_path'),
                release.get('benchmark_version'),
                release.get('dataset_version'),
                release.get('scoring_policy_version'),
                release.get('dataset_hash_sha256'),
                release.get('scoring_hash_sha256'),
                release.get('cases_sha256'),
                release.get('rubrics_sha256'),
                release.get('splits_sha256'),
                last_validated_job_id,
                last_frozen_job_id,
                created_at,
                now,
            ),
        )
        conn.commit()


def get_release(repo_root: Path, release_id: str) -> ReleaseRegistryRow | None:
    init_db(repo_root)
    with connect(repo_root) as conn:
        row = conn.execute('SELECT * FROM release_registry WHERE release_id = ?', (release_id,)).fetchone()
    if row is None:
        return None
    return ReleaseRegistryRow(**dict(row))


def list_releases(repo_root: Path) -> list[ReleaseRegistryRow]:
    init_db(repo_root)
    with connect(repo_root) as conn:
        rows = conn.execute('SELECT * FROM release_registry ORDER BY updated_at DESC, release_id ASC').fetchall()
    return [ReleaseRegistryRow(**dict(row)) for row in rows]


def insert_job(repo_root: Path, job: dict[str, Any]) -> None:
    init_db(repo_root)
    with connect(repo_root) as conn:
        conn.execute(
            '''
            INSERT INTO jobs (
                job_id, job_type, status, target_release_id, started_at, finished_at,
                exit_code, stdout_path, stderr_path, result_json_path, error_summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                job['job_id'],
                job['job_type'],
                job['status'],
                job.get('target_release_id'),
                job.get('started_at'),
                job.get('finished_at'),
                job.get('exit_code'),
                job.get('stdout_path'),
                job.get('stderr_path'),
                job.get('result_json_path'),
                job.get('error_summary_json'),
            ),
        )
        conn.commit()


def update_job(repo_root: Path, job_id: str, **fields: Any) -> None:
    init_db(repo_root)
    if not fields:
        return
    assignments = ', '.join(f'{key} = ?' for key in fields.keys())
    values = list(fields.values()) + [job_id]
    with connect(repo_root) as conn:
        conn.execute(f'UPDATE jobs SET {assignments} WHERE job_id = ?', values)
        conn.commit()


def get_job(repo_root: Path, job_id: str) -> dict[str, Any] | None:
    init_db(repo_root)
    with connect(repo_root) as conn:
        row = conn.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,)).fetchone()
    return dict(row) if row else None


def insert_run(repo_root: Path, run: dict[str, Any]) -> None:
    init_db(repo_root)
    with connect(repo_root) as conn:
        conn.execute(
            '''
            INSERT INTO run_registry (
                run_id, release_id, job_id, run_type, provider, model_name,
                split_name, status, config_json, results_root, metrics_path,
                summary_path, created_at, started_at, finished_at, error_summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                run['run_id'],
                run['release_id'],
                run['job_id'],
                run['run_type'],
                run['provider'],
                run['model_name'],
                run['split_name'],
                run['status'],
                run['config_json'],
                run.get('results_root'),
                run.get('metrics_path'),
                run.get('summary_path'),
                run['created_at'],
                run.get('started_at'),
                run.get('finished_at'),
                run.get('error_summary_json'),
            ),
        )
        conn.commit()


def update_run(repo_root: Path, run_id: str, **fields: Any) -> None:
    init_db(repo_root)
    if not fields:
        return
    assignments = ', '.join(f'{key} = ?' for key in fields.keys())
    values = list(fields.values()) + [run_id]
    with connect(repo_root) as conn:
        conn.execute(f'UPDATE run_registry SET {assignments} WHERE run_id = ?', values)
        conn.commit()


def get_run(repo_root: Path, run_id: str) -> RunRegistryRow | None:
    init_db(repo_root)
    with connect(repo_root) as conn:
        row = conn.execute('SELECT * FROM run_registry WHERE run_id = ?', (run_id,)).fetchone()
    if row is None:
        return None
    return RunRegistryRow(**dict(row))
