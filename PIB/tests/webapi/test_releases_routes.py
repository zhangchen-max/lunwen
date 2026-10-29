from __future__ import annotations

import json
import importlib.util
import tempfile
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


release_routes = load_module('pib_webapi_routes_releases', 'webapi/routes/releases.py')
server_module = load_module('pib_webapi_server', 'webapi/server.py')
create_handler = server_module.create_handler


class ReleasesRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / 'release').mkdir(parents=True)
        (self.repo_root / 'results' / 'reports').mkdir(parents=True)
        (self.repo_root / 'results' / 'audit').mkdir(parents=True)
        bundle_dir = self.repo_root / 'release' / 'PIB-Benchmark-v1.1.0-rc1'
        bundle_dir.mkdir(parents=True)

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
        for path in [self.repo_root / 'release' / 'benchmark_manifest.json', bundle_dir / 'benchmark_manifest.json']:
            path.write_text(json.dumps(manifest), encoding='utf-8')
        (bundle_dir / 'README.md').write_text('release bundle', encoding='utf-8')
        (self.repo_root / 'results' / 'reports' / 'pure_baselines.csv').write_text('a,b\n1,2\n', encoding='utf-8')
        (self.repo_root / 'results' / 'reports' / 'guided_llm_baselines.csv').write_text('a,b\n1,2\n', encoding='utf-8')
        (self.repo_root / 'results' / 'reports' / 'deprecated_results.json').write_text(json.dumps({'benchmark_version': 'v1.1.0-rc1'}), encoding='utf-8')
        (self.repo_root / 'results' / 'audit' / 'no_oracle_baselines.json').write_text(json.dumps({'ok': True}), encoding='utf-8')
        (self.repo_root / 'results' / 'audit' / 'text_contamination_scan.json').write_text(json.dumps({'ok': True}), encoding='utf-8')
        (self.repo_root / 'results' / 'audit' / 'extra_audit.json').write_text(json.dumps({'ok': True}), encoding='utf-8')

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_get_releases_returns_rc1(self) -> None:
        status, payload = release_routes.get_releases(repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['items'][0]['release_id'], 'v1.1.0-rc1')

    def test_get_releases_includes_manifest_fields(self) -> None:
        _, payload = release_routes.get_releases(repo_root=self.repo_root)
        item = payload['items'][0]
        self.assertEqual(item['benchmark_version'], '1.1.0-rc1')
        self.assertEqual(item['dataset_hash_sha256'], 'dataset-hash')
        self.assertIn('results/reports/pure_baselines.csv', item['baseline_reports'])
        self.assertIn('results/audit/no_oracle_baselines.json', item['audit_reports'])
        self.assertEqual(item['deprecated_results_path'], 'results/reports/deprecated_results.json')

    def test_get_release_detail_returns_manifest_bundle_reports(self) -> None:
        status, payload = release_routes.get_release_detail('v1.1.0-rc1', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['manifest']['slot_count'], 120)
        self.assertEqual(payload['bundle']['path'], 'release/PIB-Benchmark-v1.1.0-rc1/')
        self.assertEqual(payload['reports']['pure_baselines'], 'results/reports/pure_baselines.csv')
        self.assertEqual(payload['audits']['no_oracle'], 'results/audit/no_oracle_baselines.json')

    def test_get_release_detail_404_for_unknown_release(self) -> None:
        status, payload = release_routes.get_release_detail('v0.0.0', repo_root=self.repo_root)
        self.assertEqual(status, 404)
        self.assertEqual(payload['error']['code'], 'release_not_found')

    def test_get_release_detail_partial_when_bundle_missing(self) -> None:
        bundle_dir = self.repo_root / 'release' / 'PIB-Benchmark-v1.1.0-rc1'
        for child in bundle_dir.iterdir():
            child.unlink()
        bundle_dir.rmdir()
        status, payload = release_routes.get_release_detail('v1.1.0-rc1', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertTrue(payload['partial'])
        self.assertEqual(payload['state'], 'partial')
        self.assertEqual(payload['bundle']['path'], None)

    def test_release_routes_only_add_pr2_job_posts(self) -> None:
        handler_cls = create_handler(repo_root=self.repo_root)
        self.assertTrue('do_GET' in handler_cls.__dict__)
        self.assertTrue('do_POST' in handler_cls.__dict__)
