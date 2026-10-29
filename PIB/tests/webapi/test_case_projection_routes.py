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


cases_routes = load_module('pib_webapi_routes_cases', 'webapi/routes/cases.py')
db_module = load_module('pib_webapi_db_case_projection', 'webapi/db.py')


class CaseProjectionRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        shutil.copytree(REPO_ROOT / 'ontology', self.repo_root / 'ontology')
        shutil.copy2(REPO_ROOT / 'pib_config.yaml', self.repo_root / 'pib_config.yaml')
        (self.repo_root / 'data' / 'splits').mkdir(parents=True)
        (self.repo_root / 'results' / 'dynamic' / 'dummy' / 'run_fixture' / 'run_001').mkdir(parents=True)
        db_module.init_db(self.repo_root)
        self._seed_casebank()

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

    def _insert_run(self, *, status: str = 'completed') -> str:
        run_id = f'run_case_projection_{status}'
        results_root = 'results/dynamic/dummy/run_fixture/run_001/'
        root = self.repo_root / results_root
        root.mkdir(parents=True, exist_ok=True)
        (root / 'metrics.json').write_text(
            json.dumps({'summary': {'overall': {'top1_acc': 0.4, 'top3_cov': 0.7, 'must_ask_hit_rate': 0.75, 'svcl_coverage': 0.83}}}),
            encoding='utf-8',
        )
        (root / 'summary.csv').write_text('slice,slice_value,n\noverall,all,3\n', encoding='utf-8')
        prediction_rows = [
            {
                'case_id': 'PIB_0001',
                'dsm_module': 'OCRD',
                'label': 'OCD',
                'ambiguity': 'ambiguous',
                'asked_slots': ['intrusive_thoughts', 'ritual_behavior_present', 'intrusive_thoughts'],
                'harm_flags': [],
                'termination_reason': 'repeat_slot',
                'case_status': 'completed',
                'parse_retry_count': 0,
                'final_consumable': False,
                'invalid_final_reason': 'invalid_final_placeholder',
                'metrics': {
                    'top1_acc': 0.0,
                    'top3_cov': 1.0,
                    'must_ask_hit_rate': 0.75,
                    'svcl_coverage': 0.75,
                },
                'final_output': {
                    'diagnosis_topk': [{'label': 'OTHER', 'confidence': 1.0}],
                    'justification': [{'claim': '模型未能输出有效 FINAL，默认 OTHER。', 'support_slots': []}],
                    'risk_flags': {'suicide': False, 'violence': False, 'psychosis': False, 'substance': False},
                },
                'turn_logs': [
                    {
                        'turn': 1,
                        'doctor_action': {
                            'slot_id': 'intrusive_thoughts',
                            'utterance': '会不会有一些不想要的念头反复闯进来？',
                        },
                        'patient_answer': {
                            'slot_id': 'intrusive_thoughts',
                            'utterance': '那些念头会自己冒出来，我不想要。',
                        },
                    }
                    ,
                    {
                        'turn': 2,
                        'doctor_action': {
                            'slot_id': 'intrusive_thoughts',
                            'utterance': '这些念头会反复出现吗？',
                        },
                        'patient_answer': {
                            'utterance': '会一直重复。',
                        },
                    },
                ],
            },
            {
                'case_id': 'PIB_0041',
                'dsm_module': 'PD',
                'label': 'BPD',
                'ambiguity': 'ambiguous',
                'asked_slots': ['longstanding_pattern', 'relationship_instability', 'abandonment_sensitivity', 'impairment_social', 'self_harm_ideation'],
                'harm_flags': [],
                'timeout_error': True,
                'last_error': 'timeout',
                'adapter_latency_ms': 4321,
                'termination_reason': 'timeout',
                'case_status': 'completed',
                'parse_retry_count': 0,
                'final_consumable': True,
                'metrics': {
                    'top1_acc': 1.0,
                    'top3_cov': 1.0,
                    'must_ask_hit_rate': 1.0,
                    'svcl_coverage': 1.0,
                },
                'final_output': {
                    'diagnosis_topk': [
                        {'label': 'BPD', 'confidence': 0.72},
                        {'label': 'IED', 'confidence': 0.18},
                    ]
                },
            },
            {
                'case_id': 'PIB_0051',
                'dsm_module': 'OTHER',
                'label': 'OTHER',
                'ambiguity': 'unambiguous',
                'asked_slots': ['onset_time'],
                'harm_flags': ['overconfident_dx'],
                'parse_error': True,
                'termination_reason': 'invalid_slot_id_limit',
                'case_status': 'completed',
                'parse_retry_count': 2,
                'final_consumable': False,
                'invalid_final_reason': 'missing_diagnosis_topk',
                'metrics': {
                    'top1_acc': 0.0,
                    'top3_cov': 0.0,
                    'must_ask_hit_rate': 0.33,
                    'svcl_coverage': 0.33,
                },
                'final_output': {
                    'diagnosis_topk': [{'label': 'OTHER', 'confidence': 1.0}],
                    'justification': [{'claim': '模型未能输出有效 FINAL，默认 OTHER。', 'support_slots': []}],
                    'risk_flags': {'suicide': False, 'violence': False, 'psychosis': False, 'substance': False},
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
                'job_id': 'job_case_projection',
                'job_type': 'run_dynamic',
                'status': 'succeeded' if status == 'completed' else 'running',
                'target_release_id': 'v1.1.0-rc1',
                'started_at': '2026-03-09T00:00:00Z',
                'finished_at': '2026-03-09T00:00:10Z' if status == 'completed' else None,
                'exit_code': 0 if status == 'completed' else None,
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
                'job_id': 'job_case_projection',
                'run_type': 'dynamic',
                'provider': 'baseline',
                'model_name': 'dummy',
                'split_name': 'test',
                'status': status,
                'config_json': '{}',
                'results_root': results_root,
                'metrics_path': f'{results_root}metrics.json',
                'summary_path': f'{results_root}summary.csv',
                'created_at': '2026-03-09T00:00:00Z',
                'started_at': '2026-03-09T00:00:01Z',
                'finished_at': '2026-03-09T00:00:10Z' if status == 'completed' else None,
                'error_summary_json': None,
            },
        )
        return run_id

    def test_get_slices_pending_for_running_run(self) -> None:
        run_id = self._insert_run(status='running')
        status, payload = cases_routes.get_run_slices(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'pending')
        self.assertEqual(payload['slices']['by_module'], [])

    def test_get_slices_ready_with_module_label_ambiguity_and_failure_buckets(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_slices(run_id, repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'ready')
        self.assertEqual(payload['totals']['case_count'], 3)
        self.assertEqual(payload['totals']['completed_case_count'], 3)
        self.assertEqual({row['key'] for row in payload['slices']['by_module']}, {'OCRD', 'OTHER', 'PD'})
        self.assertEqual({row['key'] for row in payload['slices']['by_label']}, {'BPD', 'OCD', 'OTHER'})
        self.assertEqual({row['key'] for row in payload['slices']['by_ambiguity']}, {'ambiguous', 'unambiguous'})
        self.assertEqual({row['key'] for row in payload['slices']['by_required_svcl_domains_count']}, {'3', '4'})
        self.assertEqual({row['key'] for row in payload['slices']['by_termination_reason']}, {'invalid_slot_id_limit', 'repeat_slot', 'timeout'})
        self.assertEqual({row['key'] for row in payload['slices']['by_failure_source']}, {'bridge', 'protocol'})
        self.assertEqual({row['key'] for row in payload['slices']['by_risk_positive']}, {'risk_negative', 'risk_positive'})
        self.assertEqual({row['key'] for row in payload['slices']['by_personality_spectrum']}, {'non_personality_spectrum', 'personality_spectrum'})
        self.assertEqual({row['key'] for row in payload['slices']['by_parse_affected']}, {'parse_affected', 'parse_unaffected'})
        self.assertEqual({row['key'] for row in payload['slices']['by_protocol_clean_only']}, {'affected', 'clean'})
        bucket_counts = {row['key']: row['case_count'] for row in payload['slices']['by_failure_bucket']}
        self.assertEqual(bucket_counts['top1_wrong'], 1)
        self.assertEqual(bucket_counts['must_ask_miss'], 2)
        self.assertEqual(bucket_counts['safety_flagged'], 1)

    def test_get_cases_filters_by_failure_bucket(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_cases(
            run_id,
            {'failure_bucket': 'top1_wrong', 'limit': 50, 'offset': 0},
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'ready')
        self.assertEqual(payload['total'], 1)
        self.assertEqual({row['case_id'] for row in payload['items']}, {'PIB_0001'})

    def test_get_cases_filters_by_failure_source(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_cases(
            run_id,
            {'failure_source': 'protocol', 'limit': 50, 'offset': 0},
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload['total'], 2)
        self.assertEqual({row['case_id'] for row in payload['items']}, {'PIB_0001', 'PIB_0051'})

    def test_get_cases_filters_by_parse_and_protocol_clean(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_cases(
            run_id,
            {'parse_affected': 'parse_affected', 'limit': 50, 'offset': 0},
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 200)
        self.assertEqual({row['case_id'] for row in payload['items']}, {'PIB_0051'})

        status, payload = cases_routes.get_run_cases(
            run_id,
            {'protocol_clean_only': 'clean', 'limit': 50, 'offset': 0},
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 200)
        self.assertEqual({row['case_id'] for row in payload['items']}, {'PIB_0041'})

    def test_get_cases_filters_by_module_and_ambiguity(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_cases(
            run_id,
            {'module': 'OCRD', 'ambiguity': 'ambiguous', 'limit': 50, 'offset': 0},
            repo_root=self.repo_root,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload['total'], 1)
        self.assertEqual(payload['items'][0]['case_id'], 'PIB_0001')

    def test_get_case_detail_returns_case_meta_and_run_output(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_case_detail(run_id, 'PIB_0001', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'ready')
        self.assertEqual(payload['case_meta']['gold_label'], 'OCD')
        self.assertFalse(payload['run_output']['top1_correct'])
        self.assertFalse(payload['run_output']['top3_hit'])
        self.assertIn('must_ask_miss', payload['failure_analysis']['failure_buckets'])
        self.assertEqual(payload['failure_analysis']['failure_source'], 'protocol')
        self.assertEqual(payload['failure_analysis']['failure_sources']['protocol'], 'affected')
        self.assertEqual(payload['run_output']['termination_reason'], 'repeat_slot')
        self.assertEqual(payload['run_output']['repeat_slot_count'], 1)
        self.assertFalse(payload['run_output']['final_consumable'])
        self.assertEqual(payload['run_output']['invalid_final_reason'], 'invalid_final_placeholder')
        self.assertEqual(payload['failure_analysis']['fallback_other_reason'], 'invalid_final_placeholder')
        self.assertIn('repeat_slot', payload['failure_analysis']['protocol_failure_buckets'])
        self.assertIn('invalid_final', payload['failure_analysis']['protocol_failure_buckets'])

    def test_get_case_detail_returns_dynamic_replay_when_turn_logs_exist(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_case_detail(run_id, 'PIB_0001', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertTrue(payload['dynamic_replay']['available'])
        self.assertEqual(payload['dynamic_replay']['turns'][0]['doctor_slot_id'], 'intrusive_thoughts')
        self.assertEqual(payload['dynamic_replay']['turns'][1]['doctor_slot_id'], 'intrusive_thoughts')

    def test_get_case_detail_returns_partial_when_turn_logs_missing(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_case_detail(run_id, 'PIB_0041', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertEqual(payload['state'], 'partial')
        self.assertFalse(payload['dynamic_replay']['available'])
        self.assertIn('Replay unavailable', payload['warnings'])
        self.assertEqual(payload['failure_analysis']['failure_sources']['bridge'], 'affected')
        self.assertTrue(payload['run_output']['timeout_error'])
        self.assertEqual(payload['run_output']['termination_reason'], 'timeout')
        self.assertEqual(payload['run_output']['adapter_latency_ms'], 4321.0)
        self.assertIn('timeout', payload['failure_analysis']['protocol_failure_buckets'])

    def test_get_case_detail_returns_invalid_final_metadata_for_parse_error_case(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_case_detail(run_id, 'PIB_0051', repo_root=self.repo_root)
        self.assertEqual(status, 200)
        self.assertTrue(payload['run_output']['parse_error'])
        self.assertEqual(payload['run_output']['parse_retry_count'], 2)
        self.assertEqual(payload['run_output']['invalid_slot_count'], 1)
        self.assertFalse(payload['run_output']['final_consumable'])
        self.assertEqual(payload['run_output']['invalid_final_reason'], 'missing_diagnosis_topk')
        self.assertEqual(payload['failure_analysis']['fallback_other_reason'], 'parse_error_default_other')
        self.assertIn('parse_error', payload['failure_analysis']['protocol_failure_buckets'])
        self.assertIn('invalid_slot_id', payload['failure_analysis']['protocol_failure_buckets'])
        self.assertIn('fallback_other', payload['failure_analysis']['protocol_failure_buckets'])
        self.assertIsNone(payload['run_output']['adapter_latency_ms'])

    def test_get_case_detail_returns_run_not_ready_for_running_run(self) -> None:
        run_id = self._insert_run(status='running')
        status, payload = cases_routes.get_run_case_detail(run_id, 'PIB_0001', repo_root=self.repo_root)
        self.assertEqual(status, 409)
        self.assertEqual(payload['error']['code'], 'run_not_ready')

    def test_get_case_detail_404_for_unknown_case(self) -> None:
        run_id = self._insert_run()
        status, payload = cases_routes.get_run_case_detail(run_id, 'PIB_9999', repo_root=self.repo_root)
        self.assertEqual(status, 404)
        self.assertEqual(payload['error']['code'], 'case_not_found')
