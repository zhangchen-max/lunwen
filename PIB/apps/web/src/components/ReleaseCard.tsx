import { Link } from 'react-router-dom';
import type { ReleaseListItem } from '../lib/api';

function shortHash(value: string | null): string {
  if (!value) return 'n/a';
  return `${value.slice(0, 8)}...${value.slice(-8)}`;
}

export function ReleaseCard({ item }: { item: ReleaseListItem }) {
  return (
    <article style={{ border: '1px solid #d1d5db', borderRadius: 12, padding: 16, background: '#fff' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <h2 style={{ margin: '0 0 8px', fontSize: 18 }}>{item.release_id}</h2>
          <div style={{ color: '#4b5563', fontSize: 14 }}>{item.label}</div>
        </div>
        <span style={{ alignSelf: 'start', padding: '4px 8px', borderRadius: 9999, background: '#e0f2fe', color: '#075985', fontSize: 12 }}>
          {item.status}
        </span>
      </div>
      <dl style={{ margin: '16px 0', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <dt style={{ fontSize: 12, color: '#6b7280' }}>Benchmark version</dt>
          <dd style={{ margin: 0 }}>{item.benchmark_version ?? 'n/a'}</dd>
        </div>
        <div>
          <dt style={{ fontSize: 12, color: '#6b7280' }}>Dataset hash</dt>
          <dd style={{ margin: 0 }}>{shortHash(item.dataset_hash_sha256)}</dd>
        </div>
        <div>
          <dt style={{ fontSize: 12, color: '#6b7280' }}>Reports</dt>
          <dd style={{ margin: 0 }}>{item.baseline_reports.length}</dd>
        </div>
        <div>
          <dt style={{ fontSize: 12, color: '#6b7280' }}>Audits</dt>
          <dd style={{ margin: 0 }}>{item.audit_reports.length}</dd>
        </div>
      </dl>
      <Link to={`/releases/${item.release_id}`}>View release detail</Link>
    </article>
  );
}
