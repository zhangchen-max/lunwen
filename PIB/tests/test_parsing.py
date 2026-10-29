from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models.adapters.base import ChatAdapter
from models.parsing import (
    EMPTY_OUTPUT,
    PARSE_ERROR,
    parse_json_output,
    parse_json_output_with_diagnostics,
    parse_with_retry,
    parse_with_retry_diagnostics,
)


class _CountingAdapter(ChatAdapter):
    def __init__(self, cache_root: Path) -> None:
        super().__init__(model_name="counting-adapter", cache_root=cache_root, use_cache=True)
        self.calls = 0

    def _complete_uncached(self, messages, temperature: float = 0.0) -> str:
        self.calls += 1
        return '{"action":"ASK","slot_id":"onset_time"}'


class ParsingTests(unittest.TestCase):
    def test_parse_json_output_accepts_wrapped_json(self) -> None:
        raw = 'prefix\\n```json\\n{\"action\":\"ASK\",\"slot_id\":\"onset_time\"}\\n```\\nsuffix'
        parsed = parse_json_output(raw)
        self.assertEqual(parsed["action"], "ASK")
        self.assertEqual(parsed["slot_id"], "onset_time")

    def test_json_extraction_mixed_text(self) -> None:
        raw = 'analysis... {"action":"FINAL"} trailing text'
        attempt = parse_json_output_with_diagnostics(raw)
        self.assertIsNotNone(attempt.value)
        self.assertTrue(attempt.diagnostics.ok)
        self.assertEqual(attempt.diagnostics.error_code, None)
        self.assertEqual(attempt.diagnostics.extracted_json_text, '{"action":"FINAL"}')
        self.assertEqual(attempt.value["action"], "FINAL")

    def test_parse_with_retry_recovers_on_second_attempt(self) -> None:
        outputs = iter(
            [
                "not-json",
                '{"action":"ASK","slot_id":"duration"}',
            ]
        )

        parsed = parse_with_retry(lambda _: next(outputs), "prompt", max_retries=2)
        self.assertEqual(parsed["action"], "ASK")
        self.assertEqual(parsed["slot_id"], "duration")

    def test_parse_retry_success_on_second_attempt_with_diagnostics(self) -> None:
        outputs = iter(
            [
                "",
                '{"action":"ASK","slot_id":"duration"}',
            ]
        )
        result = parse_with_retry_diagnostics(lambda _: next(outputs), "prompt", max_retries=2)
        self.assertIsNotNone(result.value)
        self.assertTrue(result.diagnostics.ok)
        self.assertEqual(result.diagnostics.retry_count, 1)
        self.assertEqual(result.diagnostics.error_code, None)
        self.assertEqual(result.value["slot_id"], "duration")

    def test_parse_with_retry_diagnostics_reports_empty_output(self) -> None:
        result = parse_with_retry_diagnostics(lambda _: "", "prompt", max_retries=0)
        self.assertIsNone(result.value)
        self.assertFalse(result.diagnostics.ok)
        self.assertEqual(result.diagnostics.error_code, EMPTY_OUTPUT)

    def test_parse_with_retry_diagnostics_reports_parse_error(self) -> None:
        result = parse_with_retry_diagnostics(lambda _: "not-json", "prompt", max_retries=0)
        self.assertIsNone(result.value)
        self.assertFalse(result.diagnostics.ok)
        self.assertEqual(result.diagnostics.error_code, PARSE_ERROR)

    def test_adapter_cache_reuses_cached_response(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            adapter = _CountingAdapter(cache_root=Path(td))
            messages = [{"role": "user", "content": "hello"}]

            first = adapter.complete(messages, temperature=0.0)
            second = adapter.complete(messages, temperature=0.0)

            self.assertEqual(first, second)
            self.assertEqual(adapter.calls, 1)
            cache_files = list((Path(td) / "counting-adapter").glob("*.json"))
            self.assertEqual(len(cache_files), 1)
