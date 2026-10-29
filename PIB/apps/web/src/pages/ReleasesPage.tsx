import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ReleaseCard } from '../components/ReleaseCard';
import {
  apiErrorMessage,
  createFreezeCurrentJob,
  createValidateCurrentJob,
  fetchJob,
  fetchReleases,
  type JobResponse,
  type ReleaseListItem,
} from '../lib/api';

export function ReleasesPage() {
  const [items, setItems] = useState<ReleaseListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<false | 'validate' | 'freeze'>(false);

  async function loadReleases() {
    setError(null);
    const response = await fetchReleases();
    setItems(response.items);
  }

  useEffect(() => {
    let active = true;
    loadReleases()
      .then(() => {
        if (!active) return;
      })
      .catch((err) => {
        if (!active) return;
        setError(apiErrorMessage(err));
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) {
      return;
    }
    const timer = window.setTimeout(() => {
      fetchJob(job.job_id)
        .then((nextJob) => {
          setJob(nextJob);
          if (nextJob.status === 'succeeded') {
            void loadReleases().catch((err) => setError(apiErrorMessage(err)));
          }
        })
        .catch((err) => setJobError(apiErrorMessage(err)));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [job]);

  async function triggerJob(kind: 'validate' | 'freeze') {
    setSubmitting(kind);
    setJobError(null);
    try {
      const nextJob = kind === 'validate' ? await createValidateCurrentJob() : await createFreezeCurrentJob();
      setJob(nextJob);
    } catch (err) {
      setJobError(apiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: 24, fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ marginBottom: 8 }}>Release Center</h1>
        <p style={{ margin: 0, color: '#4b5563' }}>Read-only frozen benchmark releases.</p>
        <p style={{ marginTop: 8 }}>
          <Link to="/runs/new">New Run</Link>
        </p>
      </header>

      <section style={{ marginBottom: 24, padding: 16, borderRadius: 12, border: '1px solid #d1d5db', background: '#fff' }}>
        <h2 style={{ marginTop: 0 }}>Current workspace</h2>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button onClick={() => void triggerJob('validate')} disabled={submitting !== false}>
            {submitting === 'validate' ? 'Submitting validate...' : 'Validate current workspace'}
          </button>
          <button onClick={() => void triggerJob('freeze')} disabled={submitting !== false}>
            {submitting === 'freeze' ? 'Submitting freeze...' : 'Freeze current workspace'}
          </button>
        </div>
        {jobError ? <p role="alert">Job request failed: {jobError}</p> : null}
        {job ? (
          <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: '#f9fafb' }}>
            <div><strong>Job ID:</strong> {job.job_id}</div>
            <div><strong>Type:</strong> {job.job_type}</div>
            <div><strong>Status:</strong> {job.status}</div>
            {job.target_release_id ? <div><strong>Target release:</strong> {job.target_release_id}</div> : null}
            {job.result_json_path ? <div><strong>Result:</strong> <code>{job.result_json_path}</code></div> : null}
            {job.structured_errors.length > 0 ? (
              <div style={{ marginTop: 12 }}>
                <strong>Structured errors</strong>
                <ul>
                  {job.structured_errors.map((item, index) => (
                    <li key={`${item.field}-${index}`}>
                      <code>{item.scope}</code> / <code>{item.field}</code>
                      {item.case_id ? <> / <code>{item.case_id}</code></> : null}
                      : {item.message}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      {items === null && error === null ? <p>Loading releases...</p> : null}
      {error ? <p role="alert">Failed to load releases: {error}</p> : null}
      {items && items.length === 0 ? <p>No releases found.</p> : null}
      {items && items.length > 0 ? (
        <section style={{ display: 'grid', gap: 16 }}>
          {items.map((item) => (
            <ReleaseCard key={item.release_id} item={item} />
          ))}
        </section>
      ) : null}
    </main>
  );
}
