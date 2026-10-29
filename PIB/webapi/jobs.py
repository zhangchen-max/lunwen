from __future__ import annotations

import json
import re
import secrets
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from webapi import db
from webapi.core_adapters import releases as releases_adapter
from webapi.core_adapters import runs as runs_adapter
from webapi.models import (
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    JOB_TYPE_FREEZE_CURRENT,
    JOB_TYPE_RUN_DYNAMIC,
    JOB_TYPE_RUN_STATIC,
    JOB_TYPE_VALIDATE_CURRENT,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
)

_LOCK = threading.Lock()
_THREADS: dict[str, threading.Thread] = {}
CASE_RE = re.compile(r'PIB_\d{4,}')
FIELD_RE = re.compile(r'^(?P<field>[a-zA-Z0-9_.]+)\b')


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')


def generate_job_id() -> str:
    return f'job_{_utc_stamp()}_{secrets.token_hex(4)}'


def generate_run_id() -> str:
    return f'run_{_utc_stamp()}_{secrets.token_hex(4)}'


def _command_env(repo_root: Path, extra_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(**os_environ())
    pythonpath = env.get('PYTHONPATH')
    repo = str(repo_root)
    env['PYTHONPATH'] = repo if not pythonpath else f'{repo}:{pythonpath}'
    if extra_env:
        env.update(extra_env)
    return env


def os_environ() -> dict[str, str]:
    import os

    return dict(os.environ)


def _job_paths(repo_root: Path, job_id: str) -> dict[str, Path]:
    job_dir = db.job_dir(repo_root, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    return {
        'job_dir': job_dir,
        'stdout': job_dir / 'stdout.log',
        'stderr': job_dir / 'stderr.log',
        'result': job_dir / 'result.json',
    }


def _current_release_id(repo_root: Path) -> str | None:
    manifest = releases_adapter.read_manifest(repo_root)
    return releases_adapter.normalize_release_id(manifest.get('benchmark_version'))


def _validate_command() -> list[str]:
    return [
        sys.executable,
        '-m',
        'scripts.validate_all',
        '--cases',
        'data/cases.jsonl',
        '--rubrics',
        'data/rubrics.jsonl',
        '--ontology',
        'ontology',
        '--config',
        'pib_config.yaml',
    ]


def _freeze_commands() -> list[list[str]]:
    return [
        [sys.executable, '-m', 'scripts.freeze_release'],
        [sys.executable, '-m', 'scripts.freeze_release_reports'],
    ]


def _guess_field(message: str) -> str:
    if message.startswith('schema error:'):
        return 'schema'
    if message.startswith('rubrics missing case_id'):
        return 'case_id'
    match = FIELD_RE.match(message)
    if match:
        return match.group('field')
    return 'unknown'


def parse_validation_errors(stdout: str, stderr: str) -> list[dict[str, Any]]:
    text = '\n'.join(part for part in [stdout, stderr] if part).strip()
    if not text:
        return []
    errors: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in {'Validation failed', 'High-risk rubric coverage gaps detected:'}:
            continue
        if line.startswith('- '):
            case_id = CASE_RE.search(line)
            errors.append(
                {
                    'scope': 'validation',
                    'case_id': case_id.group(0) if case_id else None,
                    'field': 'must_ask_slots' if 'must_ask_slots' in line else 'unknown',
                    'message': line[2:],
                }
            )
            continue
        prefix_match = re.match(r'^\[(?P<prefix>[^\]]+)\]\s+(?P<message>.+)$', line)
        if prefix_match:
            prefix = prefix_match.group('prefix')
            message = prefix_match.group('message')
            case_id_match = CASE_RE.search(prefix)
            errors.append(
                {
                    'scope': 'validation',
                    'case_id': case_id_match.group(0) if case_id_match else None,
                    'field': _guess_field(message),
                    'message': message,
                }
            )
            continue
        errors.append(
            {
                'scope': 'validation',
                'case_id': CASE_RE.search(line).group(0) if CASE_RE.search(line) else None,
                'field': _guess_field(line),
                'message': line,
            }
        )
    return errors


def _tail(text: str, limit: int = 2000) -> str:
    return text[-limit:]


def _write_result(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _run_subprocess(command: list[str], repo_root: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=repo_root, capture_output=True, text=True, env=_command_env(repo_root, extra_env=extra_env))


def create_validate_current_job(repo_root: Path) -> dict[str, Any]:
    return _enqueue_job(repo_root, JOB_TYPE_VALIDATE_CURRENT)


def create_freeze_current_job(repo_root: Path) -> dict[str, Any]:
    return _enqueue_job(repo_root, JOB_TYPE_FREEZE_CURRENT)


def create_run_job(repo_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    db.init_db(repo_root)
    run_id = generate_run_id()
    job_type = JOB_TYPE_RUN_STATIC if config['run_type'] == runs_adapter.RUN_TYPE_STATIC else JOB_TYPE_RUN_DYNAMIC
    job_id = generate_job_id()
    paths = _job_paths(repo_root, job_id)
    created_at = db.utc_now_iso()
    db.insert_job(
        repo_root,
        {
            'job_id': job_id,
            'job_type': job_type,
            'status': JOB_STATUS_QUEUED,
            'target_release_id': config['release_id'],
            'started_at': None,
            'finished_at': None,
            'exit_code': None,
            'stdout_path': str(paths['stdout'].relative_to(repo_root)),
            'stderr_path': str(paths['stderr'].relative_to(repo_root)),
            'result_json_path': str(paths['result'].relative_to(repo_root)),
            'error_summary_json': None,
        },
    )
    db.insert_run(
        repo_root,
        {
            'run_id': run_id,
            'release_id': config['release_id'],
            'job_id': job_id,
            'run_type': config['run_type'],
            'provider': config['provider'],
            'model_name': config['model_name'],
            'split_name': config['split_name'],
            'status': RUN_STATUS_QUEUED,
            'config_json': runs_adapter.serialize_config(config),
            'results_root': None,
            'metrics_path': None,
            'summary_path': None,
            'created_at': created_at,
            'started_at': None,
            'finished_at': None,
            'error_summary_json': None,
        },
    )
    thread = threading.Thread(target=_run_run_job, args=(repo_root, run_id, job_id, config), daemon=True)
    with _LOCK:
        _THREADS[job_id] = thread
    thread.start()
    return {
        'run_id': run_id,
        'release_id': config['release_id'],
        'job_id': job_id,
        'run_type': config['run_type'],
        'provider': config['provider'],
        'model_name': config['model_name'],
        'split_name': config['split_name'],
        'status': RUN_STATUS_QUEUED,
        'created_at': created_at,
        'started_at': None,
        'finished_at': None,
        'results_root': None,
        'metrics_path': None,
        'summary_path': None,
        'error_summary': None,
    }


def _enqueue_job(repo_root: Path, job_type: str) -> dict[str, Any]:
    db.init_db(repo_root)
    job_id = generate_job_id()
    target_release_id = _current_release_id(repo_root)
    paths = _job_paths(repo_root, job_id)
    record = {
        'job_id': job_id,
        'job_type': job_type,
        'status': JOB_STATUS_QUEUED,
        'target_release_id': target_release_id,
        'started_at': None,
        'finished_at': None,
        'exit_code': None,
        'stdout_path': str(paths['stdout'].relative_to(repo_root)),
        'stderr_path': str(paths['stderr'].relative_to(repo_root)),
        'result_json_path': str(paths['result'].relative_to(repo_root)),
        'error_summary_json': None,
    }
    db.insert_job(repo_root, record)
    thread = threading.Thread(target=_run_job, args=(repo_root, job_id, job_type), daemon=True)
    with _LOCK:
        _THREADS[job_id] = thread
    thread.start()
    return get_job_status(repo_root, job_id)


def _run_job(repo_root: Path, job_id: str, job_type: str) -> None:
    paths = _job_paths(repo_root, job_id)
    db.update_job(repo_root, job_id, status=JOB_STATUS_RUNNING, started_at=db.utc_now_iso())
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    exit_code = 0
    structured_errors: list[dict[str, Any]] = []

    try:
        if job_type == JOB_TYPE_VALIDATE_CURRENT:
            proc = _run_subprocess(_validate_command(), repo_root)
            stdout_parts.append(proc.stdout)
            stderr_parts.append(proc.stderr)
            exit_code = proc.returncode
            structured_errors = parse_validation_errors(proc.stdout, proc.stderr) if proc.returncode != 0 else []
            if proc.returncode == 0:
                release = releases_adapter.sync_current_release_registry(repo_root, last_validated_job_id=job_id)
                target_release_id = release['release_id']
            else:
                target_release_id = _current_release_id(repo_root)
                if target_release_id:
                    releases_adapter.sync_current_release_registry(repo_root, last_validated_job_id=job_id)
        elif job_type == JOB_TYPE_FREEZE_CURRENT:
            target_release_id = _current_release_id(repo_root)
            for command in _freeze_commands():
                proc = _run_subprocess(command, repo_root)
                stdout_parts.append(proc.stdout)
                stderr_parts.append(proc.stderr)
                if proc.returncode != 0:
                    exit_code = proc.returncode
                    structured_errors = [
                        {
                            'scope': 'freeze',
                            'case_id': None,
                            'field': 'command',
                            'message': ' '.join(command[2:]) if len(command) > 2 else 'freeze command failed',
                        }
                    ]
                    break
            else:
                release = releases_adapter.sync_current_release_registry(repo_root, last_frozen_job_id=job_id)
                target_release_id = release['release_id']
        else:
            exit_code = 1
            target_release_id = _current_release_id(repo_root)
            structured_errors = [{'scope': 'job', 'case_id': None, 'field': 'job_type', 'message': f'Unsupported job_type {job_type}'}]

        status = JOB_STATUS_SUCCEEDED if exit_code == 0 else JOB_STATUS_FAILED
        stdout_text = ''.join(stdout_parts)
        stderr_text = ''.join(stderr_parts)
        paths['stdout'].write_text(stdout_text, encoding='utf-8')
        paths['stderr'].write_text(stderr_text, encoding='utf-8')
        result = {
            'job_id': job_id,
            'job_type': job_type,
            'status': status,
            'exit_code': exit_code,
            'structured_errors': structured_errors,
            'raw_summary': {
                'stdout_tail': _tail(stdout_text),
                'stderr_tail': _tail(stderr_text),
            },
        }
        if target_release_id:
            result['target_release_id'] = target_release_id
        _write_result(paths['result'], result)
        db.update_job(
            repo_root,
            job_id,
            status=status,
            target_release_id=target_release_id,
            finished_at=db.utc_now_iso(),
            exit_code=exit_code,
            error_summary_json=(json.dumps(structured_errors, ensure_ascii=False) if structured_errors else None),
        )
    finally:
        with _LOCK:
            _THREADS.pop(job_id, None)


def _run_run_job(repo_root: Path, run_id: str, job_id: str, config: dict[str, Any]) -> None:
    paths = _job_paths(repo_root, job_id)
    db.update_job(repo_root, job_id, status=JOB_STATUS_RUNNING, started_at=db.utc_now_iso())
    db.update_run(repo_root, run_id, status=RUN_STATUS_RUNNING, started_at=db.utc_now_iso())
    stdout_text = ''
    stderr_text = ''
    exit_code = 1
    result_paths = {'results_root': None, 'metrics_path': None, 'summary_path': None}
    try:
        command, output_path = runs_adapter.build_run_command(repo_root, config, run_id)
        extra_env = runs_adapter.build_run_env_overrides(config)
        proc = _run_subprocess(command, repo_root, extra_env=extra_env)
        stdout_text = proc.stdout
        stderr_text = proc.stderr
        exit_code = proc.returncode
        result_paths = runs_adapter.infer_result_paths(repo_root, output_path)
    except Exception as exc:  # pragma: no cover - defensive
        stderr_text = f'{stderr_text}\n{exc}'.strip()
    finally:
        paths['stdout'].write_text(stdout_text, encoding='utf-8')
        paths['stderr'].write_text(stderr_text, encoding='utf-8')
        run_status = RUN_STATUS_COMPLETED if exit_code == 0 else RUN_STATUS_FAILED
        job_status = JOB_STATUS_SUCCEEDED if exit_code == 0 else JOB_STATUS_FAILED
        error_summary_json = runs_adapter.parse_error_summary(
            str(paths['stdout'].relative_to(repo_root)),
            str(paths['stderr'].relative_to(repo_root)),
            exit_code,
        )
        result_payload = {
            'job_id': job_id,
            'run_id': run_id,
            'job_type': JOB_TYPE_RUN_STATIC if config['run_type'] == runs_adapter.RUN_TYPE_STATIC else JOB_TYPE_RUN_DYNAMIC,
            'status': job_status,
            'exit_code': exit_code,
            'structured_errors': [],
            'raw_summary': {
                'stdout_tail': _tail(stdout_text),
                'stderr_tail': _tail(stderr_text),
            },
            'target_release_id': config['release_id'],
            'run': {
                'run_id': run_id,
                'status': run_status,
                **result_paths,
            },
        }
        _write_result(paths['result'], result_payload)
        db.update_job(
            repo_root,
            job_id,
            status=job_status,
            target_release_id=config['release_id'],
            finished_at=db.utc_now_iso(),
            exit_code=exit_code,
            error_summary_json=error_summary_json,
        )
        db.update_run(
            repo_root,
            run_id,
            status=run_status,
            finished_at=db.utc_now_iso(),
            results_root=result_paths['results_root'],
            metrics_path=result_paths['metrics_path'],
            summary_path=result_paths['summary_path'],
            error_summary_json=error_summary_json,
        )
        with _LOCK:
            _THREADS.pop(job_id, None)


def get_job_status(repo_root: Path, job_id: str) -> dict[str, Any]:
    row = db.get_job(repo_root, job_id)
    if row is None:
        raise KeyError(job_id)
    result = None
    if row.get('result_json_path'):
        result_path = repo_root / row['result_json_path']
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding='utf-8'))
    payload = dict(row)
    payload['job_dir'] = str(db.job_dir(repo_root, job_id).relative_to(repo_root))
    payload['result'] = result
    payload['structured_errors'] = result.get('structured_errors', []) if result else []
    return payload


def get_run_status(repo_root: Path, run_id: str) -> dict[str, Any]:
    row = db.get_run(repo_root, run_id)
    if row is None:
        raise KeyError(run_id)
    payload = {
        'run_id': row.run_id,
        'release_id': row.release_id,
        'job_id': row.job_id,
        'run_type': row.run_type,
        'provider': row.provider,
        'model_name': row.model_name,
        'split_name': row.split_name,
        'status': row.status,
        'created_at': row.created_at,
        'started_at': row.started_at,
        'finished_at': row.finished_at,
        'results_root': row.results_root,
        'metrics_path': row.metrics_path,
        'summary_path': row.summary_path,
        'error_summary': json.loads(row.error_summary_json) if row.error_summary_json else None,
    }
    return payload
