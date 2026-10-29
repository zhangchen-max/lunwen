from __future__ import annotations

from pathlib import Path

from models.adapters.anthropic import AnthropicAdapter
from models.adapters.base import ChatAdapter
from models.adapters.local_llama import LocalLlamaAdapter
from models.adapters.openai_chat import OpenAIChatAdapter


def build_chat_adapter(
    provider: str,
    model: str | None = None,
    endpoint: str | None = None,
    cache_root: Path | None = None,
    use_cache: bool = True,
) -> ChatAdapter:
    if provider == "openai":
        return OpenAIChatAdapter(
            model=model or "gpt-4o-mini",
            base_url=endpoint,
            cache_root=cache_root,
            use_cache=use_cache,
        )

    if provider == "anthropic":
        return AnthropicAdapter(
            model=model or "claude-3-5-sonnet-latest",
            base_url=endpoint,
            cache_root=cache_root,
            use_cache=use_cache,
        )

    if provider == "local_llama":
        return LocalLlamaAdapter(
            endpoint=endpoint or "http://localhost:8000/v1/chat/completions",
            model=model or "local-llama",
            cache_root=cache_root,
            use_cache=use_cache,
        )

    raise ValueError(f"Unsupported provider: {provider}")
