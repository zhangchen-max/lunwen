from __future__ import annotations

import importlib.util
import json
import shutil
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


release_routes = load_module('pib_webapi_release_routes_p0_smoke', 'webapi/routes/releases.py')
runs_routes = load_module('pib_webapi_run_routes_p0_smoke', 'webapi/routes/runs.py')
cases_routes = load_module('pib_webapi_case_routes_p0_smoke', 'webapi/routes/cases.py')
db_module = load_module('pib_webapi_db_p0_smoke', 'webapi/db.py')


class P0HappyPathSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        shutil.copytree(REPO_ROOT / 'ontology', self.repo_root / 'ontology')
        shutil.copy2(REPO_ROOT / 'pib_config.yaml', self.repo_root / 'pib_config.yaml')
        (self.repo_root / 'data' / 'splits').mkdir(parents=True)
        (self.repo_root / 'release').mkdir(parents=True)
        (self.repo_root / 'results' / 'reports').mkdir(parents=True)
        (self.repo_root / 'results' / 'audit').mkdir(parents=True)
        (self.repo_root / 'eval').mkdir(parents=True)
        (self.repo_root / 'eval' / '__init__.py').write_text('', encoding='utf-8')
        db_module.init_db(self.repo_root)
        self._seed_release()
        self._seed_casebank()
        self._write_eval_module()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _read_selected_rows(self, path: Path, selected_ids: set[str]) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['case_id'] in selected_ids:
                rows.append(row)
        return rows

    def _seed_release(self) -> None:
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
        (bundle / 'README.md').write_text('bundle', encoding='utf-8')
        (self.repo_root / 'results' / 'reports' / 'pure_baselines.csv').write_text(
            'baseline_group,baseline_name,harm_flags_count,must_ask_hit_rate,n_cases,oracle_policy,split,status,task,top1_acc,top5_cov,turns\n'
            'pure,dynamic_dummy,0.04,0.60,22,no_oracle,test,active,dynamic,0.63,0.81,5.0\n',
            encoding='utf-8',
        )
        (self.repo_root / 'results' / 'reports' / 'guided_llm_baselines.csv').write_text(
            'baseline_group,baseline_name,metrics_json,note,oracle_policy,predictions_jsonl,split,status,task\n'
            'guided_llm,dynamic_llm_guided,,note,guided,,test,reported_separately,dynamic\n',
            encoding='utf-8',
        )
        (self.repo_root / 'results' / 'reports' / 'deprecated_results.json').write_text(
            '{"deprecated_results":[]}',
            encoding='utf-8',
        )
        (self.repo_root / 'results' / 'audit' / 'no_oracle_baselines.json').write_text('{}', encoding='utf-8')
        (self.repo_root / 'results' / 'audit' / 'text_contamination_scan.json').write_text('{}', encoding='utf-8')

    def _seed_casebank(self) -> None:
        selected_ids = {'PIB_0001', 'PIB_0041', 'PIB_0051'}
        case_rows = self._read_selected_rows(REPO_ROOT / 'data' / 'cases.jsonl', selected_ids)
        rubric_rows = self._read_selected_rows(REPO_ROOT / 'data' / 'rubrics.jsonl', selected_ids)
        for row in case_rows:
            if row['case_id'] == 'PIB_0051':
                row['ambiguity'] = 'unambiguous'
        (self.repo_root / 'data' / 'cases.jsonl').write_text(
            ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in case_rows),
            encoding='utf-8',
        )
        (self.repo_root / 'data' / 'rubrics.jsonl').write_text(
            ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rubric_rows),
            encoding='utf-8',
        )
        (self.repo_root / 'data' / 'splits' / 'test_ids.txt').write_text('PIB_0001\nPIB_0041\nPIB_0051\n', encoding='utf-8')
        (self.repo_root / 'data' / 'splits' / 'train_ids.txt').write_text('', encoding='utf-8')
        (self.repo_root / 'data' / 'splits' / 'dev_ids.txt').write_text('', encoding='utf-8')

    def _write_eval_module(self) -> None:
        (self.repo_root / 'eval' / 'run_dynamic.py').write_text(
            textwrap.dedent(
                '''
                import argparse
                import json
                import time
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
                    json.dumps({'summary': {'overall': {'top1_acc': 0.33, 'top3_cov': 0.67, 'must_ask_hit_rate': 0.69, 'svcl_coverage': 0.69}}}),
                    encoding='utf-8',
                )
                (artifact_dir / 'summary.csv').write_text('slice,slice_value,n\\noverall,all,3\\n', encoding='utf-8')
                rows = [
                    {
                        'case_id': 'PIB_0001',
                        'asked_slots': ['intrusive_thoughts', 'ritual_behavior_present', 'onset_time'],
                        'metrics': {'top1_acc': 0.0, 'top3_cov': 1.0, 'must_ask_hit_rate': 0.75, 'svcl_coverage': 0.75},
                        'harm_flags': [],
                        'final_output': {'diagnosis_topk': [{'label': 'BDD', 'confidence': 0.41}, {'label': 'OCD', 'confidence': 0.33}]},
                        'turn_logs': [
                            {
                                'turn': 1,
                                'doctor_action': {'slot_id': 'intrusive_thoughts', 'utterance': '会不会有一些不想要的念头反复闯进来？'},
                                'patient_answer': {'utterance': '那些念头会自己冒出来，我不想要。'},
                            }
                        ],
                    },
                    {
                        'case_id': 'PIB_0041',
                        'asked_slots': ['longstanding_pattern', 'relationship_instability', 'abandonment_sensitivity', 'impairment_social', 'self_harm_ideation'],
                        'metrics': {'top1_acc': 1.0, 'top3_cov': 1.0, 'must_ask_hit_rate': 1.0, 'svcl_coverage': 1.0},
                        'harm_flags': [],
                        'final_output': {'diagnosis_topk': [{'label': 'BPD', 'confidence': 0.72}]},
                    },
                    {
                        'case_id': 'PIB_0051',
                        'asked_slots': ['onset_time'],
                        'metrics': {'top1_acc': 0.0, 'top3_cov': 0.0, 'must_ask_hit_rate': 0.33, 'svcl_coverage': 0.33},
                        'harm_flags': ['overconfident_dx'],
                        'parse_error': True,
                        'final_output': {'diagnosis_topk': [{'label': 'ADJ', 'confidence': 0.51}]},
                    },
                ]
                (artifact_dir / 'predictions.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\\n' for row in rows), encoding='utf-8')
                print(f'Dynamic run complete: {output}')
                '''
            ),
            encoding='utf-8',
        )

    def _wait_terminal(self, run_id: str, timeout_sec: float = 5.0) -> dict:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            status, payload = runs_routes.get_run(run_id, repo_root=self.repo_root)
            self.assertEqual(status, 200)
            if payload['status'] in {'completed', 'failed'}:
                return payload
            time.sleep(0.05)
        self.fail(f'Run {run_id} did not finish')

    def test_p0_happy_path_smoke(self) -> None:
        status, releases = release_routes.get_releases(repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(releases['items'][0]['release_id'], 'v1.1.0-rc1')

        status, detail = release_routes.get_release_detail('v1.1.0-rc1', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(detail['manifest']['benchmark_version'], '1.1.0-rc1')

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
        run_id = created['run_id']

        run = self._wait_terminal(run_id)
        self.assertEqual(run['status'], 'completed')

        status, summary = runs_routes.get_run_summary(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertIn(summary['state'], {'ready', 'partial'})

        status, slices = cases_routes.get_run_slices(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertIn(slices['state'], {'ready', 'partial'})
        self.assertGreater(slices['totals']['case_count'], 0)

        status, cases = cases_routes.get_run_cases(run_id, {'failure_bucket': 'top1_wrong', 'limit': 50, 'offset': 0}, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertGreater(cases['total'], 0)

        case_id = cases['items'][0]['case_id']
        status, case_detail = cases_routes.get_run_case_detail(run_id, case_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertIn(case_detail['state'], {'ready', 'partial'})
        self.assertIn('failure_buckets', case_detail['failure_analysis'])
