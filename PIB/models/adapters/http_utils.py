from __future__ import annotations

import json
import os
import socket
import time
from typing import Any
from urllib import error, request


class AdapterHttpError(RuntimeError):
    """Raised when an HTTP adapter request fails or returns an unexpected payload."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _is_timeout_reason(reason: Any) -> bool:
    if isinstance(reason, TimeoutError | socket.timeout):
        return True
    text = str(reason or "").lower()
    return "timed out" in text or "timeout" in text


def _should_retry(code: str) -> bool:
    return code in {"timeout", "transport_error", "provider_unavailable"}


def _env_float(name: str, default: float | None) -> float | None:
    raw = os.getenv(name)
    if raw in {None, ""}:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw in {None, ""}:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def adapter_request_options(prefix: str) -> dict[str, Any]:
    upper = prefix.upper()
    return {
        "timeout": _env_float(f"PIB_{upper}_REQUEST_TIMEOUT", _env_float("PIB_ADAPTER_REQUEST_TIMEOUT", 60.0)) or 60.0,
        "connect_timeout": _env_float(
            f"PIB_{upper}_CONNECT_TIMEOUT",
            _env_float("PIB_ADAPTER_CONNECT_TIMEOUT", None),
        ),
        "max_retries": _env_int(f"PIB_{upper}_MAX_RETRIES", _env_int("PIB_ADAPTER_MAX_RETRIES", 0)),
        "backoff_base": _env_float(f"PIB_{upper}_BACKOFF_BASE", _env_float("PIB_ADAPTER_BACKOFF_BASE", 0.5)) or 0.5,
    }


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float = 60.0,
    connect_timeout: float | None = None,
    max_retries: int = 0,
    backoff_base: float = 0.5,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    effective_timeout = max(timeout, connect_timeout or 0.0)
    last_error: AdapterHttpError | None = None

    for attempt in range(max_retries + 1):
        req = request.Request(url=url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=effective_timeout) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            code = "provider_unavailable" if exc.code in {408, 429, 500, 502, 503, 504} else "adapter_error"
            last_error = AdapterHttpError(code, f"HTTP {exc.code} from {url}: {detail}")
        except error.URLError as exc:
            code = "timeout" if _is_timeout_reason(exc.reason) else "transport_error"
            last_error = AdapterHttpError(code, f"Failed to reach {url}: {exc.reason}")
        except (TimeoutError, socket.timeout) as exc:
            last_error = AdapterHttpError("timeout", f"Request to {url} timed out: {exc}")
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise AdapterHttpError("adapter_error", f"Invalid JSON response from {url}: {raw[:200]}") from exc

            if not isinstance(data, dict):
                raise AdapterHttpError("adapter_error", f"JSON response root from {url} must be an object")
            return data

        if last_error is None or attempt >= max_retries or not _should_retry(last_error.code):
            break
        if backoff_base > 0:
            time.sleep(backoff_base * (2**attempt))

    assert last_error is not None
    raise last_error


def extract_openai_chat_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AdapterHttpError("adapter_error", "OpenAI-compatible response missing choices")

    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise AdapterHttpError("adapter_error", "OpenAI-compatible response missing choices[0].message")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                texts.append(item["text"])
        if texts:
            return "\n".join(texts)

    raise AdapterHttpError("adapter_error", "OpenAI-compatible response missing textual message content")


def extract_anthropic_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        raise AdapterHttpError("adapter_error", "Anthropic response missing content blocks")

    texts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            texts.append(item["text"])

    if not texts:
        raise AdapterHttpError("adapter_error", "Anthropic response missing textual content")
    return "\n".join(texts)
