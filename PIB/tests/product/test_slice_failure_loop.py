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


runs_routes = load_module('pib_webapi_routes_runs_slice_flow', 'webapi/routes/runs.py')
cases_routes = load_module('pib_webapi_routes_cases_slice_flow', 'webapi/routes/cases.py')
db_module = load_module('pib_webapi_db_slice_flow', 'webapi/db.py')


class SliceFailureLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        shutil.copytree(REPO_ROOT / 'ontology', self.repo_root / 'ontology')
        shutil.copy2(REPO_ROOT / 'pib_config.yaml', self.repo_root / 'pib_config.yaml')
        (self.repo_root / 'data' / 'splits').mkdir(parents=True)
        (self.repo_root / 'results' / 'reports').mkdir(parents=True)
        (self.repo_root / 'results' / 'dynamic' / 'dummy' / 'run_flow' / 'run_001').mkdir(parents=True)
        db_module.init_db(self.repo_root)
        self._seed_casebank()
        self._seed_reports()
        self.run_id = self._insert_completed_run()

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

    def _seed_reports(self) -> None:
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

    def _insert_completed_run(self) -> str:
        run_id = 'run_slice_flow_completed'
        results_root = 'results/dynamic/dummy/run_flow/run_001/'
        root = self.repo_root / results_root
        (root / 'metrics.json').write_text(
            json.dumps({'summary': {'overall': {'top1_acc': 0.33, 'top3_cov': 0.67, 'must_ask_hit_rate': 0.69, 'svcl_coverage': 0.69}}}),
            encoding='utf-8',
        )
        (root / 'summary.csv').write_text('slice,slice_value,n\noverall,all,3\n', encoding='utf-8')
        prediction_rows = [
            {
                'case_id': 'PIB_0001',
                'asked_slots': ['intrusive_thoughts', 'ritual_behavior_present', 'intrusive_thoughts'],
                'metrics': {'top1_acc': 0.0, 'top3_cov': 0.0, 'must_ask_hit_rate': 0.75, 'svcl_coverage': 0.75},
                'harm_flags': [],
                'termination_reason': 'repeat_slot',
                'final_output': {
                    'diagnosis_topk': [{'label': 'OTHER', 'confidence': 1.0}],
                    'risk_flags': {'suicide': False, 'violence': False, 'psychosis': False, 'substance': False},
                    'justification': [{'claim': '模型未能输出有效 FINAL，默认 OTHER。', 'support_slots': []}],
                },
                'turn_logs': [
                    {
                        'turn': 1,
                        'doctor_action': {'slot_id': 'intrusive_thoughts', 'utterance': '会不会有一些不想要的念头反复闯进来？'},
                        'patient_answer': {'utterance': '那些念头会自己冒出来，我不想要。'},
                    },
                    {
                        'turn': 2,
                        'doctor_action': {'slot_id': 'intrusive_thoughts', 'utterance': '这些念头是不是还会反复出现？'},
                        'patient_answer': {'utterance': '是，一直会重复冒出来。'},
                    },
                ],
            },
            {
                'case_id': 'PIB_0041',
                'asked_slots': ['longstanding_pattern', 'relationship_instability', 'abandonment_sensitivity', 'impairment_social', 'self_harm_ideation'],
                'metrics': {'top1_acc': 1.0, 'top3_cov': 1.0, 'must_ask_hit_rate': 1.0, 'svcl_coverage': 1.0},
                'harm_flags': [],
                'termination_reason': 'timeout',
                'timeout_error': True,
                'adapter_latency_ms': 4321,
                'final_output': {'diagnosis_topk': [{'label': 'BPD', 'confidence': 0.72}]},
            },
            {
                'case_id': 'PIB_0051',
                'asked_slots': ['onset_time'],
                'metrics': {'top1_acc': 1.0, 'top3_cov': 1.0, 'must_ask_hit_rate': 0.33, 'svcl_coverage': 0.33},
                'harm_flags': ['overconfident_dx'],
                'parse_error': True,
                'termination_reason': 'invalid_slot_id_limit',
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
        db_module.insert_job(
            self.repo_root,
            {
                'job_id': 'job_slice_flow',
                'job_type': 'run_dynamic',
                'status': 'succeeded',
                'target_release_id': 'v1.1.0-rc1',
                'started_at': '2026-03-09T00:00:00Z',
                'finished_at': '2026-03-09T00:00:10Z',
                'exit_code': 0,
                'stdout_path': None,
                'stderr_path': None,
                'result_json_path': None,
                'error_summary_json': None,
            },
        )
        db_module.insert_run(
            self.repo_root,
            {
                'run_id': run_id,
                'release_id': 'v1.1.0-rc1',
                'job_id': 'job_slice_flow',
                'run_type': 'dynamic',
                'provider': 'baseline',
                'model_name': 'dummy',
                'split_name': 'test',
                'status': 'completed',
                'config_json': '{}',
                'results_root': results_root,
                'metrics_path': f'{results_root}metrics.json',
                'summary_path': f'{results_root}summary.csv',
                'created_at': '2026-03-09T00:00:00Z',
                'started_at': '2026-03-09T00:00:01Z',
                'finished_at': '2026-03-09T00:00:10Z',
                'error_summary_json': None,
            },
        )
        return run_id

    def test_run_summary_to_slices_to_case_detail_loop(self) -> None:
        status, summary = runs_routes.get_run_summary(self.run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertIn(summary['state'], {'ready', 'partial'})
        self.assertTrue(summary['process_score'])
        self.assertTrue(summary['compliance_score'])
        self.assertTrue(summary['final_diagnosis_score'])
        self.assertIsNotNone(summary['failure_attribution'])

        status, slices = cases_routes.get_run_slices(self.run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(slices['state'], 'ready')
        self.assertIn('by_failure_source', slices['slices'])
        self.assertIn('by_protocol_clean_only', slices['slices'])

        status, filtered_cases = cases_routes.get_run_cases(
            self.run_id,
            {'failure_bucket': 'top1_wrong', 'limit': 50, 'offset': 0},
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(filtered_cases['total'], 1)
        target_case = filtered_cases['items'][0]['case_id']

        status, case_detail = cases_routes.get_run_case_detail(self.run_id, target_case, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertIn('failure_buckets', case_detail['failure_analysis'])
        self.assertIn(case_detail['state'], {'ready', 'partial'})
        self.assertIn('failure_sources', case_detail['failure_analysis'])
        self.assertIn('termination_reason', case_detail['run_output'])
        self.assertIn('final_consumable', case_detail['run_output'])

    def test_case_detail_shows_partial_when_replay_missing(self) -> None:
        status, payload = cases_routes.get_run_case_detail(self.run_id, 'PIB_0041', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'partial')
        self.assertFalse(payload['dynamic_replay']['available'])
        self.assertIn('Replay unavailable', payload['warnings'])
        self.assertTrue(payload['run_output']['timeout_error'])
        self.assertEqual(payload['run_output']['termination_reason'], 'timeout')

    def test_case_list_can_filter_by_failure_source(self) -> None:
        status, payload = cases_routes.get_run_cases(
            self.run_id,
            {'failure_source': 'protocol', 'limit': 50, 'offset': 0},
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload['items'][0]['failure_source'], 'protocol')

    def test_case_detail_exposes_repeat_slot_and_invalid_final_metadata(self) -> None:
        status, payload = cases_routes.get_run_case_detail(self.run_id, 'PIB_0001', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'ready')
        self.assertEqual(payload['run_output']['termination_reason'], 'repeat_slot')
        self.assertEqual(payload['run_output']['repeat_slot_count'], 1)
        self.assertFalse(payload['run_output']['final_consumable'])
        self.assertEqual(payload['failure_analysis']['fallback_other_reason'], 'invalid_final_placeholder')
        self.assertTrue(payload['dynamic_replay']['available'])

    def test_case_detail_exposes_parse_error_metadata(self) -> None:
        status, payload = cases_routes.get_run_case_detail(self.run_id, 'PIB_0051', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'partial')
        self.assertTrue(payload['run_output']['parse_error'])
        self.assertEqual(payload['run_output']['parse_retry_count'], 1)
        self.assertEqual(payload['run_output']['invalid_slot_count'], 1)
        self.assertFalse(payload['run_output']['final_consumable'])
        self.assertEqual(payload['failure_analysis']['fallback_other_reason'], 'parse_error_default_other')
