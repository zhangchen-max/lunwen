from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from models.adapters.base import ChatAdapter
from models.adapters.http_utils import adapter_request_options, extract_anthropic_text, post_json


class AnthropicAdapter(ChatAdapter):
    def __init__(
        self,
        model: str = "claude-3-5-sonnet-latest",
        api_key: str | None = None,
        base_url: str | None = None,
        cache_root: str | Path | None = None,
        use_cache: bool = True,
    ):
        super().__init__(model_name=model, cache_root=cache_root, use_cache=use_cache)
        self.model = model
        self.api_key = api_key if api_key is not None else os.getenv("ANTHROPIC_API_KEY", "")
        resolved_base_url = base_url if base_url is not None else os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        self.endpoint = f"{resolved_base_url.rstrip('/')}/messages"

    def _complete_uncached(self, messages: Sequence[dict[str, str]], temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for AnthropicAdapter")

        system_parts: list[str] = []
        anthropic_messages: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "user"))
            content = str(message.get("content", ""))
            if role == "system":
                system_parts.append(content)
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            anthropic_messages.append({"role": role, "content": content})

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": 1024,
            "temperature": temperature,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        response = post_json(
            self.endpoint,
            payload=payload,
            headers=headers,
            **adapter_request_options("anthropic"),
        )
        return extract_anthropic_text(response)
