export type ReleaseListItem = {
  release_id: string;
  label: string;
  status: string;
  manifest_path: string;
  bundle_path: string | null;
  benchmark_version: string | null;
  dataset_version?: string | null;
  scoring_policy_version: string | null;
  dataset_hash_sha256: string | null;
  scoring_hash_sha256: string | null;
  cases_sha256: string | null;
  rubrics_sha256: string | null;
  splits_sha256: string | null;
  baseline_reports: string[];
  audit_reports: string[];
  deprecated_results_path: string | null;
  last_validated_job_id?: string | null;
  last_frozen_job_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ReleaseListResponse = {
  items: ReleaseListItem[];
};

export type ReleaseDetailResponse = {
  release_id: string;
  label: string;
  status?: string;
  state?: 'success' | 'partial';
  partial?: boolean;
  registry?: {
    last_validated_job_id?: string | null;
    last_frozen_job_id?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
  };
  manifest: {
    benchmark_version?: string | null;
    dataset_version?: string | null;
    scoring_policy_version?: string | null;
    no_oracle_policy_version?: string | null;
    slot_count?: number | null;
    dynamic_max_turns?: number | null;
    os_ocrd_subtypes?: string[] | null;
    dataset_hash_sha256?: string | null;
    scoring_hash_sha256?: string | null;
    cases_sha256?: string | null;
    rubrics_sha256?: string | null;
    splits_sha256?: string | null;
  };
  bundle: {
    path: string | null;
    files: Array<{ name: string; path: string; size: number }>;
  };
  reports: {
    pure_baselines: string | null;
    guided_llm_baselines: string | null;
    deprecated_results: string | null;
  };
  audits: {
    no_oracle: string | null;
    text_contamination: string | null;
    other: string[];
  };
};

export type RunOptionsResponse = {
  releases: Array<{ release_id: string; label: string }>;
  run_types: Array<'static' | 'dynamic'>;
  providers: Array<{ id: string; label: string }>;
  default_split: string;
};

export type CreateRunRequest = {
  release_id: string;
  run_type: 'static' | 'dynamic';
  provider: string;
  model_name: string;
  split_name: string;
  notes?: string;
};

export type CreateRunResponse = {
  run_id: string;
  job_id: string;
  status: 'queued';
  redirect_url: string;
};

export type RunStatusResponse = {
  run_id: string;
  release_id: string;
  job_id: string;
  run_type: 'static' | 'dynamic';
  provider: string;
  model_name: string;
  split_name: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  results_root: string | null;
  metrics_path: string | null;
  summary_path: string | null;
  error_summary: {
    message: string;
    stdout_path: string | null;
    stderr_path: string | null;
  } | null;
};

export type RunSummaryResponse = {
  run_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  state: 'pending' | 'ready' | 'partial' | 'failed';
  overall_metrics: Array<{
    key: string;
    label: string;
    value: number;
    unit?: string | null;
  }>;
  process_score?: Array<{
    key: string;
    label: string;
    value: number;
    unit?: string | null;
  }>;
  compliance_score?: Array<{
    key: string;
    label: string;
    value: number;
    unit?: string | null;
  }>;
  final_diagnosis_score?: Array<{
    key: string;
    label: string;
    value: number;
    unit?: string | null;
  }>;
  baseline_compare: {
    metrics: Array<{
      metric_key: string;
      current_value: number | null;
      pure_baseline_value: number | null;
      guided_baseline_value: number | null;
      delta_vs_pure: number | null;
      delta_vs_guided: number | null;
    }>;
    source_tables: {
      pure_baselines_path: string | null;
      guided_llm_baselines_path: string | null;
      deprecated_results_path: string | null;
    };
    warnings: string[];
  } | null;
  failure_attribution?: {
    execution_success_rate?: number | null;
    timeout_count?: number | null;
    bridge_failure_count?: number | null;
    parse_retry_count?: number | null;
    termination_reason_histogram?: Record<string, number>;
    failure_source_counts?: Record<string, number>;
    bridge?: {
      affected: boolean;
      timeout: boolean;
      provider_unavailable: boolean;
      transport_failure: boolean;
      message: string | null;
    };
    protocol_failure_count?: number | null;
    capability_failure_count?: number | null;
  } | null;
  supplemental?: {
    oracle_final_metrics: Array<{
      key: string;
      label: string;
      value: number;
      unit?: string | null;
    }>;
    available_case_count?: number;
    warnings: string[];
  } | null;
  summary_paths: {
    metrics_path: string | null;
    summary_path: string | null;
  };
  warnings: string[];
  error_summary?: RunStatusResponse['error_summary'];
};

export type RunArtifactsResponse = {
  run_id: string;
  results_root: string | null;
  items: Array<{
    kind: string;
    label: string;
    path: string;
    size_bytes: number;
    exists: boolean;
  }>;
};

export type RunSlicesResponse = {
  run_id: string;
  status?: 'queued' | 'running' | 'completed' | 'failed';
  state: 'pending' | 'ready' | 'partial' | 'failed';
  totals: {
    case_count: number;
    completed_case_count: number;
  };
  slices: {
    by_module: SliceRow[];
    by_label: SliceRow[];
    by_ambiguity: SliceRow[];
    by_required_svcl_domains_count: SliceRow[];
    by_failure_source: SliceRow[];
    by_failure_bucket: FailureBucketRow[];
    by_risk_positive: SliceRow[];
    by_personality_spectrum: SliceRow[];
    by_timeout_affected: SliceRow[];
    by_parse_affected: SliceRow[];
    by_protocol_clean_only: SliceRow[];
  };
  warnings: string[];
  error_summary?: RunStatusResponse['error_summary'];
};

export type SliceRow = {
  key: string;
  label: string;
  case_count: number;
  metrics?: Record<string, number | null>;
};

export type FailureBucketRow = {
  key: string;
  label: string;
  case_count: number;
};

export type RunCasesResponse = {
  run_id: string;
  state: 'pending' | 'ready' | 'partial' | 'failed';
  filters: {
    module: string | null;
    label: string | null;
    ambiguity: string | null;
    required_svcl_domains_count: string | number | null;
    failure_bucket: string | null;
    risk_positive?: string | null;
    personality_spectrum?: string | null;
    timeout_affected?: string | null;
    parse_affected?: string | null;
    protocol_clean_only?: string | null;
    failure_source?: string | null;
  };
  total: number;
  items: Array<{
    case_id: string;
    dsm_module: string;
    label: string;
    ambiguity: string;
    required_svcl_domains_count: number | null;
    pred_top1: string | null;
    gold_label: string;
    top1_correct: boolean;
    top3_hit: boolean;
    must_ask_hit_rate: number | null;
    svcl_coverage: number | null;
    failure_buckets: string[];
    failure_source?: string | null;
    risk_flags: {
      suicide: boolean;
      violence: boolean;
      psychosis: boolean;
      substance: boolean;
    };
  }>;
  warnings: string[];
  error_summary?: RunStatusResponse['error_summary'];
};

export type RunCaseDetailResponse = {
  run_id: string;
  case_id: string;
  state: 'ready' | 'partial';
  case_meta: {
    dsm_module: string;
    label: string;
    ambiguity: string;
    required_svcl_domains: string[];
    must_ask_slots: string[];
    gold_label: string;
    gold_ddx_top5: string[];
    risk_flags: {
      suicide: boolean;
      violence: boolean;
      psychosis: boolean;
      substance: boolean;
    };
    minimal_cc: string;
  };
  run_output: {
    pred_topk: Array<{ label: string; confidence: number | null }>;
    top1_correct: boolean;
    top3_hit: boolean;
    must_ask_hit_rate: number | null;
    svcl_coverage: number | null;
    safety_flags: string[];
    action_schema_valid?: boolean;
    parse_error?: boolean;
    parse_retry_count?: number;
    repeat_slot_count?: number;
    invalid_slot_count?: number;
    final_consumable?: boolean;
    termination_reason?: string | null;
    adapter_latency_ms?: number | null;
    timeout_error?: boolean;
  } | null;
  failure_analysis: {
    failure_buckets: string[];
    failure_source?: string | null;
    failure_sources?: {
      bridge: string;
      protocol: string;
      capability: string;
    };
    missing_must_ask_slots: string[];
    missing_svcl_domains: string[];
    fallback_other_reason?: string;
    warnings: string[];
  };
  dynamic_replay: {
    available: boolean;
    turns: Array<{
      t: number | null;
      doctor_slot_id: string | null;
      doctor_utterance: string | null;
      patient_utterance: string | null;
    }>;
    final_output: Record<string, unknown> | null;
  };
  warnings: string[];
};

export type JobResponse = {
  job_id: string;
  job_type: 'validate_current' | 'freeze_current';
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  target_release_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  stdout_path: string | null;
  stderr_path: string | null;
  result_json_path: string | null;
  error_summary_json: string | null;
  job_dir: string;
  result: {
    job_id: string;
    job_type: string;
    status: string;
    exit_code: number | null;
    structured_errors: Array<{
      scope: string;
      case_id: string | null;
      field: string;
      message: string;
    }>;
    raw_summary: {
      stdout_tail: string;
      stderr_tail: string;
    };
    target_release_id?: string;
  } | null;
  structured_errors: Array<{
    scope: string;
    case_id: string | null;
    field: string;
    message: string;
  }>;
};

export type ApiError = {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown> | null;
    retryable: boolean;
  };
};

const MOCK_RELEASE_LIST = '/releases.list.json';
const MOCK_RELEASE_DETAIL = '/releases.detail.rc1.json';

async function readJson<T>(input: RequestInfo): Promise<T> {
  const response = await fetch(input);
  const payload = (await response.json()) as T | ApiError;
  if (!response.ok) {
    throw payload;
  }
  return payload as T;
}

function useMocks(): boolean {
  return new URLSearchParams(window.location.search).get('mock') === '1';
}

export async function fetchReleases(): Promise<ReleaseListResponse> {
  return useMocks() ? readJson<ReleaseListResponse>(MOCK_RELEASE_LIST) : readJson<ReleaseListResponse>('/api/releases');
}

export async function fetchReleaseDetail(releaseId: string): Promise<ReleaseDetailResponse> {
  if (useMocks()) {
    return readJson<ReleaseDetailResponse>(MOCK_RELEASE_DETAIL);
  }
  return readJson<ReleaseDetailResponse>(`/api/releases/${releaseId}`);
}

function syntheticJob(jobType: JobResponse['job_type']): JobResponse {
  const jobId = `job_mock_${jobType}`;
  return {
    job_id: jobId,
    job_type: jobType,
    status: 'succeeded',
    target_release_id: 'v1.1.0-rc1',
    started_at: null,
    finished_at: null,
    exit_code: 0,
    stdout_path: null,
    stderr_path: null,
    result_json_path: null,
    error_summary_json: null,
    job_dir: `artifacts/jobs/${jobId}`,
    result: {
      job_id: jobId,
      job_type: jobType,
      status: 'succeeded',
      exit_code: 0,
      structured_errors: [],
      raw_summary: {
        stdout_tail: '',
        stderr_tail: '',
      },
      target_release_id: 'v1.1.0-rc1',
    },
    structured_errors: [],
  };
}

function syntheticRunOptions(): RunOptionsResponse {
  return {
    releases: [{ release_id: 'v1.1.0-rc1', label: 'PIB Benchmark v1.1.0-rc1' }],
    run_types: ['static', 'dynamic'],
    providers: [
      { id: 'openai', label: 'OpenAI' },
      { id: 'anthropic', label: 'Anthropic' },
      { id: 'local', label: 'Local' },
      { id: 'baseline', label: 'Baseline' },
    ],
    default_split: 'test',
  };
}

function syntheticRunStatus(runId: string): RunStatusResponse {
  return {
    run_id: runId,
    release_id: 'v1.1.0-rc1',
    job_id: 'job_mock_run',
    run_type: 'dynamic',
    provider: 'baseline',
    model_name: 'dummy',
    split_name: 'test',
    status: 'completed',
    created_at: '2026-03-09T00:00:00Z',
    started_at: '2026-03-09T00:00:01Z',
    finished_at: '2026-03-09T00:00:02Z',
    results_root: 'results/dynamic/dummy/run_mock/run_001/',
    metrics_path: 'results/dynamic/dummy/run_mock/run_001/metrics.json',
    summary_path: 'results/dynamic/dummy/run_mock/run_001/summary.csv',
    error_summary: null,
  };
}

function syntheticRunSummary(runId: string): RunSummaryResponse {
  return {
    run_id: runId,
    status: 'completed',
    state: 'ready',
    overall_metrics: [
      { key: 'top1_acc', label: 'Top-1 Accuracy', value: 0.72, unit: 'ratio' },
      { key: 'top3_cov', label: 'Top-3 Coverage', value: 0.88, unit: 'ratio' },
    ],
    process_score: [
      { key: 'must_ask_hit_rate', label: 'Must-Ask Hit Rate', value: 0.75, unit: 'ratio' },
      { key: 'svcl_coverage', label: 'SVCL Coverage', value: 0.75, unit: 'ratio' },
      { key: 'turns', label: 'Turns', value: 5, unit: 'count' },
    ],
    compliance_score: [
      { key: 'execution_success_rate', label: 'Execution Success Rate', value: 1, unit: 'ratio' },
      { key: 'action_schema_valid_rate', label: 'Action Schema Valid Rate', value: 0.67, unit: 'ratio' },
      { key: 'final_consumable_rate', label: 'Final Consumable Rate', value: 0.67, unit: 'ratio' },
      { key: 'parse_retry_count', label: 'Parse Retry Count', value: 1, unit: 'count' },
    ],
    final_diagnosis_score: [
      { key: 'top1_acc', label: 'Top-1 Accuracy', value: 0.72, unit: 'ratio' },
      { key: 'top3_cov', label: 'Top-3 Coverage', value: 0.88, unit: 'ratio' },
    ],
    baseline_compare: {
      metrics: [
        {
          metric_key: 'top1_acc',
          current_value: 0.72,
          pure_baseline_value: 0.61,
          guided_baseline_value: null,
          delta_vs_pure: 0.11,
          delta_vs_guided: null,
        },
      ],
      source_tables: {
        pure_baselines_path: 'results/reports/pure_baselines.csv',
        guided_llm_baselines_path: 'results/reports/guided_llm_baselines.csv',
        deprecated_results_path: 'results/reports/deprecated_results.json',
      },
      warnings: [],
    },
    failure_attribution: {
      execution_success_rate: 1,
      timeout_count: 0,
      bridge_failure_count: 0,
      parse_retry_count: 1,
      termination_reason_histogram: { final: 2, repeat_slot: 1 },
      failure_source_counts: { bridge: 0, protocol: 1, capability: 1, clean: 1 },
      bridge: { affected: false, timeout: false, provider_unavailable: false, transport_failure: false, message: null },
      protocol_failure_count: 1,
      capability_failure_count: 1,
    },
    supplemental: {
      oracle_final_metrics: [
        { key: 'oracle_final_top1_acc', label: 'Oracle-Final Top-1 Accuracy', value: 0.8, unit: 'ratio' },
      ],
      available_case_count: 1,
      warnings: [],
    },
    summary_paths: {
      metrics_path: 'results/dynamic/dummy/run_mock/run_001/metrics.json',
      summary_path: 'results/dynamic/dummy/run_mock/run_001/summary.csv',
    },
    warnings: [],
  };
}

function syntheticRunArtifacts(runId: string): RunArtifactsResponse {
  return {
    run_id: runId,
    results_root: 'results/dynamic/dummy/run_mock/run_001/',
    items: [
      {
        kind: 'metrics',
        label: 'metrics.json',
        path: 'results/dynamic/dummy/run_mock/run_001/metrics.json',
        size_bytes: 1234,
        exists: true,
      },
      {
        kind: 'summary',
        label: 'summary.csv',
        path: 'results/dynamic/dummy/run_mock/run_001/summary.csv',
        size_bytes: 456,
        exists: true,
      },
    ],
  };
}

function syntheticRunSlices(runId: string): RunSlicesResponse {
  return {
    run_id: runId,
    status: 'completed',
    state: 'ready',
    totals: {
      case_count: 3,
      completed_case_count: 3,
    },
    slices: {
      by_module: [
        { key: 'OCRD', label: 'OCRD', case_count: 1, metrics: { top1_acc: 0, top3_cov: 1, must_ask_hit_rate: 0.75, svcl_coverage: 0.75 } },
        { key: 'PD', label: 'PD', case_count: 1, metrics: { top1_acc: 1, top3_cov: 1, must_ask_hit_rate: 1, svcl_coverage: 1 } },
      ],
      by_label: [
        { key: 'OCD', label: 'OCD', case_count: 1, metrics: { top1_acc: 0 } },
        { key: 'BPD', label: 'BPD', case_count: 1, metrics: { top1_acc: 1 } },
      ],
      by_ambiguity: [
        { key: 'ambiguous', label: 'Ambiguous', case_count: 2, metrics: { top1_acc: 0.5 } },
        { key: 'unambiguous', label: 'Unambiguous', case_count: 1, metrics: { top1_acc: 0 } },
      ],
      by_required_svcl_domains_count: [
        { key: '3', label: '3 domains', case_count: 1, metrics: { top1_acc: 0 } },
        { key: '4', label: '4 domains', case_count: 2, metrics: { top1_acc: 0.5 } },
      ],
      by_failure_source: [
        { key: 'protocol', label: 'Protocol', case_count: 1, metrics: { top1_acc: 0 } },
        { key: 'capability', label: 'Capability', case_count: 1, metrics: { top1_acc: 0 } },
        { key: 'clean', label: 'Clean', case_count: 1, metrics: { top1_acc: 1 } },
      ],
      by_failure_bucket: [
        { key: 'top1_wrong', label: 'top1_wrong', case_count: 2 },
        { key: 'must_ask_miss', label: 'must_ask_miss', case_count: 1 },
      ],
      by_risk_positive: [
        { key: 'risk_negative', label: 'risk negative', case_count: 2, metrics: { top1_acc: 0 } },
        { key: 'risk_positive', label: 'risk positive', case_count: 1, metrics: { top1_acc: 1 } },
      ],
      by_personality_spectrum: [
        { key: 'personality_spectrum', label: 'personality spectrum', case_count: 1, metrics: { top1_acc: 1 } },
        { key: 'non_personality_spectrum', label: 'non personality spectrum', case_count: 2, metrics: { top1_acc: 0 } },
      ],
      by_timeout_affected: [
        { key: 'timeout_unaffected', label: 'timeout unaffected', case_count: 3, metrics: { top1_acc: 0.33 } },
      ],
      by_parse_affected: [
        { key: 'parse_affected', label: 'parse affected', case_count: 1, metrics: { top1_acc: 0 } },
        { key: 'parse_unaffected', label: 'parse unaffected', case_count: 2, metrics: { top1_acc: 0.5 } },
      ],
      by_protocol_clean_only: [
        { key: 'clean', label: 'clean', case_count: 2, metrics: { top1_acc: 0.5 } },
        { key: 'affected', label: 'affected', case_count: 1, metrics: { top1_acc: 0 } },
      ],
    },
    warnings: [],
  };
}

function syntheticRunCases(runId: string): RunCasesResponse {
  return {
    run_id: runId,
    state: 'ready',
    filters: {
      module: null,
      label: null,
      ambiguity: null,
      required_svcl_domains_count: null,
      failure_bucket: null,
      risk_positive: null,
      personality_spectrum: null,
      timeout_affected: null,
      parse_affected: null,
      protocol_clean_only: null,
      failure_source: null,
    },
    total: 2,
    items: [
      {
        case_id: 'PIB_0001',
        dsm_module: 'OCRD',
        label: 'OCD',
        ambiguity: 'ambiguous',
        required_svcl_domains_count: 4,
        pred_top1: 'BDD',
        gold_label: 'OCD',
        top1_correct: false,
        top3_hit: true,
        must_ask_hit_rate: 0.75,
        svcl_coverage: 0.75,
        failure_buckets: ['top1_wrong', 'must_ask_miss'],
        failure_source: 'capability',
        risk_flags: { suicide: false, violence: false, psychosis: false, substance: false },
      },
      {
        case_id: 'PIB_0041',
        dsm_module: 'PD',
        label: 'BPD',
        ambiguity: 'ambiguous',
        required_svcl_domains_count: 4,
        pred_top1: 'BPD',
        gold_label: 'BPD',
        top1_correct: true,
        top3_hit: true,
        must_ask_hit_rate: 1,
        svcl_coverage: 1,
        failure_buckets: [],
        failure_source: 'clean',
        risk_flags: { suicide: true, violence: false, psychosis: false, substance: false },
      },
    ],
    warnings: [],
  };
}

function syntheticRunCaseDetail(runId: string, caseId: string): RunCaseDetailResponse {
  return {
    run_id: runId,
    case_id: caseId,
    state: caseId === 'PIB_0041' ? 'partial' : 'ready',
    case_meta: {
      dsm_module: caseId === 'PIB_0041' ? 'PD' : 'OCRD',
      label: caseId === 'PIB_0041' ? 'BPD' : 'OCD',
      ambiguity: 'ambiguous',
      required_svcl_domains: ['symptom_profile', 'cog_emotion_process'],
      must_ask_slots: ['onset_time', 'intrusive_thoughts'],
      gold_label: caseId === 'PIB_0041' ? 'BPD' : 'OCD',
      gold_ddx_top5: caseId === 'PIB_0041' ? ['BPD', 'IED', 'PMDD', 'ADJ', 'OTHER'] : ['OCD', 'BDD', 'OCPD', 'SSD', 'OTHER'],
      risk_flags: { suicide: caseId === 'PIB_0041', violence: false, psychosis: false, substance: false },
      minimal_cc: caseId === 'PIB_0041' ? '关系一乱我就会想伤害自己。' : '最近总怕手被弄脏。',
    },
    run_output: {
      pred_topk: caseId === 'PIB_0041' ? [{ label: 'BPD', confidence: 0.72 }] : [{ label: 'BDD', confidence: 0.41 }, { label: 'OCD', confidence: 0.33 }],
      top1_correct: caseId === 'PIB_0041',
      top3_hit: true,
      must_ask_hit_rate: caseId === 'PIB_0041' ? 1 : 0.75,
      svcl_coverage: caseId === 'PIB_0041' ? 1 : 0.75,
      safety_flags: [],
      action_schema_valid: caseId !== 'PIB_0041',
      final_consumable: caseId !== 'PIB_0041',
      termination_reason: caseId === 'PIB_0041' ? 'repeat_slot' : 'final',
    },
    failure_analysis: {
      failure_buckets: caseId === 'PIB_0041' ? [] : ['top1_wrong', 'must_ask_miss'],
      failure_source: caseId === 'PIB_0041' ? 'protocol' : 'capability',
      failure_sources: {
        bridge: 'clean',
        protocol: caseId === 'PIB_0041' ? 'affected' : 'clean',
        capability: caseId === 'PIB_0041' ? 'not_evaluable' : 'affected',
      },
      missing_must_ask_slots: caseId === 'PIB_0041' ? [] : ['impairment_school'],
      missing_svcl_domains: caseId === 'PIB_0041' ? [] : ['functional_impairment'],
      warnings: caseId === 'PIB_0041' ? ['Replay unavailable'] : [],
    },
    dynamic_replay: {
      available: caseId !== 'PIB_0041',
      turns: caseId === 'PIB_0041' ? [] : [
        {
          t: 1,
          doctor_slot_id: 'intrusive_thoughts',
          doctor_utterance: '会不会有一些不想要的念头反复闯进来？',
          patient_utterance: '那些念头会自己冒出来，我不想要。',
        },
      ],
      final_output: {},
    },
    warnings: caseId === 'PIB_0041' ? ['Replay unavailable'] : [],
  };
}

async function postJson<T>(input: RequestInfo): Promise<T> {
  return postJsonBody<T>(input, {});
}

async function postJsonBody<T>(input: RequestInfo, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(input, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const payload = (await response.json()) as T | ApiError;
  if (!response.ok) {
    throw payload;
  }
  return payload as T;
}

export async function createValidateCurrentJob(): Promise<JobResponse> {
  return useMocks() ? syntheticJob('validate_current') : postJson<JobResponse>('/api/releases/validate-current');
}

export async function createFreezeCurrentJob(): Promise<JobResponse> {
  return useMocks() ? syntheticJob('freeze_current') : postJson<JobResponse>('/api/releases/freeze-current');
}

export async function fetchJob(jobId: string): Promise<JobResponse> {
  return useMocks() ? syntheticJob('validate_current') : readJson<JobResponse>(`/api/jobs/${jobId}`);
}

export async function fetchRunOptions(): Promise<RunOptionsResponse> {
  return useMocks() ? syntheticRunOptions() : readJson<RunOptionsResponse>('/api/runs/options');
}

export async function createRun(payload: CreateRunRequest): Promise<CreateRunResponse> {
  return useMocks()
    ? {
        run_id: 'run_mock_dynamic',
        job_id: 'job_mock_run',
        status: 'queued',
        redirect_url: '/runs/run_mock_dynamic',
      }
    : postJsonBody<CreateRunResponse>('/api/runs', payload);
}

export async function fetchRun(runId: string): Promise<RunStatusResponse> {
  return useMocks() ? syntheticRunStatus(runId) : readJson<RunStatusResponse>(`/api/runs/${runId}`);
}

export async function fetchRunSummary(runId: string): Promise<RunSummaryResponse> {
  return useMocks() ? syntheticRunSummary(runId) : readJson<RunSummaryResponse>(`/api/runs/${runId}/summary`);
}

export async function fetchRunArtifacts(runId: string): Promise<RunArtifactsResponse> {
  return useMocks() ? syntheticRunArtifacts(runId) : readJson<RunArtifactsResponse>(`/api/runs/${runId}/artifacts`);
}

export async function fetchRunSlices(runId: string): Promise<RunSlicesResponse> {
  return useMocks() ? syntheticRunSlices(runId) : readJson<RunSlicesResponse>(`/api/runs/${runId}/slices`);
}

export async function fetchRunCases(
  runId: string,
  filters: Partial<RunCasesResponse['filters']> & { limit?: number; offset?: number },
): Promise<RunCasesResponse> {
  if (useMocks()) {
    return syntheticRunCases(runId);
  }
  const params = new URLSearchParams();
  if (filters.module) params.set('module', filters.module);
  if (filters.label) params.set('label', filters.label);
  if (filters.ambiguity) params.set('ambiguity', filters.ambiguity);
  if (filters.required_svcl_domains_count !== null && filters.required_svcl_domains_count !== undefined) {
    params.set('required_svcl_domains_count', String(filters.required_svcl_domains_count));
  }
  if (filters.failure_bucket) params.set('failure_bucket', filters.failure_bucket);
  if (filters.risk_positive) params.set('risk_positive', filters.risk_positive);
  if (filters.personality_spectrum) params.set('personality_spectrum', filters.personality_spectrum);
  if (filters.timeout_affected) params.set('timeout_affected', filters.timeout_affected);
  if (filters.parse_affected) params.set('parse_affected', filters.parse_affected);
  if (filters.protocol_clean_only) params.set('protocol_clean_only', filters.protocol_clean_only);
  if (filters.failure_source) params.set('failure_source', filters.failure_source);
  if (filters.limit !== undefined) params.set('limit', String(filters.limit));
  if (filters.offset !== undefined) params.set('offset', String(filters.offset));
  return readJson<RunCasesResponse>(`/api/runs/${runId}/cases?${params.toString()}`);
}

export async function fetchRunCaseDetail(runId: string, caseId: string): Promise<RunCaseDetailResponse> {
  return useMocks() ? syntheticRunCaseDetail(runId, caseId) : readJson<RunCaseDetailResponse>(`/api/runs/${runId}/cases/${caseId}`);
}

export function artifactDownloadUrl(runId: string, path: string): string {
  return `/api/runs/${runId}/artifacts/download?path=${encodeURIComponent(path)}`;
}

export function apiErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error && 'error' in error) {
    const apiError = error as ApiError;
    return apiError.error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unknown error';
}

export function apiErrorCode(error: unknown): string | null {
  if (typeof error === 'object' && error && 'error' in error) {
    return (error as ApiError).error.code;
  }
  return null;
}
