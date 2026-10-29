import { Link, useParams } from 'react-router-dom';
import { useEffect, useMemo, useState } from 'react';
import { ArtifactList } from '../components/ArtifactList';
import { ManifestSummary } from '../components/ManifestSummary';
import { apiErrorMessage, fetchReleaseDetail, type ReleaseDetailResponse } from '../lib/api';

export function ReleaseDetailPage() {
  const { releaseId = '' } = useParams();
  const [detail, setDetail] = useState<ReleaseDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchReleaseDetail(releaseId)
      .then((response) => {
        if (!active) return;
        setDetail(response);
      })
      .catch((err) => {
        if (!active) return;
        setError(apiErrorMessage(err));
      });
    return () => {
      active = false;
    };
  }, [releaseId]);

  const bundleItems = useMemo(() => {
    if (!detail) return [];
    return detail.bundle.files.map((file) => ({
      label: file.name,
      path: file.path,
      meta: `${file.size} bytes`,
    }));
  }, [detail]);

  const reportItems = useMemo(() => {
    if (!detail) return [];
    return [
      ['Pure baselines', detail.reports.pure_baselines],
      ['Guided LLM baselines', detail.reports.guided_llm_baselines],
      ['Deprecated results', detail.reports.deprecated_results],
    ]
      .filter(([, path]) => Boolean(path))
      .map(([label, path]) => ({ label, path: path as string }));
  }, [detail]);

  const auditItems = useMemo(() => {
    if (!detail) return [];
    const primary = [
      ['No-oracle audit', detail.audits.no_oracle],
      ['Text contamination audit', detail.audits.text_contamination],
    ]
      .filter(([, path]) => Boolean(path))
      .map(([label, path]) => ({ label, path: path as string }));
    const other = detail.audits.other.map((path) => ({ label: 'Audit artifact', path }));
    return [...primary, ...other];
  }, [detail]);

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: 24, fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}>
      <p>
        <Link to="/releases">Back to releases</Link> · <Link to={`/runs/new?release_id=${releaseId}`}>Run on this release</Link>
      </p>
      {detail === null && error === null ? <p>Loading release detail...</p> : null}
      {error ? <p role="alert">Failed to load release detail: {error}</p> : null}
      {detail ? (
        <>
          <header style={{ marginBottom: 24 }}>
            <h1 style={{ marginBottom: 8 }}>{detail.release_id}</h1>
            <p style={{ margin: 0, color: '#4b5563' }}>{detail.label}</p>
            <p style={{ marginTop: 8 }}>
              <strong>Status:</strong> {detail.status ?? 'frozen'}
            </p>
          </header>
          {detail.partial ? (
            <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, background: '#fef3c7', color: '#92400e' }}>
              Partial release detail: manifest is available, but bundle or related artifacts are incomplete.
            </div>
          ) : null}
          <div style={{ display: 'grid', gap: 24 }}>
            <ManifestSummary manifest={detail.manifest} />
            <section>
              <h2>Registry metadata</h2>
              <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '8px 16px' }}>
                <div style={{ display: 'contents' }}>
                  <dt style={{ fontWeight: 600 }}>Last validated job</dt>
                  <dd style={{ margin: 0 }}>{detail.registry?.last_validated_job_id ?? 'n/a'}</dd>
                </div>
                <div style={{ display: 'contents' }}>
                  <dt style={{ fontWeight: 600 }}>Last frozen job</dt>
                  <dd style={{ margin: 0 }}>{detail.registry?.last_frozen_job_id ?? 'n/a'}</dd>
                </div>
                <div style={{ display: 'contents' }}>
                  <dt style={{ fontWeight: 600 }}>Created at</dt>
                  <dd style={{ margin: 0 }}>{detail.registry?.created_at ?? 'n/a'}</dd>
                </div>
                <div style={{ display: 'contents' }}>
                  <dt style={{ fontWeight: 600 }}>Updated at</dt>
                  <dd style={{ margin: 0 }}>{detail.registry?.updated_at ?? 'n/a'}</dd>
                </div>
              </dl>
            </section>
            <section>
              <h2>Bundle path</h2>
              <p style={{ margin: 0 }}>
                <code>{detail.bundle.path ?? 'n/a'}</code>
              </p>
            </section>
            <ArtifactList title="Bundle files" items={bundleItems} emptyText="No bundle files found." />
            <ArtifactList title="Reports" items={reportItems} emptyText="No report files found." />
            <ArtifactList title="Audits" items={auditItems} emptyText="No audit files found." />
          </div>
        </>
      ) : null}
    </main>
  );
}
