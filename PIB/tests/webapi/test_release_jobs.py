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


release_routes = load_module('pib_webapi_routes_releases_jobs', 'webapi/routes/releases.py')
db_module = load_module('pib_webapi_db_jobs', 'webapi/db.py')


class ReleaseJobsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / 'release').mkdir(parents=True)
        (self.repo_root / 'results' / 'reports').mkdir(parents=True)
        (self.repo_root / 'results' / 'audit').mkdir(parents=True)
        (self.repo_root / 'scripts').mkdir(parents=True)
        (self.repo_root / 'scripts' / '__init__.py').write_text('', encoding='utf-8')
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
        (self.repo_root / 'results' / 'audit' / 'no_oracle_baselines.json').write_text('{}', encoding='utf-8')
        (self.repo_root / 'results' / 'audit' / 'text_contamination_scan.json').write_text('{}', encoding='utf-8')

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_script(self, relative_path: str, body: str) -> None:
        path = self.repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body), encoding='utf-8')

    def _wait_for_terminal(self, job_id: str, timeout_sec: float = 5.0) -> dict:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            status, payload = release_routes.get_job(job_id, repo_root=self.repo_root)
            self.assertEqual(status, 200)
            if payload['status'] in {'succeeded', 'failed'}:
                return payload
            time.sleep(0.05)
        self.fail(f'Job {job_id} did not reach terminal state within timeout')

    def test_validate_current_success_updates_job_and_release_registry(self) -> None:
        self._write_script(
            'scripts/validate_all.py',
            '''
            print('Validation passed')
            ''',
        )
        status, payload = release_routes.post_validate_current(repo_root=self.repo_root)
        self.assertEqual(status, 202)
        result = self._wait_for_terminal(payload['job_id'])
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['result']['status'], 'succeeded')
        release_row = db_module.get_release(self.repo_root, 'v1.1.0-rc1')
        self.assertIsNotNone(release_row)
        self.assertEqual(release_row.last_validated_job_id, payload['job_id'])
        self.assertTrue((self.repo_root / result['stdout_path']).exists())
        self.assertTrue((self.repo_root / result['result_json_path']).exists())

    def test_validate_current_failure_structures_errors(self) -> None:
        self._write_script(
            'scripts/validate_all.py',
            '''
            import sys
            print('Validation failed')
            print('[PIB_0123] label_subtype is required when label == OS_OCRD')
            print('[row 4] schema error: field required')
            sys.exit(1)
            ''',
        )
        status, payload = release_routes.post_validate_current(repo_root=self.repo_root)
        self.assertEqual(status, 202)
        result = self._wait_for_terminal(payload['job_id'])
        self.assertEqual(result['status'], 'failed')
        structured = result['structured_errors']
        self.assertEqual(structured[0]['case_id'], 'PIB_0123')
        self.assertEqual(structured[0]['field'], 'label_subtype')
        self.assertIn('schema error', structured[1]['message'])

    def test_freeze_current_runs_both_scripts_and_updates_registry(self) -> None:
        self._write_script(
            'scripts/freeze_release.py',
            '''
            import json
            from pathlib import Path
            root = Path('.')
            bundle = root / 'release' / 'PIB-Benchmark-v1.1.0-rc1'
            bundle.mkdir(parents=True, exist_ok=True)
            manifest = json.loads((root / 'release' / 'benchmark_manifest.json').read_text())
            (bundle / 'benchmark_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            (bundle / 'README.md').write_text('bundle', encoding='utf-8')
            print('Release manifest written')
            ''',
        )
        self._write_script(
            'scripts/freeze_release_reports.py',
            '''
            from pathlib import Path
            root = Path('.')
            reports = root / 'results' / 'reports'
            reports.mkdir(parents=True, exist_ok=True)
            (reports / 'pure_baselines.csv').write_text('a,b\\n1,2\\n', encoding='utf-8')
            (reports / 'guided_llm_baselines.csv').write_text('a,b\\n1,2\\n', encoding='utf-8')
            (reports / 'deprecated_results.json').write_text('{}', encoding='utf-8')
            print('Release baseline reports written')
            ''',
        )
        status, payload = release_routes.post_freeze_current(repo_root=self.repo_root)
        self.assertEqual(status, 202)
        result = self._wait_for_terminal(payload['job_id'])
        self.assertEqual(result['status'], 'succeeded')
        release_row = db_module.get_release(self.repo_root, 'v1.1.0-rc1')
        self.assertIsNotNone(release_row)
        self.assertEqual(release_row.last_frozen_job_id, payload['job_id'])
        self.assertEqual(release_row.status, 'frozen')
        self.assertTrue((self.repo_root / 'release' / 'PIB-Benchmark-v1.1.0-rc1' / 'benchmark_manifest.json').exists())

    def test_get_job_404_for_unknown_job(self) -> None:
        status, payload = release_routes.get_job('job_missing', repo_root=self.repo_root)
        self.assertEqual(status, 404)
        self.assertEqual(payload['error']['code'], 'job_not_found')
