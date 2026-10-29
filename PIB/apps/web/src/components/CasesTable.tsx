import { Link } from 'react-router-dom';
import type { RunCasesResponse } from '../lib/api';

type CasesTableProps = {
  runId: string;
  cases: RunCasesResponse['items'];
};

function formatMetric(value: number | null): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return value.toFixed(2);
}

export function CasesTable({ runId, cases }: CasesTableProps) {
  return (
    <section style={{ marginTop: 24 }}>
      <h2 style={{ marginBottom: 12 }}>Cases</h2>
      {cases.length === 0 ? (
        <p style={{ color: '#6b7280' }}>No cases for current filter.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', border: '1px solid #e5e7eb' }}>
          <thead style={{ background: '#f9fafb' }}>
            <tr>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Case</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Module</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Gold</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Pred Top-1</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Must-Ask</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>SVCL</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Failure Source</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Buckets</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((row) => (
              <tr key={row.case_id}>
                <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>
                  <Link to={`/runs/${runId}/cases/${row.case_id}`}>{row.case_id}</Link>
                </td>
                <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{row.dsm_module}</td>
                <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{row.gold_label}</td>
                <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{row.pred_top1 ?? '—'}</td>
                <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{formatMetric(row.must_ask_hit_rate)}</td>
                <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{formatMetric(row.svcl_coverage)}</td>
                <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{row.failure_source ?? '—'}</td>
                <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{row.failure_buckets.join(', ') || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
