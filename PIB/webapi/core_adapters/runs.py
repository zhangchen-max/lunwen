from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from webapi.core_adapters import releases as releases_adapter
from webapi.models import error_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_TYPE_STATIC = 'static'
RUN_TYPE_DYNAMIC = 'dynamic'
PROVIDER_OPENAI = 'openai'
PROVIDER_ANTHROPIC = 'anthropic'
PROVIDER_LOCAL = 'local'
PROVIDER_BASELINE = 'baseline'
PROVIDER_GPT_OAUTH = 'gpt_oauth'
GPT_OAUTH_DEFAULT_MODEL = 'gpt-5.2'
ALLOWED_RUN_TYPES = {RUN_TYPE_STATIC, RUN_TYPE_DYNAMIC}
ALLOWED_PROVIDERS = {PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_LOCAL, PROVIDER_BASELINE, PROVIDER_GPT_OAUTH}
DEFAULT_SPLIT = 'test'


class RunAdapterError(Exception):
    code = 'invalid_request'

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ReleaseNotFoundError(RunAdapterError):
    code = 'release_not_found'


class InvalidRunTypeError(RunAdapterError):
    code = 'invalid_run_type'


def list_run_options(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    releases = releases_adapter.list_releases(repo_root=repo_root).get('items', [])
    return {
        'releases': [
            {'release_id': item['release_id'], 'label': item['label']}
            for item in releases
        ],
        'run_types': [RUN_TYPE_STATIC, RUN_TYPE_DYNAMIC],
        'providers': [
            {'id': PROVIDER_OPENAI, 'label': 'OpenAI'},
            {'id': PROVIDER_ANTHROPIC, 'label': 'Anthropic'},
            {'id': PROVIDER_LOCAL, 'label': 'Local'},
            {'id': PROVIDER_BASELINE, 'label': 'Baseline'},
            {'id': PROVIDER_GPT_OAUTH, 'label': 'GPT-5.2 (local OAuth dev)'},
        ],
        'default_split': DEFAULT_SPLIT,
    }


def normalize_create_run_request(payload: dict[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    release_id = str(payload.get('release_id') or '').strip()
    run_type = str(payload.get('run_type') or '').strip()
    provider = str(payload.get('provider') or '').strip()
    model_name = str(payload.get('model_name') or '').strip()
    split_name = str(payload.get('split_name') or DEFAULT_SPLIT).strip() or DEFAULT_SPLIT
    notes = str(payload.get('notes') or '').strip()

    if not release_id:
        raise RunAdapterError('release_id is required', {'field': 'release_id'})
    available_release_ids = {item['release_id'] for item in releases_adapter.list_releases(repo_root=repo_root).get('items', [])}
    if release_id not in available_release_ids:
        raise ReleaseNotFoundError(f'Unknown release_id: {release_id}', {'release_id': release_id})
    if run_type not in ALLOWED_RUN_TYPES:
        raise InvalidRunTypeError(f'Unsupported run_type: {run_type}', {'run_type': run_type})
    if provider not in ALLOWED_PROVIDERS:
        raise RunAdapterError(f'Unsupported provider: {provider}', {'field': 'provider', 'provider': provider})
    if provider == PROVIDER_GPT_OAUTH and not model_name:
        model_name = GPT_OAUTH_DEFAULT_MODEL
    if not model_name:
        raise RunAdapterError('model_name is required', {'field': 'model_name'})
    if split_name not in {'train', 'dev', 'test'}:
        raise RunAdapterError(f'Unsupported split_name: {split_name}', {'field': 'split_name', 'split_name': split_name})

    return {
        'release_id': release_id,
        'run_type': run_type,
        'provider': provider,
        'model_name': model_name,
        'split_name': split_name,
        'notes': notes,
    }


def _slug(value: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9._-]+', '-', value.strip())
    slug = slug.strip('-').lower()
    return slug or 'run'


def output_path_for_run(repo_root: Path, config: dict[str, Any], run_id: str) -> Path:
    model_slug = _slug(config['model_name'])
    return repo_root / 'results' / config['run_type'] / model_slug / f'{run_id}.jsonl'


def build_run_command(repo_root: Path, config: dict[str, Any], run_id: str) -> tuple[list[str], Path]:
    import sys

    output_path = output_path_for_run(repo_root, config, run_id)
    command: list[str]
    if config['run_type'] == RUN_TYPE_STATIC:
        command = [
            sys.executable,
            '-m',
            'eval.run_static',
            '--output',
            str(output_path.relative_to(repo_root)),
            '--split',
            config['split_name'],
        ]
        if config['provider'] == PROVIDER_BASELINE:
            command.extend(['--mode', 'heuristic'])
        else:
            provider = 'local_llama' if config['provider'] == PROVIDER_LOCAL else 'openai' if config['provider'] == PROVIDER_GPT_OAUTH else config['provider']
            command.extend(
                [
                    '--mode',
                    'llm',
                    '--provider',
                    provider,
                    '--model',
                    config['model_name'],
                ]
            )
    else:
        command = [
            sys.executable,
            '-m',
            'eval.run_dynamic',
            '--output',
            str(output_path.relative_to(repo_root)),
            '--split',
            config['split_name'],
        ]
        if config['provider'] == PROVIDER_BASELINE:
            command.extend(['--doctor', 'dummy'])
        else:
            provider = 'local_llama' if config['provider'] == PROVIDER_LOCAL else 'openai' if config['provider'] == PROVIDER_GPT_OAUTH else config['provider']
            command.extend(
                [
                    '--doctor',
                    'llm',
                    '--provider',
                    provider,
                    '--model',
                    config['model_name'],
                ]
            )
    return command, output_path


def build_run_env_overrides(config: dict[str, Any]) -> dict[str, str]:
    if config['provider'] != PROVIDER_GPT_OAUTH:
        return {}
    base_url = (os_environ().get('PIB_WEBAPI_BASE_URL') or 'http://127.0.0.1:8780').rstrip('/')
    return {
        'OPENAI_BASE_URL': f'{base_url}/v1',
        'OPENAI_API_KEY': 'gpt-oauth-local-dev',
    }


def os_environ() -> dict[str, str]:
    import os

    return dict(os.environ)


def infer_result_paths(repo_root: Path, output_path: Path) -> dict[str, str | None]:
    base_dir = output_path.with_suffix('')
    if not base_dir.exists():
        return {'results_root': None, 'metrics_path': None, 'summary_path': None}

    candidates = [path for path in sorted(base_dir.glob('run_*')) if path.is_dir()]
    if not candidates:
        return {'results_root': None, 'metrics_path': None, 'summary_path': None}

    artifact_dir = candidates[-1]
    metrics_path = artifact_dir / 'metrics.json'
    summary_path = artifact_dir / 'summary.csv'
    return {
        'results_root': str(artifact_dir.relative_to(repo_root)) + '/',
        'metrics_path': str(metrics_path.relative_to(repo_root)) if metrics_path.exists() else None,
        'summary_path': str(summary_path.relative_to(repo_root)) if summary_path.exists() else None,
    }


def serialize_config(config: dict[str, Any]) -> str:
    return json.dumps(config, ensure_ascii=False, sort_keys=True)


def parse_error_summary(stdout_path: str | None, stderr_path: str | None, exit_code: int | None) -> str | None:
    if exit_code in (None, 0):
        return None
    summary = {
        'message': f'subprocess exited with code {exit_code}',
        'stdout_path': stdout_path,
        'stderr_path': stderr_path,
    }
    return json.dumps(summary, ensure_ascii=False)
