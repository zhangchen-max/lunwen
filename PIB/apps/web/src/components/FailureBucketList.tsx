import type { FailureBucketRow } from '../lib/api';

type FailureBucketListProps = {
  title?: string;
  buckets: FailureBucketRow[] | string[];
  activeKey?: string | null;
  onSelect?: (bucketKey: string) => void;
};

export function FailureBucketList({ title = 'Failure buckets', buckets, activeKey, onSelect }: FailureBucketListProps) {
  const normalized = buckets.map((bucket) =>
    typeof bucket === 'string' ? { key: bucket, label: bucket, case_count: null } : bucket,
  );

  return (
    <section style={{ marginTop: 24 }}>
      <h2 style={{ marginBottom: 12 }}>{title}</h2>
      {normalized.length === 0 ? (
        <p style={{ color: '#6b7280' }}>No failure buckets.</p>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {normalized.map((bucket) => {
            const active = activeKey === bucket.key;
            const label = bucket.case_count === null ? bucket.label : `${bucket.label} (${bucket.case_count})`;
            return onSelect ? (
              <button
                key={bucket.key}
                type="button"
                onClick={() => onSelect(bucket.key)}
                style={{
                  border: '1px solid #d1d5db',
                  background: active ? '#eff6ff' : '#fff',
                  color: active ? '#1d4ed8' : '#111827',
                  padding: '8px 10px',
                  borderRadius: 8,
                  cursor: 'pointer',
                }}
              >
                {label}
              </button>
            ) : (
              <span
                key={bucket.key}
                style={{ border: '1px solid #e5e7eb', background: '#f9fafb', padding: '8px 10px', borderRadius: 8 }}
              >
                {label}
              </span>
            );
          })}
        </div>
      )}
    </section>
  );
}
