import type { RunStatusResponse } from '../lib/api';

type Props = {
  run: RunStatusResponse;
};

export function RunStatusPanel({ run }: Props) {
  return (
    <section style={{ padding: 16, borderRadius: 12, border: '1px solid #d1d5db', background: '#fff', display: 'grid', gap: 12 }}>
      <div><strong>Run ID:</strong> {run.run_id}</div>
      <div><strong>Release:</strong> {run.release_id}</div>
      <div><strong>Type:</strong> {run.run_type}</div>
      <div><strong>Provider:</strong> {run.provider}</div>
      <div><strong>Model:</strong> {run.model_name}</div>
      <div><strong>Split:</strong> {run.split_name}</div>
      <div><strong>Status:</strong> {run.status}</div>
      <div><strong>Created:</strong> {run.created_at}</div>
      <div><strong>Started:</strong> {run.started_at ?? 'n/a'}</div>
      <div><strong>Finished:</strong> {run.finished_at ?? 'n/a'}</div>
      <div><strong>Results root:</strong> <code>{run.results_root ?? 'n/a'}</code></div>
      <div><strong>Metrics path:</strong> <code>{run.metrics_path ?? 'n/a'}</code></div>
      <div><strong>Summary path:</strong> <code>{run.summary_path ?? 'n/a'}</code></div>
      {run.error_summary ? (
        <div style={{ padding: 12, borderRadius: 8, background: '#fef2f2', color: '#991b1b' }}>
          <div><strong>Error:</strong> {run.error_summary.message}</div>
          <div><strong>stdout:</strong> <code>{run.error_summary.stdout_path ?? 'n/a'}</code></div>
          <div><strong>stderr:</strong> <code>{run.error_summary.stderr_path ?? 'n/a'}</code></div>
        </div>
      ) : null}
    </section>
  );
}
