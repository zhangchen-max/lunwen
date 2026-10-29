from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence


def _normalize_messages(messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    for message in messages:
        normalized.append(
            {
                "role": str(message.get("role", "")),
                "content": str(message.get("content", "")),
            }
        )
    return normalized


class ChatAdapter(ABC):
    """Adapter base with deterministic filesystem caching for reproducible runs."""

    def __init__(
        self,
        model_name: str,
        cache_root: str | Path | None = None,
        use_cache: bool = True,
    ) -> None:
        self.model_name = model_name
        self.cache_root = Path(cache_root) if cache_root is not None else Path("cache")
        self.use_cache = use_cache

    def complete(self, messages: Sequence[dict[str, str]], temperature: float = 0.0) -> str:
        payload = self._cache_payload(messages, temperature)
        cache_path = self._cache_path(payload["prompt_hash"])

        if self.use_cache:
            cached = self._read_cache(cache_path)
            if cached is not None:
                return cached

        response = self._complete_uncached(messages, temperature)
        if not isinstance(response, str):
            raise TypeError("_complete_uncached must return a string response")

        if self.use_cache:
            self._write_cache(cache_path, payload, response)

        return response

    def _cache_payload(self, messages: Sequence[dict[str, str]], temperature: float) -> dict[str, Any]:
        normalized = _normalize_messages(messages)
        serialized = json.dumps(
            {
                "model_name": self.model_name,
                "temperature": temperature,
                "messages": normalized,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        prompt_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return {
            "model_name": self.model_name,
            "temperature": temperature,
            "messages": normalized,
            "prompt_hash": prompt_hash,
        }

    def _cache_path(self, prompt_hash: str) -> Path:
        safe_model_name = self.model_name.replace("/", "__")
        return self.cache_root / safe_model_name / f"{prompt_hash}.json"

    def _read_cache(self, cache_path: Path) -> str | None:
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        response = payload.get("response")
        return response if isinstance(response, str) else None

    def _write_cache(self, cache_path: Path, payload: dict[str, Any], response: str) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(payload)
        record["response"] = response
        cache_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @abstractmethod
    def _complete_uncached(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float = 0.0,
    ) -> str:
        raise NotImplementedError
