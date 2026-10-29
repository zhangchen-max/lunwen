from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable


class JsonParseError(ValueError):
    """Raised when model output cannot be parsed into JSON object."""


EMPTY_OUTPUT = "empty_output"
PARSE_ERROR = "parse_error"
SCHEMA_ERROR = "schema_error"
RAW_SNIPPET_LIMIT = 400


@dataclass
class ParseDiagnostics:
    ok: bool
    error_code: str | None
    extracted_json_text: str | None
    retry_count: int
    raw_response_snippet: str | None
    error_message: str | None
    attempts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_code": self.error_code,
            "extracted_json_text": self.extracted_json_text,
            "retry_count": self.retry_count,
            "raw_response_snippet": self.raw_response_snippet,
            "error_message": self.error_message,
            "attempts": self.attempts,
        }


@dataclass
class ParseAttemptResult:
    value: dict[str, Any] | None
    diagnostics: ParseDiagnostics


def _snippet(raw_text: str | None) -> str | None:
    if raw_text is None:
        return None
    return raw_text.strip()[:RAW_SNIPPET_LIMIT] or None


def _extract_json_from_fence(text: str) -> str | None:
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_balanced_object(text: str) -> str | None:
    start = None
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                return text[start : i + 1]
    return None


def extract_json_text(raw_text: str) -> str:
    candidates = []
    stripped = raw_text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)

    fenced = _extract_json_from_fence(raw_text)
    if fenced:
        candidates.append(fenced)

    balanced = _extract_balanced_object(raw_text)
    if balanced:
        candidates.append(balanced)

    for candidate in candidates:
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue

    raise JsonParseError("No valid JSON object found in model output")


def parse_json_output_with_diagnostics(raw_text: str) -> ParseAttemptResult:
    stripped = raw_text.strip()
    if not stripped:
        diagnostics = ParseDiagnostics(
            ok=False,
            error_code=EMPTY_OUTPUT,
            extracted_json_text=None,
            retry_count=0,
            raw_response_snippet=None,
            error_message="Model output was empty",
            attempts=[],
        )
        return ParseAttemptResult(value=None, diagnostics=diagnostics)

    candidates = []
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)

    fenced = _extract_json_from_fence(raw_text)
    if fenced and fenced not in candidates:
        candidates.append(fenced)

    balanced = _extract_balanced_object(raw_text)
    if balanced and balanced not in candidates:
        candidates.append(balanced)

    extracted_json_text: str | None = candidates[-1] if candidates else None
    last_decode_error: str | None = None

    for candidate in candidates:
        extracted_json_text = candidate
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_decode_error = str(exc)
            continue

        if not isinstance(obj, dict):
            diagnostics = ParseDiagnostics(
                ok=False,
                error_code=SCHEMA_ERROR,
                extracted_json_text=candidate,
                retry_count=0,
                raw_response_snippet=_snippet(raw_text),
                error_message="JSON root must be an object",
                attempts=[],
            )
            return ParseAttemptResult(value=None, diagnostics=diagnostics)

        diagnostics = ParseDiagnostics(
            ok=True,
            error_code=None,
            extracted_json_text=candidate,
            retry_count=0,
            raw_response_snippet=_snippet(raw_text),
            error_message=None,
            attempts=[],
        )
        return ParseAttemptResult(value=obj, diagnostics=diagnostics)

    diagnostics = ParseDiagnostics(
        ok=False,
        error_code=PARSE_ERROR,
        extracted_json_text=extracted_json_text,
        retry_count=0,
        raw_response_snippet=_snippet(raw_text),
        error_message=last_decode_error or "No valid JSON object found in model output",
        attempts=[],
    )
    return ParseAttemptResult(value=None, diagnostics=diagnostics)


def parse_json_output(raw_text: str) -> dict[str, Any]:
    result = parse_json_output_with_diagnostics(raw_text)
    if result.value is not None:
        return result.value
    raise JsonParseError(
        result.diagnostics.error_message
        or f"Failed to parse model output ({result.diagnostics.error_code})"
    )


def parse_with_retry(
    call_model: Callable[[str], str],
    prompt: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Call model with retry; enforce raw JSON-only output on retries."""
    result = parse_with_retry_diagnostics(call_model, prompt, max_retries=max_retries)
    if result.value is not None:
        return result.value
    diagnostics = result.diagnostics
    raise JsonParseError(
        f"Exceeded retry limit ({max_retries}). Last error: "
        f"{diagnostics.error_code or 'unknown'}: {diagnostics.error_message or 'parse failed'}"
    )


def parse_with_retry_diagnostics(
    call_model: Callable[[str], str],
    prompt: str,
    max_retries: int = 2,
) -> ParseAttemptResult:
    """Call model with retry and return machine-readable parse diagnostics."""
    retry_suffix = "\n\n请只输出一个 JSON 对象，不要包含任何额外文本。"
    attempts: list[dict[str, Any]] = []

    for attempt in range(max_retries + 1):
        effective_prompt = prompt if attempt == 0 else prompt + retry_suffix
        raw = call_model(effective_prompt)
        parsed = parse_json_output_with_diagnostics(raw)
        attempt_diag = {
            "attempt": attempt,
            "error_code": parsed.diagnostics.error_code,
            "extracted_json_text": parsed.diagnostics.extracted_json_text,
            "raw_response_snippet": parsed.diagnostics.raw_response_snippet,
            "error_message": parsed.diagnostics.error_message,
        }
        attempts.append(attempt_diag)
        if parsed.value is not None:
            diagnostics = parsed.diagnostics
            diagnostics.retry_count = attempt
            diagnostics.attempts = attempts
            return ParseAttemptResult(value=parsed.value, diagnostics=diagnostics)

    latest = attempts[-1] if attempts else {
        "error_code": PARSE_ERROR,
        "extracted_json_text": None,
        "raw_response_snippet": None,
        "error_message": "Failed to parse model output",
    }
    diagnostics = ParseDiagnostics(
        ok=False,
        error_code=str(latest.get("error_code") or PARSE_ERROR),
        extracted_json_text=latest.get("extracted_json_text"),
        retry_count=max_retries,
        raw_response_snippet=latest.get("raw_response_snippet"),
        error_message=latest.get("error_message"),
        attempts=attempts,
    )
    return ParseAttemptResult(value=None, diagnostics=diagnostics)
