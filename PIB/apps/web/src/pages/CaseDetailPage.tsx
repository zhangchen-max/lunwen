import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { FailureBucketList } from '../components/FailureBucketList';
import { ReplayTimeline } from '../components/ReplayTimeline';
import { apiErrorCode, apiErrorMessage, fetchRunCaseDetail, type RunCaseDetailResponse } from '../lib/api';

function JsonPreview({ value }: { value: unknown }) {
  return (
    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 }}>
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function AttributionChip({ label, value }: { label: string; value: string }) {
  const palette =
    value === 'bridge'
      ? { background: '#fef2f2', color: '#991b1b', border: '#fecaca' }
      : value === 'protocol'
        ? { background: '#fff7ed', color: '#9a3412', border: '#fdba74' }
        : value === 'capability'
          ? { background: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' }
          : { background: '#ecfdf5', color: '#047857', border: '#a7f3d0' };
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        border: `1px solid ${palette.border}`,
        background: palette.background,
        color: palette.color,
        padding: '6px 10px',
        borderRadius: 999,
        fontSize: 13,
      }}
    >
      <strong>{label}</strong>: {value}
    </span>
  );
}

function FailureBadge({ label, tone }: { label: string; tone: 'warning' | 'danger' | 'neutral' }) {
  const palette =
    tone === 'danger'
      ? { background: '#fef2f2', color: '#991b1b', border: '#fecaca' }
      : tone === 'warning'
        ? { background: '#fff7ed', color: '#9a3412', border: '#fdba74' }
        : { background: '#f3f4f6', color: '#374151', border: '#d1d5db' };
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        border: `1px solid ${palette.border}`,
        background: palette.background,
        color: palette.color,
        padding: '5px 10px',
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {label}
    </span>
  );
}

export function CaseDetailPage() {
  const { runId = '', caseId = '' } = useParams();
  const [detail, setDetail] = useState<RunCaseDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchRunCaseDetail(runId, caseId)
      .then((response) => {
        if (!active) return;
        setDetail(response);
        setError(null);
        setErrorCode(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(apiErrorMessage(err));
        setErrorCode(apiErrorCode(err));
      });
    return () => {
      active = false;
    };
  }, [runId, caseId]);

  return (
    <main style={{ maxWidth: 1080, margin: '0 auto', padding: 24, fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}>
      <p>
        <Link to="/releases">Releases</Link> · <Link to={`/runs/${runId}`}>Run summary</Link> · <Link to={`/runs/${runId}/slices`}>Slices</Link>
      </p>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ marginBottom: 8 }}>Case Detail</h1>
        <p style={{ margin: 0, color: '#4b5563' }}>
          Run {runId} · Case {caseId}
        </p>
      </header>

      {!detail && !error ? <p>Loading case detail...</p> : null}
      {errorCode === 'run_not_ready' ? <p>Run is not ready for case-level projection.</p> : null}
      {errorCode === 'case_not_found' ? <p>Case not found in this run context.</p> : null}
      {error && !['run_not_ready', 'case_not_found'].includes(errorCode ?? '') ? <p role="alert">Failed to load case detail: {error}</p> : null}

      {detail ? (
        <>
          {detail.state === 'partial' ? (
            <div style={{ padding: 12, borderRadius: 8, background: '#fef3c7', color: '#92400e', marginBottom: 16 }}>
              {detail.dynamic_replay.available
                ? 'Partial case projection: some case-level outputs are unavailable.'
                : 'Partial case projection: replay data is missing for this run.'}
            </div>
          ) : null}
          <section style={{ marginTop: 24 }}>
            <h2>Case header</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }}>
              <div><strong>Module</strong><div>{detail.case_meta.dsm_module}</div></div>
              <div><strong>Label</strong><div>{detail.case_meta.label}</div></div>
              <div><strong>Ambiguity</strong><div>{detail.case_meta.ambiguity}</div></div>
              <div><strong>Gold</strong><div>{detail.case_meta.gold_label}</div></div>
            </div>
          </section>

          <section style={{ marginTop: 24, display: 'grid', gap: 16 }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 16,
                alignItems: 'start',
              }}
            >
              <article style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, background: '#fff' }}>
                <h2 style={{ marginTop: 0 }}>Case meta</h2>
                <div style={{ display: 'grid', gap: 12 }}>
                  <div><strong>Minimal CC</strong><div>{detail.case_meta.minimal_cc}</div></div>
                  <div><strong>Required SVCL domains</strong><div>{detail.case_meta.required_svcl_domains.join(', ') || '—'}</div></div>
                  <div><strong>Must-ask slots</strong><div>{detail.case_meta.must_ask_slots.join(', ') || '—'}</div></div>
                  <div><strong>Gold DDX Top-5</strong><div>{detail.case_meta.gold_ddx_top5.join(', ') || '—'}</div></div>
                  <div><strong>Risk flags</strong><JsonPreview value={detail.case_meta.risk_flags} /></div>
                </div>
              </article>

              <article style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, background: '#fff' }}>
                <h2 style={{ marginTop: 0 }}>Run output</h2>
                {detail.run_output ? (
                  <div style={{ display: 'grid', gap: 12 }}>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {detail.run_output.parse_error ? <FailureBadge label="Parse failure" tone="danger" /> : null}
                      {(detail.run_output.repeat_slot_count ?? 0) > 0 ? <FailureBadge label="Repeat slot" tone="warning" /> : null}
                      {detail.run_output.final_consumable === false ? <FailureBadge label="Invalid final" tone="danger" /> : null}
                      {detail.run_output.timeout_error ? <FailureBadge label="Timeout" tone="danger" /> : null}
                    </div>
                    <div><strong>Pred top-k</strong><JsonPreview value={detail.run_output.pred_topk} /></div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                      <div><strong>Top-1 correct</strong><div>{String(detail.run_output.top1_correct)}</div></div>
                      <div><strong>Top-3 hit</strong><div>{String(detail.run_output.top3_hit)}</div></div>
                      <div><strong>Must-ask hit rate</strong><div>{detail.run_output.must_ask_hit_rate ?? '—'}</div></div>
                      <div><strong>SVCL coverage</strong><div>{detail.run_output.svcl_coverage ?? '—'}</div></div>
                      <div><strong>Action schema valid</strong><div>{detail.run_output.action_schema_valid === undefined ? '—' : String(detail.run_output.action_schema_valid)}</div></div>
                      <div><strong>Parse retries</strong><div>{detail.run_output.parse_retry_count ?? '—'}</div></div>
                      <div><strong>Repeat slot count</strong><div>{detail.run_output.repeat_slot_count ?? '—'}</div></div>
                      <div><strong>Invalid slot count</strong><div>{detail.run_output.invalid_slot_count ?? '—'}</div></div>
                      <div><strong>Adapter latency</strong><div>{detail.run_output.adapter_latency_ms === null || detail.run_output.adapter_latency_ms === undefined ? '—' : `${detail.run_output.adapter_latency_ms} ms`}</div></div>
                    </div>
                    <div style={{ display: 'grid', gap: 6, padding: 12, borderRadius: 8, background: '#f9fafb', border: '1px solid #e5e7eb' }}>
                      <div><strong>FINAL status</strong></div>
                      <div>{detail.run_output.final_consumable === undefined ? '—' : detail.run_output.final_consumable ? 'Consumable' : 'Invalid'}</div>
                      <div><strong>Termination reason</strong>: {detail.run_output.termination_reason ?? '—'}</div>
                    </div>
                    <div><strong>Safety flags</strong><div>{detail.run_output.safety_flags.join(', ') || '—'}</div></div>
                    {detail.dynamic_replay.final_output ? (
                      <details>
                        <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Raw final preview</summary>
                        <div style={{ marginTop: 8 }}>
                          <JsonPreview value={detail.dynamic_replay.final_output} />
                        </div>
                      </details>
                    ) : null}
                  </div>
                ) : (
                  <p style={{ color: '#6b7280', marginBottom: 0 }}>Run output unavailable.</p>
                )}
              </article>

              <article style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, background: '#fff' }}>
                <h2 style={{ marginTop: 0 }}>Failure analysis</h2>
                <FailureBucketList buckets={detail.failure_analysis.failure_buckets} />
                {detail.failure_analysis.failure_sources ? (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                    <AttributionChip label="Bridge" value={detail.failure_analysis.failure_sources.bridge} />
                    <AttributionChip label="Protocol" value={detail.failure_analysis.failure_sources.protocol} />
                    <AttributionChip label="Capability" value={detail.failure_analysis.failure_sources.capability} />
                  </div>
                ) : detail.failure_analysis.failure_source ? (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                    <AttributionChip label="Primary failure source" value={detail.failure_analysis.failure_source} />
                  </div>
                ) : null}
                <div style={{ display: 'grid', gap: 12 }}>
                  <div><strong>Missing must-ask slots</strong><div>{detail.failure_analysis.missing_must_ask_slots.join(', ') || '—'}</div></div>
                  <div><strong>Missing SVCL domains</strong><div>{detail.failure_analysis.missing_svcl_domains.join(', ') || '—'}</div></div>
                  <div><strong>Fallback reason</strong><div>{detail.failure_analysis.fallback_other_reason && detail.failure_analysis.fallback_other_reason !== 'none' ? detail.failure_analysis.fallback_other_reason : '—'}</div></div>
                  {detail.failure_analysis.warnings.length > 0 ? <div><strong>Warnings</strong><div>{detail.failure_analysis.warnings.join('; ')}</div></div> : null}
                </div>
              </article>
            </div>

            <ReplayTimeline
              available={detail.dynamic_replay.available}
              turns={detail.dynamic_replay.turns}
              finalOutput={detail.dynamic_replay.final_output}
            />
          </section>
        </>
      ) : null}
    </main>
  );
}
