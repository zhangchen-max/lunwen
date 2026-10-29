from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load module {module_name} from {relative_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


oauth_bridge = load_module('pib_webapi_oauth_bridge', 'webapi/oauth_bridge.py')


class OAuthBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.auth_path = Path(self.tempdir.name) / 'auth.json'
        self.auth_path.write_text(json.dumps({'auth_mode': 'chatgpt'}), encoding='utf-8')
        self.repo_root = Path(self.tempdir.name)
        self.codex_path = Path(self.tempdir.name) / 'codex'
        self.codex_path.write_text('#!/bin/sh\n', encoding='utf-8')

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_list_models_returns_gpt_5_2(self) -> None:
        with mock.patch.object(oauth_bridge, 'AUTH_PATH', self.auth_path):
            payload = oauth_bridge.list_models()
        self.assertEqual(payload['data'][0]['id'], 'gpt-5.2')

    def test_chat_completion_returns_openai_compatible_payload(self) -> None:
        def fake_run(command, cwd, capture_output, text, **kwargs):
            output_path = Path(command[command.index('-o') + 1])
            output_path.write_text('{"action":"ASK","slot_id":"onset_time"}\n', encoding='utf-8')
            return mock.Mock(returncode=0, stdout='ok', stderr='')

        with mock.patch.object(oauth_bridge, 'AUTH_PATH', self.auth_path):
            with mock.patch.object(oauth_bridge, 'CODEX_EXECUTABLE', self.codex_path):
                with mock.patch('subprocess.run', side_effect=fake_run):
                    payload = oauth_bridge.chat_completion(
                        {
                            'model': 'gpt-5.2',
                            'messages': [
                                {'role': 'system', 'content': 'Return JSON only.'},
                                {'role': 'user', 'content': 'Ask for onset.'},
                            ],
                        },
                        repo_root=self.repo_root,
                    )
        self.assertEqual(payload['object'], 'chat.completion')
        self.assertEqual(payload['model'], 'gpt-5.2')
        self.assertEqual(payload['choices'][0]['message']['content'], '{"action":"ASK","slot_id":"onset_time"}')

    def test_chat_completion_surfaces_unavailable_error(self) -> None:
        def fake_run(command, cwd, capture_output, text, **kwargs):
            return mock.Mock(returncode=1, stdout='', stderr='model unavailable')

        with mock.patch.object(oauth_bridge, 'AUTH_PATH', self.auth_path):
            with mock.patch.object(oauth_bridge, 'CODEX_EXECUTABLE', self.codex_path):
                with mock.patch('subprocess.run', side_effect=fake_run):
                    with self.assertRaises(oauth_bridge.OAuthBridgeError) as ctx:
                        oauth_bridge.chat_completion(
                            {'model': 'gpt-5.2', 'messages': [{'role': 'user', 'content': 'Hello'}]},
                            repo_root=self.repo_root,
                        )
        self.assertEqual(ctx.exception.code, 'adapter_error')
