type SliceMetricMap = Record<string, number | null> | undefined;

type SliceRow = {
  key: string;
  label: string;
  case_count: number;
  metrics?: SliceMetricMap;
};

type SliceTableProps = {
  title: string;
  rows: SliceRow[];
  activeKey?: string | null;
  onSelect: (row: SliceRow) => void;
};

function formatMetric(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

export function SliceTable({ title, rows, activeKey, onSelect }: SliceTableProps) {
  return (
    <section style={{ marginTop: 24 }}>
      <h2 style={{ marginBottom: 12 }}>{title}</h2>
      {rows.length === 0 ? (
        <p style={{ color: '#6b7280' }}>No slice data.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', border: '1px solid #e5e7eb' }}>
          <thead style={{ background: '#f9fafb' }}>
            <tr>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Slice</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Cases</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Top-1</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Top-3</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>Must-Ask</th>
              <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb' }}>SVCL</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const selected = activeKey === row.key;
              return (
                <tr
                  key={row.key}
                  onClick={() => onSelect(row)}
                  style={{ background: selected ? '#eff6ff' : undefined, cursor: 'pointer' }}
                >
                  <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{row.label}</td>
                  <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{row.case_count}</td>
                  <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{formatMetric(row.metrics?.top1_acc)}</td>
                  <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{formatMetric(row.metrics?.top3_cov)}</td>
                  <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{formatMetric(row.metrics?.must_ask_hit_rate)}</td>
                  <td style={{ padding: 10, borderBottom: '1px solid #f3f4f6' }}>{formatMetric(row.metrics?.svcl_coverage)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
