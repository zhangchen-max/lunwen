from __future__ import annotations

import importlib.util
import json
import shutil
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


db_module = load_module('pib_webapi_db_summary', 'webapi/db.py')
runs_routes = load_module('pib_webapi_runs_routes_summary', 'webapi/routes/runs.py')
artifact_service = load_module('pib_webapi_artifacts_summary', 'webapi/artifacts.py')


class RunSummaryRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        shutil.copytree(REPO_ROOT / 'ontology', self.repo_root / 'ontology')
        shutil.copy2(REPO_ROOT / 'pib_config.yaml', self.repo_root / 'pib_config.yaml')
        (self.repo_root / 'data' / 'splits').mkdir(parents=True)
        (self.repo_root / 'results' / 'reports').mkdir(parents=True)
        (self.repo_root / 'artifacts' / 'jobs' / 'job_1').mkdir(parents=True)
        (self.repo_root / 'results' / 'dynamic' / 'dummy' / 'run_1' / 'run_001').mkdir(parents=True)
        db_module.init_db(self.repo_root)
        self._seed_casebank()
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
            json.dumps({'deprecated_results': [{'path': 'results/dynamic/old', 'kind': 'run_artifact_dir'}]}),
            encoding='utf-8',
        )
        (self.repo_root / 'artifacts' / 'jobs' / 'job_1' / 'stdout.log').write_text('ok\n', encoding='utf-8')
        (self.repo_root / 'artifacts' / 'jobs' / 'job_1' / 'stderr.log').write_text('', encoding='utf-8')

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _read_selected_rows(self, path: Path, selected_ids: set[str]) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['case_id'] in selected_ids:
                rows.append(row)
        return rows

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
        (self.repo_root / 'data' / 'splits' / 'test_ids.txt').write_text(
            'PIB_0001\nPIB_0041\nPIB_0051\n',
            encoding='utf-8',
        )
        (self.repo_root / 'data' / 'splits' / 'train_ids.txt').write_text('', encoding='utf-8')
        (self.repo_root / 'data' / 'splits' / 'dev_ids.txt').write_text('', encoding='utf-8')

    def _insert_run(self, *, status: str, metrics: bool = True, summary: bool = True, run_type: str = 'dynamic') -> str:
        run_id = f'run_{status}_{run_type}'
        results_root = f'results/{run_type}/dummy/{run_id}/run_001/'
        root = self.repo_root / results_root
        root.mkdir(parents=True, exist_ok=True)
        metrics_path = root / 'metrics.json'
        summary_path = root / 'summary.csv'
        if metrics:
            metrics_path.write_text(
                json.dumps(
                    {
                        'summary': {
                            'overall': {
                                'top1_acc': 0.72,
                                'top3_cov': 0.88,
                                'must_ask_hit_rate': 0.64,
                                'svcl_coverage': 0.91,
                                'turns': 5.0,
                            }
                        }
                    }
                ),
                encoding='utf-8',
            )
        if summary:
            summary_path.write_text('slice,slice_value,n\noverall,all,22\n', encoding='utf-8')
        if run_type == 'dynamic':
            prediction_rows = [
                {
                    'case_id': 'PIB_0001',
                    'asked_slots': ['intrusive_thoughts', 'ritual_behavior_present', 'onset_time'],
                    'metrics': {'top1_acc': 0.0, 'top3_cov': 1.0, 'must_ask_hit_rate': 0.75, 'svcl_coverage': 0.75},
                    'harm_flags': [],
                    'case_status': 'completed',
                    'parse_retry_count': 0,
                    'final_consumable': False,
                    'invalid_final_reason': 'invalid_final_placeholder',
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
                    'case_status': 'completed',
                    'parse_retry_count': 0,
                    'final_consumable': True,
                    'final_output': {'diagnosis_topk': [{'label': 'BPD', 'confidence': 0.72}]},
                },
                {
                    'case_id': 'PIB_0051',
                    'asked_slots': ['onset_time'],
                    'metrics': {'top1_acc': 0.0, 'top3_cov': 0.0, 'must_ask_hit_rate': 0.33, 'svcl_coverage': 0.33},
                    'harm_flags': ['overconfident_dx'],
                    'parse_error': True,
                    'case_status': 'completed',
                    'parse_retry_count': 2,
                    'final_consumable': False,
                    'invalid_final_reason': 'missing_diagnosis_topk',
                    'diagnosis_topk': [{'label': 'OTHER', 'confidence': 0.9}],
                    'final_output': {
                        'risk_flags': {'suicide': False, 'violence': False, 'psychosis': False, 'substance': False},
                        'justification': [{'claim': '模型未能输出有效 FINAL，默认 OTHER。', 'support_slots': []}],
                    },
                },
            ]
            (root / 'predictions.jsonl').write_text(
                ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in prediction_rows),
                encoding='utf-8',
            )
        else:
            (root / 'predictions.jsonl').write_text('{}\n', encoding='utf-8')
        db_module.insert_job(
            self.repo_root,
            {
                'job_id': 'job_1',
                'job_type': 'run_dynamic',
                'status': 'succeeded' if status == 'completed' else 'failed' if status == 'failed' else 'running',
                'target_release_id': 'v1.1.0-rc1',
                'started_at': '2026-03-09T00:00:00Z',
                'finished_at': '2026-03-09T00:00:10Z' if status in {'completed', 'failed'} else None,
                'exit_code': 0 if status == 'completed' else 1 if status == 'failed' else None,
                'stdout_path': 'artifacts/jobs/job_1/stdout.log',
                'stderr_path': 'artifacts/jobs/job_1/stderr.log',
                'result_json_path': None,
                'error_summary_json': None,
            },
        )
        db_module.insert_run(
            self.repo_root,
            {
                'run_id': run_id,
                'release_id': 'v1.1.0-rc1',
                'job_id': 'job_1',
                'run_type': run_type,
                'provider': 'baseline',
                'model_name': 'dummy',
                'split_name': 'test',
                'status': status,
                'config_json': '{}',
                'results_root': results_root,
                'metrics_path': str(metrics_path.relative_to(self.repo_root)) if metrics else None,
                'summary_path': str(summary_path.relative_to(self.repo_root)) if summary else None,
                'created_at': '2026-03-09T00:00:00Z',
                'started_at': '2026-03-09T00:00:01Z',
                'finished_at': '2026-03-09T00:00:10Z' if status in {'completed', 'failed'} else None,
                'error_summary_json': json.dumps({'message': 'subprocess exited with code 1', 'stdout_path': 'artifacts/jobs/job_1/stdout.log', 'stderr_path': 'artifacts/jobs/job_1/stderr.log'}) if status == 'failed' else None,
            },
        )
        return run_id

    def test_get_run_summary_pending_for_running_run(self) -> None:
        run_id = self._insert_run(status='running')
        status, payload = runs_routes.get_run_summary(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'pending')
        self.assertEqual(payload['overall_metrics'], [])

    def test_get_run_summary_ready_for_completed_run(self) -> None:
        run_id = self._insert_run(status='completed')
        status, payload = runs_routes.get_run_summary(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'ready')
        self.assertTrue(any(item['key'] == 'top1_acc' for item in payload['overall_metrics']))
        self.assertIsNotNone(payload['baseline_compare'])
        self.assertTrue(payload['process_score'])
        self.assertTrue(payload['compliance_score'])
        self.assertTrue(payload['final_diagnosis_score'])
        self.assertIsNotNone(payload['failure_attribution'])
        compliance_keys = {item['key'] for item in payload['compliance_score']}
        self.assertIn('parse_error_rate', compliance_keys)
        self.assertIn('invalid_final_rate', compliance_keys)
        self.assertEqual(payload['failure_attribution']['protocol_failure_count'], 2)
        self.assertEqual(payload['failure_attribution']['capability_failure_count'], 0)
        self.assertEqual(payload['failure_attribution']['failure_source_counts']['protocol'], 2)
        self.assertEqual(payload['failure_attribution']['parse_retry_count'], 2.0)
        self.assertAlmostEqual(payload['failure_attribution']['parse_error_rate'], 1 / 3)
        self.assertAlmostEqual(payload['failure_attribution']['invalid_final_rate'], 2 / 3)
        self.assertTrue(any(item['key'] == 'oracle_final_top1_acc' for item in payload['supplemental']['oracle_final_metrics']))

    def test_get_run_summary_partial_when_summary_missing(self) -> None:
        run_id = self._insert_run(status='completed', summary=False)
        status, payload = runs_routes.get_run_summary(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'partial')
        self.assertIn('summary.csv missing', payload['warnings'])

    def test_get_run_summary_failed_for_failed_run(self) -> None:
        run_id = self._insert_run(status='failed')
        status, payload = runs_routes.get_run_summary(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'failed')
        self.assertIsNotNone(payload['error_summary'])
        self.assertIsNotNone(payload['failure_attribution'])

    def test_get_run_summary_failed_marks_bridge_timeout(self) -> None:
        run_id = self._insert_run(status='failed')
        db_module.update_run(
            self.repo_root,
            run_id,
            error_summary_json=json.dumps(
                {
                    'message': 'relay request timed out',
                    'stdout_path': 'artifacts/jobs/job_1/stdout.log',
                    'stderr_path': 'artifacts/jobs/job_1/stderr.log',
                }
            ),
        )
        (self.repo_root / 'artifacts' / 'jobs' / 'job_1' / 'stderr.log').write_text('TimeoutError: timed out\n', encoding='utf-8')
        status, payload = runs_routes.get_run_summary(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['failure_attribution']['bridge_failure_count'], 1)
        self.assertTrue(payload['failure_attribution']['bridge']['timeout'])

    def test_get_run_artifacts_lists_metrics_and_summary(self) -> None:
        run_id = self._insert_run(status='completed')
        status, payload = runs_routes.get_run_artifacts(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        labels = {item['label'] for item in payload['items']}
        self.assertIn('metrics.json', labels)
        self.assertIn('summary.csv', labels)
        self.assertIn('stdout.log', labels)

    def test_download_artifact_rejects_path_traversal(self) -> None:
        with self.assertRaises(artifact_service.ArtifactPathNotAllowedError):
            artifact_service.resolve_download_path('../secret.txt', repo_root=self.repo_root)

    def test_download_artifact_serves_allowed_file(self) -> None:
        run_id = self._insert_run(status='completed')
        resolved = artifact_service.resolve_download_path(
            f'results/dynamic/dummy/{run_id}/run_001/metrics.json',
            repo_root=self.repo_root,
        )
        self.assertTrue(resolved.exists())
        self.assertIn('"top1_acc": 0.72', resolved.read_text(encoding='utf-8'))

    def test_baseline_compare_returns_warnings_when_no_match(self) -> None:
        run_id = self._insert_run(status='completed', run_type='static')
        status, payload = runs_routes.get_run_summary(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'partial')
        self.assertIn('No matching baseline row found for current run.', payload['baseline_compare']['warnings'])
