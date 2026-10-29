import type { ReleaseDetailResponse } from '../lib/api';

function renderValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  if (value === null || value === undefined || value === '') {
    return 'n/a';
  }
  return String(value);
}

export function ManifestSummary({ manifest }: { manifest: ReleaseDetailResponse['manifest'] }) {
  const rows = [
    ['Benchmark version', manifest.benchmark_version],
    ['Dataset version', manifest.dataset_version],
    ['Scoring policy version', manifest.scoring_policy_version],
    ['No-oracle policy version', manifest.no_oracle_policy_version],
    ['Slot count', manifest.slot_count],
    ['Dynamic max turns', manifest.dynamic_max_turns],
    ['OS_OCRD subtypes', manifest.os_ocrd_subtypes],
    ['Dataset hash', manifest.dataset_hash_sha256],
    ['Scoring hash', manifest.scoring_hash_sha256],
    ['Cases sha256', manifest.cases_sha256],
    ['Rubrics sha256', manifest.rubrics_sha256],
    ['Splits sha256', manifest.splits_sha256],
  ];

  return (
    <section>
      <h2>Manifest summary</h2>
      <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '8px 16px' }}>
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: 'contents' }}>
            <dt style={{ fontWeight: 600 }}>{label}</dt>
            <dd style={{ margin: 0 }}>{renderValue(value)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
