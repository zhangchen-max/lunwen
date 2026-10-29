type Props = {
  label: string;
  value: number;
  unit?: string | null;
};

export function MetricCard({ label, value, unit }: Props) {
  const display = unit === 'ratio' ? value.toFixed(4) : String(value);
  return (
    <div style={{ padding: 16, borderRadius: 12, border: '1px solid #d1d5db', background: '#fff', minWidth: 180 }}>
      <div style={{ fontSize: 13, color: '#4b5563', marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700 }}>{display}</div>
    </div>
  );
}
