import type { RunSummaryResponse } from '../lib/api';

type Props = {
  baselineCompare: NonNullable<RunSummaryResponse['baseline_compare']>;
};

function formatValue(value: number | null) {
  return value === null ? '—' : value.toFixed(4);
}

export function BaselineCompareTable({ baselineCompare }: Props) {
  return (
    <section style={{ padding: 16, borderRadius: 12, border: '1px solid #d1d5db', background: '#fff' }}>
      <h2 style={{ marginTop: 0 }}>Baseline compare</h2>
      {baselineCompare.warnings.length > 0 ? (
        <div style={{ marginBottom: 12, padding: 12, borderRadius: 8, background: '#fef3c7', color: '#92400e' }}>
          {baselineCompare.warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      ) : null}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th align="left">metric_key</th>
            <th align="right">current_value</th>
            <th align="right">pure_baseline_value</th>
            <th align="right">guided_baseline_value</th>
            <th align="right">delta_vs_pure</th>
            <th align="right">delta_vs_guided</th>
          </tr>
        </thead>
        <tbody>
          {baselineCompare.metrics.map((row) => (
            <tr key={row.metric_key}>
              <td style={{ padding: '8px 0' }}>{row.metric_key}</td>
              <td align="right">{formatValue(row.current_value)}</td>
              <td align="right">{formatValue(row.pure_baseline_value)}</td>
              <td align="right">{formatValue(row.guided_baseline_value)}</td>
              <td align="right">{formatValue(row.delta_vs_pure)}</td>
              <td align="right">{formatValue(row.delta_vs_guided)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
