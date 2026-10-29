type ReplayTurn = {
  t: number | null;
  doctor_slot_id: string | null;
  doctor_utterance: string | null;
  patient_utterance: string | null;
};

type ReplayTimelineProps = {
  available: boolean;
  turns: ReplayTurn[];
  finalOutput?: Record<string, unknown> | null;
};

type DiagnosisItem = {
  label: string;
  confidence: number | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function extractDiagnosisTopk(value: unknown): DiagnosisItem[] {
  const record = asRecord(value);
  const raw = record?.diagnosis_topk;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((item) => {
      const entry = asRecord(item);
      if (!entry || typeof entry.label !== 'string') {
        return null;
      }
      return {
        label: entry.label,
        confidence: typeof entry.confidence === 'number' ? entry.confidence : null,
      };
    })
    .filter((item): item is DiagnosisItem => item !== null);
}

function extractRiskFlags(value: unknown): Array<{ key: string; value: string }> {
  const record = asRecord(value);
  const raw = asRecord(record?.risk_flags);
  if (!raw) {
    return [];
  }
  return Object.entries(raw).map(([key, itemValue]) => ({
    key,
    value: String(itemValue),
  }));
}

function buildFinalPreview(value: unknown): string | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }
  const previewSource: Record<string, unknown> = { ...record };
  delete previewSource.diagnosis_topk;
  delete previewSource.risk_flags;
  if (Object.keys(previewSource).length === 0) {
    return null;
  }
  const serialized = JSON.stringify(previewSource, null, 2);
  if (serialized.length <= 280) {
    return serialized;
  }
  return `${serialized.slice(0, 277)}...`;
}

function renderConfidence(confidence: number | null): string {
  if (confidence === null) {
    return '—';
  }
  return `${Math.round(confidence * 100)}%`;
}

export function ReplayTimeline({ available, turns, finalOutput = null }: ReplayTimelineProps) {
  const diagnosisTopk = extractDiagnosisTopk(finalOutput);
  const riskFlags = extractRiskFlags(finalOutput);
  const finalPreview = buildFinalPreview(finalOutput);

  return (
    <section style={{ marginTop: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Interview replay</h2>
        {available ? (
          <span style={{ fontSize: 12, color: '#6b7280', background: '#f3f4f6', borderRadius: 999, padding: '4px 10px' }}>
            {turns.length} turns
          </span>
        ) : null}
      </div>
      {!available ? (
        <div style={{ color: '#6b7280', border: '1px dashed #d1d5db', borderRadius: 12, padding: 16, background: '#f9fafb' }}>
          Replay unavailable.
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gap: 16,
            padding: 16,
            borderRadius: 16,
            border: '1px solid #e5e7eb',
            background: 'linear-gradient(180deg, #f8fafc 0%, #ffffff 100%)',
          }}
        >
          {turns.map((turn, index) => (
            <article key={`${turn.t ?? index}-${turn.doctor_slot_id ?? 'turn'}`} style={{ display: 'grid', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <div
                  style={{
                    fontSize: 12,
                    color: '#475569',
                    marginBottom: 2,
                    padding: '4px 10px',
                    borderRadius: 999,
                    background: '#e2e8f0',
                  }}
                >
                  Turn {turn.t ?? index + 1} · {turn.doctor_slot_id ?? 'unknown_slot'}
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <div
                  style={{
                    maxWidth: '78%',
                    borderRadius: '18px 18px 18px 6px',
                    background: '#dbeafe',
                    color: '#1e3a8a',
                    padding: '12px 14px',
                    boxShadow: '0 1px 2px rgba(15, 23, 42, 0.08)',
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>Doctor · {turn.doctor_slot_id ?? 'unknown_slot'}</div>
                  <div style={{ lineHeight: 1.5 }}>{turn.doctor_utterance ?? '—'}</div>
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <div
                  style={{
                    maxWidth: '78%',
                    borderRadius: '18px 18px 6px 18px',
                    background: '#f3f4f6',
                    color: '#111827',
                    padding: '12px 14px',
                    boxShadow: '0 1px 2px rgba(15, 23, 42, 0.06)',
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6, color: '#4b5563' }}>Patient</div>
                  <div style={{ lineHeight: 1.5 }}>{turn.patient_utterance ?? '—'}</div>
                </div>
              </div>
            </article>
          ))}
          {finalOutput ? (
            <article
              style={{
                marginTop: 8,
                borderRadius: 14,
                border: '1px solid #d1fae5',
                background: '#ecfdf5',
                padding: 16,
                display: 'grid',
                gap: 12,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0, fontSize: 16 }}>FINAL</h3>
                <span style={{ fontSize: 12, color: '#065f46', background: '#d1fae5', padding: '4px 10px', borderRadius: 999 }}>
                  structured output
                </span>
              </div>
              {diagnosisTopk.length > 0 ? (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8, color: '#065f46' }}>Diagnosis top-k</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {diagnosisTopk.map((item) => (
                      <span
                        key={`${item.label}-${item.confidence ?? 'na'}`}
                        style={{
                          fontSize: 12,
                          color: '#065f46',
                          background: '#ffffff',
                          border: '1px solid #a7f3d0',
                          borderRadius: 999,
                          padding: '5px 10px',
                        }}
                      >
                        {item.label} · {renderConfidence(item.confidence)}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {riskFlags.length > 0 ? (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8, color: '#065f46' }}>Risk flags</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {riskFlags.map((flag) => (
                      <span
                        key={flag.key}
                        style={{
                          fontSize: 12,
                          color: '#111827',
                          background: '#ffffff',
                          border: '1px solid #d1d5db',
                          borderRadius: 999,
                          padding: '5px 10px',
                        }}
                      >
                        {flag.key}: {flag.value}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {finalPreview ? (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8, color: '#065f46' }}>Additional output</div>
                  <pre
                    style={{
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontSize: 12,
                      lineHeight: 1.5,
                      background: '#ffffff',
                      border: '1px solid #d1d5db',
                      borderRadius: 10,
                      padding: 12,
                    }}
                  >
                    {finalPreview}
                  </pre>
                </div>
              ) : null}
            </article>
          ) : null}
        </div>
      )}
    </section>
  );
}
