from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from models.adapters.base import ChatAdapter
from models.adapters.http_utils import adapter_request_options, extract_openai_chat_text, post_json


class OpenAIChatAdapter(ChatAdapter):
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        cache_root: str | Path | None = None,
        use_cache: bool = True,
    ):
        super().__init__(model_name=model, cache_root=cache_root, use_cache=use_cache)
        self.model = model
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        resolved_base_url = base_url if base_url is not None else os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.endpoint = f"{resolved_base_url.rstrip('/')}/chat/completions"

    def _complete_uncached(self, messages: Sequence[dict[str, str]], temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIChatAdapter")

        payload = {
            "model": self.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        # 支持通过环境变量注入额外参数（如 Qwen3 的 enable_thinking）
        import json as _json
        _extra = os.getenv("OPENAI_EXTRA_BODY")
        if _extra:
            payload.update(_json.loads(_extra))
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = post_json(
            self.endpoint,
            payload=payload,
            headers=headers,
            **adapter_request_options("openai"),
        )
        return extract_openai_chat_text(response)
