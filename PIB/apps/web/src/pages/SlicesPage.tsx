import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CasesTable } from '../components/CasesTable';
import { FailureBucketList } from '../components/FailureBucketList';
import { SliceTable } from '../components/SliceTable';
import { apiErrorMessage, fetchRunCases, fetchRunSlices, type RunCasesResponse, type RunSlicesResponse } from '../lib/api';

type ActiveFilter = {
  module?: string | null;
  label?: string | null;
  ambiguity?: string | null;
  required_svcl_domains_count?: string | null;
  failure_bucket?: string | null;
  risk_positive?: string | null;
  personality_spectrum?: string | null;
  timeout_affected?: string | null;
  parse_affected?: string | null;
  protocol_clean_only?: string | null;
  failure_source?: string | null;
};

export function SlicesPage() {
  const { runId = '' } = useParams();
  const [slices, setSlices] = useState<RunSlicesResponse | null>(null);
  const [cases, setCases] = useState<RunCasesResponse | null>(null);
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchRunSlices(runId)
      .then((response) => {
        if (!active) return;
        setSlices(response);
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
    if (!slices || !['ready', 'partial'].includes(slices.state)) {
      return;
    }
    let active = true;
    fetchRunCases(runId, { ...activeFilter, limit: 50, offset: 0 })
      .then((response) => {
        if (!active) return;
        setCases(response);
      })
      .catch((err) => {
        if (!active) return;
        setError(apiErrorMessage(err));
      });
    return () => {
      active = false;
    };
  }, [runId, slices, activeFilter]);

  const activeFilterLabel = useMemo(() => {
    const [key, value] = Object.entries(activeFilter).find(([, current]) => current) ?? [];
    return key && value ? `${key}: ${value}` : 'All cases';
  }, [activeFilter]);

  return (
    <main style={{ maxWidth: 1080, margin: '0 auto', padding: 24, fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}>
      <p>
        <Link to="/releases">Releases</Link> · <Link to={`/runs/${runId}`}>Run summary</Link>
      </p>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ marginBottom: 8 }}>Slice Analysis</h1>
        <p style={{ margin: 0, color: '#4b5563' }}>Best-effort slice and failure-bucket projection for run {runId}.</p>
      </header>

      {!slices && !error ? <p>Loading slices...</p> : null}
      {error ? <p role="alert">Failed to load slices: {error}</p> : null}
      {slices?.state === 'pending' ? <p>Run is still executing. Slices will appear when the run is ready.</p> : null}
      {slices?.state === 'failed' ? <p role="alert">Run failed. Slice projection is unavailable.</p> : null}
      {slices?.state === 'partial' ? (
        <div style={{ padding: 12, borderRadius: 8, background: '#fef3c7', color: '#92400e' }}>Partial slice projection: some case joins or replay artifacts are missing.</div>
      ) : null}

      {slices && ['ready', 'partial'].includes(slices.state) ? (
        <>
          <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: '#f9fafb', border: '1px solid #e5e7eb' }}>
            Cases: {slices.totals.completed_case_count} / {slices.totals.case_count} · Active filter: {activeFilterLabel}
          </div>
          <SliceTable title="By module" rows={slices.slices.by_module} activeKey={activeFilter.module ?? null} onSelect={(row) => setActiveFilter({ module: row.key })} />
          <SliceTable title="By label" rows={slices.slices.by_label} activeKey={activeFilter.label ?? null} onSelect={(row) => setActiveFilter({ label: row.key })} />
          <SliceTable title="By ambiguity" rows={slices.slices.by_ambiguity} activeKey={activeFilter.ambiguity ?? null} onSelect={(row) => setActiveFilter({ ambiguity: row.key })} />
          <SliceTable
            title="By required SVCL domains count"
            rows={slices.slices.by_required_svcl_domains_count}
            activeKey={activeFilter.required_svcl_domains_count ?? null}
            onSelect={(row) => setActiveFilter({ required_svcl_domains_count: row.key })}
          />
          <SliceTable
            title="By failure source"
            rows={slices.slices.by_failure_source}
            activeKey={activeFilter.failure_source ?? null}
            onSelect={(row) => setActiveFilter({ failure_source: row.key })}
          />
          <FailureBucketList
            buckets={slices.slices.by_failure_bucket}
            activeKey={activeFilter.failure_bucket ?? null}
            onSelect={(bucketKey) => setActiveFilter({ failure_bucket: bucketKey })}
          />
          <SliceTable
            title="By risk-positive"
            rows={slices.slices.by_risk_positive}
            activeKey={activeFilter.risk_positive ?? null}
            onSelect={(row) => setActiveFilter({ risk_positive: row.key })}
          />
          <SliceTable
            title="By personality spectrum"
            rows={slices.slices.by_personality_spectrum}
            activeKey={activeFilter.personality_spectrum ?? null}
            onSelect={(row) => setActiveFilter({ personality_spectrum: row.key })}
          />
          <SliceTable
            title="By timeout affected"
            rows={slices.slices.by_timeout_affected}
            activeKey={activeFilter.timeout_affected ?? null}
            onSelect={(row) => setActiveFilter({ timeout_affected: row.key })}
          />
          <SliceTable
            title="By parse affected"
            rows={slices.slices.by_parse_affected}
            activeKey={activeFilter.parse_affected ?? null}
            onSelect={(row) => setActiveFilter({ parse_affected: row.key })}
          />
          <SliceTable
            title="By protocol clean only"
            rows={slices.slices.by_protocol_clean_only}
            activeKey={activeFilter.protocol_clean_only ?? null}
            onSelect={(row) => setActiveFilter({ protocol_clean_only: row.key })}
          />
          {cases ? <CasesTable runId={runId} cases={cases.items} /> : <p style={{ marginTop: 24 }}>Loading filtered cases...</p>}
        </>
      ) : null}
    </main>
  );
}
