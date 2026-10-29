import { artifactDownloadUrl, type RunArtifactsResponse } from '../lib/api';

type Props = {
  runId: string;
  artifacts: RunArtifactsResponse;
};

export function ArtifactDownloads({ runId, artifacts }: Props) {
  return (
    <section style={{ padding: 16, borderRadius: 12, border: '1px solid #d1d5db', background: '#fff' }}>
      <h2 style={{ marginTop: 0 }}>Artifacts</h2>
      {artifacts.items.length === 0 ? <p style={{ marginBottom: 0 }}>No artifacts available.</p> : null}
      {artifacts.items.length > 0 ? (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th align="left">label</th>
              <th align="left">kind</th>
              <th align="right">size</th>
              <th align="left">download</th>
            </tr>
          </thead>
          <tbody>
            {artifacts.items.map((item) => (
              <tr key={item.path}>
                <td style={{ padding: '8px 0' }}>{item.label}</td>
                <td>{item.kind}</td>
                <td align="right">{item.size_bytes}</td>
                <td>
                  {item.exists ? (
                    <a href={artifactDownloadUrl(runId, item.path)}>Download</a>
                  ) : (
                    <span style={{ color: '#9ca3af' }}>Unavailable</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
