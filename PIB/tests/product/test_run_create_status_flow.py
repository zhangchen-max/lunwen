from __future__ import annotations

import json
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
from webapi.routes import runs as runs_routes


class RunCreateStatusFlowTests(unittest.TestCase):
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

    def _wait_terminal(self, run_id: str) -> dict:
        deadline = time.time() + 5
        while time.time() < deadline:
            status, payload = runs_routes.get_run(run_id, repo_root=self.repo_root)
            self.assertEqual(status, 200)
            if payload['status'] in {'completed', 'failed'}:
                return payload
            time.sleep(0.05)
        self.fail(f'Run {run_id} did not finish')

    def test_submit_run_returns_redirect_and_terminal_status(self) -> None:
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
            time.sleep(0.1)
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
                'provider': 'baseline',
                'model_name': 'dummy',
                'split_name': 'test',
            },
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 202)
        self.assertEqual(created['redirect_url'], f"/runs/{created['run_id']}")
        final = self._wait_terminal(created['run_id'])
        self.assertEqual(final['status'], 'completed')
        self.assertTrue(final['results_root'].startswith('results/dynamic/'))

    def test_gpt_oauth_run_uses_default_model_and_completes(self) -> None:
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
        final = self._wait_terminal(created['run_id'])
        self.assertEqual(final['status'], 'completed')
        self.assertEqual(final['provider'], 'gpt_oauth')
        self.assertEqual(final['model_name'], 'gpt-5.2')

    def test_completed_run_exposes_ready_summary_projection(self) -> None:
        self._write_eval_module(
            'run_static',
            '''
            import argparse, json, time
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument('--output', required=True)
            parser.add_argument('--split')
            parser.add_argument('--mode')
            args = parser.parse_args()
            time.sleep(0.1)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{}\\n', encoding='utf-8')
            artifact_dir = output.with_suffix('') / 'run_001'
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / 'metrics.json').write_text(
                json.dumps({'summary': {'overall': {'top1_acc': 0.5, 'top5_cov': 0.9}}}),
                encoding='utf-8',
            )
            (artifact_dir / 'summary.csv').write_text('slice,slice_value,n\\noverall,all,22\\n', encoding='utf-8')
            ''',
        )
        (self.repo_root / 'results' / 'reports' / 'pure_baselines.csv').write_text(
            'baseline_group,baseline_name,harm_flags_count,must_ask_hit_rate,n_cases,oracle_policy,split,status,task,top1_acc,top5_cov,turns\\n'
            'pure,static_heuristic,0.0,,22,no_oracle,test,active,static,0.4,0.8,\\n',
            encoding='utf-8',
        )
        (self.repo_root / 'results' / 'reports' / 'guided_llm_baselines.csv').write_text(
            'baseline_group,baseline_name,metrics_json,note,oracle_policy,predictions_jsonl,split,status,task\\n'
            'guided_llm,static_llm_guided,,note,guided,,test,reported_separately,static\\n',
            encoding='utf-8',
        )
        (self.repo_root / 'results' / 'reports' / 'deprecated_results.json').write_text(
            '{"deprecated_results":[]}',
            encoding='utf-8',
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
        final = self._wait_terminal(created['run_id'])
        self.assertEqual(final['status'], 'completed')
        status, summary = runs_routes.get_run_summary(created['run_id'], repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertIn(summary['state'], {'ready', 'partial'})
        self.assertTrue(any(item['key'] == 'top1_acc' for item in summary['overall_metrics']))
        self.assertIsNotNone(summary['baseline_compare'])

    def test_completed_run_with_missing_summary_returns_partial_projection(self) -> None:
        self._write_eval_module(
            'run_dynamic',
            '''
            import argparse, json, time
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument('--output', required=True)
            parser.add_argument('--split')
            parser.add_argument('--doctor')
            args = parser.parse_args()
            time.sleep(0.1)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{}\\n', encoding='utf-8')
            artifact_dir = output.with_suffix('') / 'run_001'
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / 'metrics.json').write_text(
                json.dumps({'summary': {'overall': {'top1_acc': 0.6, 'top5_cov': 0.85, 'must_ask_hit_rate': 0.7}}}),
                encoding='utf-8',
            )
            ''',
        )
        (self.repo_root / 'results' / 'reports' / 'pure_baselines.csv').write_text(
            'baseline_group,baseline_name,harm_flags_count,must_ask_hit_rate,n_cases,oracle_policy,split,status,task,top1_acc,top5_cov,turns\\n'
            'pure,dynamic_dummy,0.04,0.60,22,no_oracle,test,active,dynamic,0.5,0.8,5.0\\n',
            encoding='utf-8',
        )
        (self.repo_root / 'results' / 'reports' / 'guided_llm_baselines.csv').write_text(
            'baseline_group,baseline_name,metrics_json,note,oracle_policy,predictions_jsonl,split,status,task\\n'
            'guided_llm,dynamic_llm_guided,,note,guided,,test,reported_separately,dynamic\\n',
            encoding='utf-8',
        )
        (self.repo_root / 'results' / 'reports' / 'deprecated_results.json').write_text(
            '{"deprecated_results":[]}',
            encoding='utf-8',
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
        final = self._wait_terminal(created['run_id'])
        self.assertEqual(final['status'], 'completed')
        status, summary = runs_routes.get_run_summary(created['run_id'], repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(summary['state'], 'partial')
        self.assertIn('summary.csv missing', summary['warnings'])

    def test_failed_run_exposes_failed_summary_projection(self) -> None:
        self._write_eval_module(
            'run_static',
            '''
            import sys
            sys.stderr.write('runner failed\\n')
            raise SystemExit(1)
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
        final = self._wait_terminal(created['run_id'])
        self.assertEqual(final['status'], 'failed')
        status, summary = runs_routes.get_run_summary(created['run_id'], repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(summary['state'], 'failed')
        self.assertIsNotNone(summary['error_summary'])
