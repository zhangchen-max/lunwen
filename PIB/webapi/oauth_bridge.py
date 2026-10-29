from __future__ import annotations

import json
import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

CODEX_EXECUTABLE = Path('/Applications/Codex.app/Contents/Resources/codex')
AUTH_PATH = Path.home() / '.codex' / 'auth.json'
DEFAULT_MODEL = 'gpt-5.2'


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw in {None, ''}:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw in {None, ''}:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class OAuthBridgeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _load_auth() -> dict[str, Any]:
    if not AUTH_PATH.exists():
        raise OAuthBridgeError('oauth_auth_missing', f'Missing local Codex auth file: {AUTH_PATH}')
    try:
        payload = json.loads(AUTH_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise OAuthBridgeError('oauth_auth_invalid', f'Invalid local Codex auth file: {exc}') from exc
    if payload.get('auth_mode') != 'chatgpt':
        raise OAuthBridgeError('oauth_auth_mode_invalid', 'Local Codex session is not using chatgpt OAuth')
    return payload


def list_models() -> dict[str, Any]:
    _load_auth()
    now = int(time.time())
    return {
        'object': 'list',
        'data': [
            {
                'id': DEFAULT_MODEL,
                'object': 'model',
                'created': now,
                'owned_by': 'local-codex-oauth',
            }
        ],
    }


def _messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    lines = [
        'You are serving as a local OpenAI-compatible relay for PIB development.',
        'Return only the assistant response text for the conversation below.',
        'Do not add commentary, metadata, markdown fences, or role labels.',
        'If the conversation requests strict JSON, output strict JSON only.',
        '',
        'Conversation:',
    ]
    for message in messages:
        role = str(message.get('role') or 'user').strip() or 'user'
        content = message.get('content')
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get('text')
                    if text:
                        parts.append(str(text))
                elif item:
                    parts.append(str(item))
            rendered = '\n'.join(parts).strip()
        else:
            rendered = str(content or '').strip()
        lines.append(f'[{role}]')
        lines.append(rendered)
        lines.append('')
    return '\n'.join(lines).strip()


def _run_codex(prompt: str, repo_root: Path, model: str) -> tuple[str, float]:
    if not CODEX_EXECUTABLE.exists():
        raise OAuthBridgeError('codex_exec_missing', f'Codex executable not found: {CODEX_EXECUTABLE}')
    timeout = _env_float('PIB_GPT_OAUTH_REQUEST_TIMEOUT', 90.0)
    max_retries = _env_int('PIB_GPT_OAUTH_MAX_RETRIES', 1)
    backoff_base = _env_float('PIB_GPT_OAUTH_BACKOFF_BASE', 1.0)

    with tempfile.NamedTemporaryFile('w+', encoding='utf-8', delete=False) as output_file:
        output_path = Path(output_file.name)
    try:
        last_error: OAuthBridgeError | None = None
        for attempt in range(max_retries + 1):
            command = [
                str(CODEX_EXECUTABLE),
                'exec',
                '-m',
                model,
                '--ephemeral',
                '--skip-git-repo-check',
                '-s',
                'read-only',
                '-C',
                str(repo_root),
                '-o',
                str(output_path),
                prompt,
            ]
            started = time.perf_counter()
            try:
                proc = subprocess.run(
                    command,
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as exc:
                last_error = OAuthBridgeError('timeout', f'Local GPT OAuth bridge timed out after {timeout:.1f}s')
            else:
                elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
                if proc.returncode != 0:
                    stderr = proc.stderr.strip() or proc.stdout.strip() or f'codex exec exited with code {proc.returncode}'
                    message = stderr.lower()
                    if 'unauthorized' in message or 'forbidden' in message or 'not entitled' in message:
                        last_error = OAuthBridgeError('provider_unavailable', stderr)
                    else:
                        last_error = OAuthBridgeError('adapter_error', stderr)
                else:
                    result = output_path.read_text(encoding='utf-8').strip()
                    if not result:
                        raise OAuthBridgeError('adapter_error', 'Local GPT OAuth bridge returned an empty response')
                    return result, elapsed_ms
            if attempt >= max_retries or last_error is None or last_error.code not in {'timeout', 'transport_error', 'provider_unavailable'}:
                break
            if backoff_base > 0:
                time.sleep(backoff_base * (2**attempt))
    finally:
        output_path.unlink(missing_ok=True)
    assert last_error is not None
    raise last_error


def chat_completion(payload: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    _load_auth()
    messages = payload.get('messages')
    if not isinstance(messages, list) or not messages:
        raise OAuthBridgeError('invalid_chat_payload', 'messages is required and must be a non-empty list')
    requested_model = str(payload.get('model') or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    prompt = _messages_to_prompt(messages)
    content, latency_ms = _run_codex(prompt, repo_root=repo_root, model=requested_model)
    now = int(time.time())
    return {
        'id': f'chatcmpl-{secrets.token_hex(8)}',
        'object': 'chat.completion',
        'created': now,
        'model': requested_model,
        'choices': [
            {
                'index': 0,
                'message': {
                    'role': 'assistant',
                    'content': content,
                },
                'finish_reason': 'stop',
            }
        ],
        'usage': {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
        },
        'pib_bridge': {
            'adapter_latency_ms': latency_ms,
        },
    }
