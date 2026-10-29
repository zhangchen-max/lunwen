from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from models.adapters.anthropic import AnthropicAdapter
from models.adapters.openai_chat import OpenAIChatAdapter


class AdapterTests(unittest.TestCase):
    def test_openai_adapter_formats_payload_and_uses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            adapter = OpenAIChatAdapter(
                model="mock-openai",
                api_key="test-key",
                base_url="https://example.test/v1",
                cache_root=Path(td),
                use_cache=True,
            )
            messages = [{"role": "user", "content": "hello"}]

            with mock.patch(
                "models.adapters.openai_chat.post_json",
                return_value={
                    "choices": [
                        {"message": {"content": '{"action":"ASK","slot_id":"onset_time"}'}}
                    ]
                },
            ) as post_json:
                first = adapter.complete(messages, temperature=0.0)
                second = adapter.complete(messages, temperature=0.0)

        self.assertEqual(first, '{"action":"ASK","slot_id":"onset_time"}')
        self.assertEqual(second, first)
        self.assertEqual(post_json.call_count, 1)
        args, kwargs = post_json.call_args
        self.assertEqual(args[0], "https://example.test/v1/chat/completions")
        self.assertEqual(kwargs["payload"]["model"], "mock-openai")
        self.assertEqual(kwargs["payload"]["messages"], messages)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_anthropic_adapter_sends_system_field(self) -> None:
        adapter = AnthropicAdapter(
            model="mock-claude",
            api_key="test-key",
            base_url="https://example.test/v1",
            use_cache=False,
        )

        with mock.patch(
            "models.adapters.anthropic.post_json",
            return_value={
                "content": [
                    {
                        "type": "text",
                        "text": '{"action":"ASK","slot_id":"duration"}',
                    }
                ]
            },
        ) as post_json:
            response = adapter.complete(
                [
                    {"role": "system", "content": "只输出 JSON"},
                    {"role": "user", "content": "请继续"},
                ],
                temperature=0.0,
            )

        self.assertEqual(response, '{"action":"ASK","slot_id":"duration"}')
        self.assertEqual(post_json.call_count, 1)
        args, kwargs = post_json.call_args
        self.assertEqual(args[0], "https://example.test/v1/messages")
        self.assertEqual(kwargs["payload"]["model"], "mock-claude")
        self.assertEqual(kwargs["payload"]["system"], "只输出 JSON")
        self.assertEqual(
            kwargs["payload"]["messages"],
            [{"role": "user", "content": "请继续"}],
        )
        self.assertEqual(kwargs["headers"]["x-api-key"], "test-key")
