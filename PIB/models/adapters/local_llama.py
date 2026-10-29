from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from models.adapters.base import ChatAdapter
from models.adapters.http_utils import adapter_request_options, extract_openai_chat_text, post_json


class LocalLlamaAdapter(ChatAdapter):
    def __init__(
        self,
        endpoint: str = "http://localhost:8000/v1/chat/completions",
        model: str = "local-llama",
        cache_root: str | Path | None = None,
        use_cache: bool = True,
    ):
        super().__init__(model_name=model, cache_root=cache_root, use_cache=use_cache)
        self.endpoint = endpoint

    def _complete_uncached(self, messages: Sequence[dict[str, str]], temperature: float = 0.0) -> str:
        payload = {
            "model": self.model_name,
            "messages": list(messages),
            "temperature": temperature,
        }
        api_key = os.environ.get("LLM_API_KEY", "dummy")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        response = post_json(
            self.endpoint,
            payload=payload,
            headers=headers,
            **adapter_request_options("local"),
        )
        return extract_openai_chat_text(response)
