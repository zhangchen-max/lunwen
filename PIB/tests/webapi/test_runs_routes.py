from __future__ import annotations

import importlib.util
import json
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load module {module_name} from {relative_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runs_routes = load_module('pib_webapi_routes_runs', 'webapi/routes/runs.py')
jobs_module = load_module('pib_webapi_jobs_runs', 'webapi/jobs.py')
db_module = load_module('pib_webapi_db_runs', 'webapi/db.py')


class RunsRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / 'release').mkdir(parents=True)
        (self.repo_root / 'results' / 'reports').mkdir(parents=True)
        (self.repo_root / 'results' / 'audit').mkdir(parents=True)
        (self.repo_root / 'eval').mkdir(parents=True)
        (self.repo_root / 'eval' / '__init__.py').write_text('', encoding='utf-8')
        manifest = {
            'benchmark_version': '1.1.0-rc1',
            'dataset_version': '1.1.0-rc1',
            'scoring_policy_version': '1.1.0-rc1',
            'no_oracle_policy_version': '1.1.0-rc1',
            'hard_constraints': {
                'slot_count': 120,
                'dynamic_max_turns_cap': 15,
                'os_ocrd_subtypes': ['OS_OCRD_BFRB', 'OS_OCRD_JEAL', 'OS_OCRD_OTHER'],
            },
            'dataset_hash_sha256': 'dataset-hash',
            'scoring_hash_sha256': 'scoring-hash',
            'cases_sha256': 'cases-hash',
            'rubrics_sha256': 'rubrics-hash',
            'splits_sha256': 'splits-hash',
        }
        (self.repo_root / 'release' / 'benchmark_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        bundle = self.repo_root / 'release' / 'PIB-Benchmark-v1.1.0-rc1'
        bundle.mkdir(parents=True)
        (bundle / 'benchmark_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        (self.repo_root / 'results' / 'reports' / 'pure_baselines.csv').write_text('a,b\n1,2\n', encoding='utf-8')
        (self.repo_root / 'results' / 'reports' / 'guided_llm_baselines.csv').write_text('a,b\n1,2\n', encoding='utf-8')
        (self.repo_root / 'results' / 'reports' / 'deprecated_results.json').write_text('{}', encoding='utf-8')
        (self.repo_root / 'results' / 'audit' / 'no_oracle_baselines.json').write_text('{}', encoding='utf-8')
        (self.repo_root / 'results' / 'audit' / 'text_contamination_scan.json').write_text('{}', encoding='utf-8')

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_eval_module(self, module_name: str, body: str) -> None:
        path = self.repo_root / 'eval' / f'{module_name}.py'
        path.write_text(textwrap.dedent(body), encoding='utf-8')

    def _wait_for_run(self, run_id: str, timeout_sec: float = 5.0) -> dict:
        deadline = time.time() + timeout_sec
        last_payload = None
        while time.time() < deadline:
            status, payload = runs_routes.get_run(run_id, repo_root=self.repo_root)
            self.assertEqual(status, 200)
            last_payload = payload
            if payload['status'] in {'completed', 'failed'}:
                return payload
            time.sleep(0.05)
        self.fail(f'Run {run_id} did not reach terminal state: {last_payload}')

    def test_post_run_creates_run_and_job(self) -> None:
        self._write_eval_module(
            'run_static',
            '''
            import argparse
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument('--output', required=True)
            parser.add_argument('--split')
            parser.add_argument('--mode')
            parser.add_argument('--provider', default=None)
            parser.add_argument('--model', default=None)
            args = parser.parse_args()
            import time
            time.sleep(0.1)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{}\\n', encoding='utf-8')
            artifact_dir = output.with_suffix('') / 'run_001'
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / 'metrics.json').write_text('{}\\n', encoding='utf-8')
            (artifact_dir / 'summary.csv').write_text('a,b\\n1,2\\n', encoding='utf-8')
            print(f'Static run complete: {output}')
            ''',
        )
        payload = {
            'release_id': 'v1.1.0-rc1',
            'run_type': 'static',
            'provider': 'baseline',
            'model_name': 'heuristic',
            'split_name': 'test',
            'notes': 'smoke',
        }
        status, created = runs_routes.post_run(payload, repo_root=self.repo_root)
        self.assertEqual(status, 202)
        self.assertTrue(created['run_id'].startswith('run_'))
        self.assertTrue(created['job_id'].startswith('job_'))
        self.assertEqual(created['status'], 'queued')
        self.assertEqual(created['redirect_url'], f"/runs/{created['run_id']}")
        row = db_module.get_run(self.repo_root, created['run_id'])
        self.assertIsNotNone(row)
        self.assertIn(row.status, {'queued', 'running', 'completed'})
        self._wait_for_run(created['run_id'])

    def test_post_run_rejects_unknown_release(self) -> None:
        status, payload = runs_routes.post_run(
            {
                'release_id': 'v9.9.9',
                'run_type': 'static',
                'provider': 'baseline',
                'model_name': 'heuristic',
                'split_name': 'test',
            },
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 404)
        self.assertEqual(payload['error']['code'], 'release_not_found')

    def test_post_run_rejects_invalid_run_type(self) -> None:
        status, payload = runs_routes.post_run(
            {
                'release_id': 'v1.1.0-rc1',
                'run_type': 'chat',
                'provider': 'baseline',
                'model_name': 'heuristic',
                'split_name': 'test',
            },
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload['error']['code'], 'invalid_run_type')

    def test_get_run_returns_queued_running_completed(self) -> None:
        self._write_eval_module(
            'run_dynamic',
            '''
            import argparse, time
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument('--output', required=True)
            parser.add_argument('--split')
            parser.add_argument('--doctor')
            args = parser.parse_args()
            time.sleep(0.15)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{}\\n', encoding='utf-8')
            artifact_dir = output.with_suffix('') / 'run_001'
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / 'metrics.json').write_text('{}\\n', encoding='utf-8')
            (artifact_dir / 'summary.csv').write_text('a,b\\n1,2\\n', encoding='utf-8')
            print(f'Dynamic run complete: {output}')
            ''',
        )
        status, created = runs_routes.post_run(
            {
                'release_id': 'v1.1.0-rc1',
                'run_type': 'dynamic',
                'provider': 'baseline',
                'model_name': 'dummy',
                'split_name': 'test',
            },
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 202)
        initial_status, initial = runs_routes.get_run(created['run_id'], repo_root=self.repo_root)
        self.assertEqual(initial_status, 200)
        self.assertIn(initial['status'], {'queued', 'running', 'completed'})
        final = self._wait_for_run(created['run_id'])
        self.assertEqual(final['status'], 'completed')
        self.assertIsNotNone(final['results_root'])
        self.assertTrue(final['metrics_path'].endswith('metrics.json'))
        self.assertTrue(final['summary_path'].endswith('summary.csv'))

    def test_get_run_returns_failed_with_error_summary(self) -> None:
        self._write_eval_module(
            'run_static',
            '''
            import sys
            sys.stderr.write('boom\\n')
            sys.exit(1)
            ''',
        )
        status, created = runs_routes.post_run(
            {
                'release_id': 'v1.1.0-rc1',
                'run_type': 'static',
                'provider': 'baseline',
                'model_name': 'heuristic',
                'split_name': 'test',
            },
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 202)
        final = self._wait_for_run(created['run_id'])
        self.assertEqual(final['status'], 'failed')
        self.assertIsNotNone(final['error_summary'])
        self.assertIn('stdout_path', final['error_summary'])
        self.assertIn('stderr_path', final['error_summary'])

    def test_get_run_preserves_artifacts_on_failed_exit_when_available(self) -> None:
        self._write_eval_module(
            'run_dynamic',
            '''
            import argparse
            import sys
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument('--output', required=True)
            parser.add_argument('--split')
            parser.add_argument('--doctor')
            args = parser.parse_args()
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{}\\n', encoding='utf-8')
            artifact_dir = output.with_suffix('') / 'run_001'
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / 'metrics.json').write_text('{}\\n', encoding='utf-8')
            (artifact_dir / 'summary.csv').write_text('a,b\\n1,2\\n', encoding='utf-8')
            sys.stderr.write('timeout on one case\\n')
            sys.exit(1)
            ''',
        )
        status, created = runs_routes.post_run(
            {
                'release_id': 'v1.1.0-rc1',
                'run_type': 'dynamic',
                'provider': 'baseline',
                'model_name': 'dummy',
                'split_name': 'test',
            },
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 202)
        final = self._wait_for_run(created['run_id'])
        self.assertEqual(final['status'], 'failed')
        self.assertIsNotNone(final['metrics_path'])
        self.assertIsNotNone(final['summary_path'])
        self.assertTrue(final['metrics_path'].endswith('metrics.json'))
        self.assertTrue(final['summary_path'].endswith('summary.csv'))

    def test_get_run_options_returns_minimal_choices(self) -> None:
        status, payload = runs_routes.get_run_options(repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['default_split'], 'test')
        self.assertEqual(payload['run_types'], ['static', 'dynamic'])
        self.assertEqual(payload['releases'][0]['release_id'], 'v1.1.0-rc1')
        self.assertTrue(any(provider['id'] == 'gpt_oauth' for provider in payload['providers']))

    def test_post_run_accepts_gpt_oauth_provider(self) -> None:
        self._write_eval_module(
            'run_dynamic',
            '''
            import argparse, time
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument('--output', required=True)
            parser.add_argument('--split')
            parser.add_argument('--doctor')
            parser.add_argument('--provider', default=None)
            parser.add_argument('--model', default=None)
            args = parser.parse_args()
            time.sleep(0.05)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{}\\n', encoding='utf-8')
            artifact_dir = output.with_suffix('') / 'run_001'
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / 'metrics.json').write_text('{}\\n', encoding='utf-8')
            (artifact_dir / 'summary.csv').write_text('a,b\\n1,2\\n', encoding='utf-8')
            ''',
        )
        status, created = runs_routes.post_run(
            {
                'release_id': 'v1.1.0-rc1',
                'run_type': 'dynamic',
                'provider': 'gpt_oauth',
                'model_name': '',
                'split_name': 'test',
            },
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 202)
        final = self._wait_for_run(created['run_id'])
        self.assertEqual(final['provider'], 'gpt_oauth')
        self.assertEqual(final['model_name'], 'gpt-5.2')
        self.assertEqual(final['status'], 'completed')

    def test_run_registry_updated_after_completion(self) -> None:
        self._write_eval_module(
            'run_static',
            '''
            import argparse
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument('--output', required=True)
            parser.add_argument('--split')
            parser.add_argument('--mode')
            args = parser.parse_args()
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{}\\n', encoding='utf-8')
            artifact_dir = output.with_suffix('') / 'run_001'
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / 'metrics.json').write_text('{}\\n', encoding='utf-8')
            (artifact_dir / 'summary.csv').write_text('a,b\\n1,2\\n', encoding='utf-8')
            ''',
        )
        status, created = runs_routes.post_run(
            {
                'release_id': 'v1.1.0-rc1',
                'run_type': 'static',
                'provider': 'baseline',
                'model_name': 'heuristic',
                'split_name': 'test',
            },
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 202)
        self._wait_for_run(created['run_id'])
        row = db_module.get_run(self.repo_root, created['run_id'])
        self.assertIsNotNone(row)
        self.assertEqual(row.status, 'completed')
        self.assertIsNotNone(row.metrics_path)
        self.assertIsNotNone(row.summary_path)
