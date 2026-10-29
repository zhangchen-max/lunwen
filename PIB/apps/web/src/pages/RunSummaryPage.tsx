import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArtifactDownloads } from '../components/ArtifactDownloads';
import { BaselineCompareTable } from '../components/BaselineCompareTable';
import { MetricCard } from '../components/MetricCard';
import { RunStatusPanel } from '../components/RunStatusPanel';
import { apiErrorMessage, fetchRun, fetchRunArtifacts, fetchRunSummary, type RunArtifactsResponse, type RunStatusResponse, type RunSummaryResponse } from '../lib/api';

function MetricSection({ title, metrics }: { title: string; metrics?: RunSummaryResponse['overall_metrics'] }) {
  if (!metrics || metrics.length === 0) {
    return null;
  }
  return (
    <section style={{ marginTop: 24 }}>
      <h2>{title}</h2>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {metrics.map((metric) => (
          <MetricCard key={`${title}-${metric.key}`} label={metric.label} value={metric.value} unit={metric.unit} />
        ))}
      </div>
    </section>
  );
}

function AttributionPanel({ summary }: { summary: RunSummaryResponse }) {
  if (!summary.failure_attribution) {
    return null;
  }
  const attribution = summary.failure_attribution;
  const sourceCounts = attribution.failure_source_counts ?? {};
  const terminationHistogram = attribution.termination_reason_histogram ?? {};
  return (
    <section style={{ marginTop: 24, display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
      <article style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, background: '#fff' }}>
        <h2 style={{ marginTop: 0 }}>Failure attribution</h2>
        <div style={{ display: 'grid', gap: 8 }}>
          <div><strong>Execution success</strong>: {attribution.execution_success_rate ?? '—'}</div>
          <div><strong>Bridge failures</strong>: {attribution.bridge_failure_count ?? '—'}</div>
          <div><strong>Protocol failures</strong>: {attribution.protocol_failure_count ?? '—'}</div>
          <div><strong>Capability failures</strong>: {attribution.capability_failure_count ?? '—'}</div>
          <div><strong>Parse retries</strong>: {attribution.parse_retry_count ?? '—'}</div>
          <div><strong>Timeout count</strong>: {attribution.timeout_count ?? '—'}</div>
        </div>
      </article>
      <article style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, background: '#fff' }}>
        <h2 style={{ marginTop: 0 }}>Failure sources</h2>
        {Object.keys(sourceCounts).length === 0 ? (
          <p style={{ color: '#6b7280', marginBottom: 0 }}>No failure-source counts.</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {Object.entries(sourceCounts).map(([key, value]) => (
              <li key={key}>
                <strong>{key}</strong>: {value}
              </li>
            ))}
          </ul>
        )}
      </article>
      <article style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, background: '#fff' }}>
        <h2 style={{ marginTop: 0 }}>Termination reasons</h2>
        {Object.keys(terminationHistogram).length === 0 ? (
          <p style={{ color: '#6b7280', marginBottom: 0 }}>No termination anomalies recorded.</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {Object.entries(terminationHistogram).map(([key, value]) => (
              <li key={key}>
                <strong>{key}</strong>: {value}
              </li>
            ))}
          </ul>
        )}
      </article>
      {attribution.bridge ? (
        <article style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, background: '#fff' }}>
          <h2 style={{ marginTop: 0 }}>Bridge / infra</h2>
          <div style={{ display: 'grid', gap: 8 }}>
            <div><strong>Affected</strong>: {String(attribution.bridge.affected)}</div>
            <div><strong>Timeout</strong>: {String(attribution.bridge.timeout)}</div>
            <div><strong>Provider unavailable</strong>: {String(attribution.bridge.provider_unavailable)}</div>
            <div><strong>Transport failure</strong>: {String(attribution.bridge.transport_failure)}</div>
            {attribution.bridge.message ? <div><strong>Message</strong>: {attribution.bridge.message}</div> : null}
          </div>
        </article>
      ) : null}
    </section>
  );
}

function SupplementalPanel({ summary }: { summary: RunSummaryResponse }) {
  if (!summary.supplemental) {
    return null;
  }
  return (
    <section style={{ marginTop: 24 }}>
      <h2>Supplemental oracle-finalization</h2>
      {summary.supplemental.warnings.length > 0 ? (
        <div style={{ marginBottom: 12, padding: 12, borderRadius: 8, background: '#fef3c7', color: '#92400e' }}>
          {summary.supplemental.warnings.join('; ')}
        </div>
      ) : null}
      <p style={{ color: '#4b5563' }}>Available cases: {summary.supplemental.available_case_count ?? 0}</p>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {summary.supplemental.oracle_final_metrics.map((metric) => (
          <MetricCard key={`oracle-${metric.key}`} label={metric.label} value={metric.value} unit={metric.unit} />
        ))}
      </div>
    </section>
  );
}

export function RunSummaryPage() {
  const { runId = '' } = useParams();
  const [run, setRun] = useState<RunStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<RunSummaryResponse | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<RunArtifactsResponse | null>(null);

  useEffect(() => {
    let active = true;
    fetchRun(runId)
      .then((response) => {
        if (!active) return;
        setRun(response);
        setError(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(apiErrorMessage(err));
      });
    return () => {
      active = false;
    };
  }, [runId]);

  useEffect(() => {
    if (!run || !['queued', 'running'].includes(run.status)) {
      return;
    }
    const timer = window.setTimeout(() => {
      fetchRun(run.run_id)
        .then((response) => {
          setRun(response);
          setError(null);
        })
        .catch((err) => setError(apiErrorMessage(err)));
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [run]);

  useEffect(() => {
    if (!run) {
      return;
    }
    if (run.status === 'completed') {
      fetchRunSummary(run.run_id)
        .then((response) => {
          setSummary(response);
          setSummaryError(null);
        })
        .catch((err) => setSummaryError(apiErrorMessage(err)));
      fetchRunArtifacts(run.run_id)
        .then((response) => setArtifacts(response))
        .catch((err) => setSummaryError(apiErrorMessage(err)));
      return;
    }
    if (run.status === 'failed') {
      setSummary({
        run_id: run.run_id,
        status: 'failed',
        state: 'failed',
        overall_metrics: [],
        baseline_compare: null,
        summary_paths: {
          metrics_path: run.metrics_path,
          summary_path: run.summary_path,
        },
        warnings: [],
        error_summary: run.error_summary,
      });
      setArtifacts({ run_id: run.run_id, results_root: run.results_root, items: [] });
      return;
    }
    setSummary({
      run_id: run.run_id,
      status: run.status,
      state: 'pending',
      overall_metrics: [],
      baseline_compare: null,
      summary_paths: {
        metrics_path: run.metrics_path,
        summary_path: run.summary_path,
      },
      warnings: [],
    });
    setArtifacts({ run_id: run.run_id, results_root: run.results_root, items: [] });
  }, [run]);

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: 24, fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}>
      <p>
        <Link to="/releases">Back to releases</Link> · <Link to="/runs/new">New run</Link>
      </p>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ marginBottom: 8 }}>Run Summary</h1>
        <p style={{ margin: 0, color: '#4b5563' }}>Minimal run status and metadata view.</p>
      </header>
      {run === null && error === null ? <p>Loading run...</p> : null}
      {error ? <p role="alert">Failed to load run: {error}</p> : null}
      {run ? <RunStatusPanel run={run} /> : null}
      {run?.provider === 'gpt_oauth' ? (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: '#fef3c7', color: '#92400e' }}>
          Development-only GPT provider; do not use for canonical benchmark reporting.
        </div>
      ) : null}
      {summaryError ? <p role="alert">Failed to load run summary: {summaryError}</p> : null}
      {summary?.state === 'pending' ? (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: '#eff6ff', color: '#1d4ed8' }}>
          Run is still executing. Summary will appear when artifacts are ready.
        </div>
      ) : null}
      {summary?.state === 'partial' ? (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: '#fef3c7', color: '#92400e' }}>
          Partial summary: some artifacts or baseline matches are missing.
        </div>
      ) : null}
      {summary?.state === 'failed' && summary.error_summary ? (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: '#fef2f2', color: '#991b1b' }}>
          Run failed: {summary.error_summary.message}
        </div>
      ) : null}
      <MetricSection title="Overall metrics" metrics={summary?.overall_metrics} />
      <MetricSection title="Process score" metrics={summary?.process_score} />
      <MetricSection title="Structure / compliance score" metrics={summary?.compliance_score} />
      <MetricSection title="Final diagnosis score" metrics={summary?.final_diagnosis_score} />
      {summary ? <AttributionPanel summary={summary} /> : null}
      {summary ? <SupplementalPanel summary={summary} /> : null}
      {summary?.warnings && summary.warnings.length > 0 ? (
        <div style={{ marginTop: 24, padding: 12, borderRadius: 8, background: '#fff7ed', color: '#9a3412' }}>
          {summary.warnings.join('; ')}
        </div>
      ) : null}
      {summary?.baseline_compare ? (
        <section style={{ marginTop: 24 }}>
          <BaselineCompareTable baselineCompare={summary.baseline_compare} />
        </section>
      ) : null}
      {run && ['completed'].includes(run.status) && summary && ['ready', 'partial'].includes(summary.state) ? (
        <section style={{ marginTop: 24 }}>
          <Link to={`/runs/${run.run_id}/slices`}>View slices</Link>
        </section>
      ) : null}
      {artifacts ? (
        <section style={{ marginTop: 24 }}>
          <ArtifactDownloads runId={runId} artifacts={artifacts} />
        </section>
      ) : null}
    </main>
  );
}
