export type ArtifactItem = {
  label: string;
  path: string;
  meta?: string;
};

export function ArtifactList({ title, items, emptyText }: { title: string; items: ArtifactItem[]; emptyText: string }) {
  return (
    <section>
      <h2>{title}</h2>
      {items.length === 0 ? (
        <p>{emptyText}</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={`${title}-${item.path}`}>
              <strong>{item.label}:</strong> <code>{item.path}</code>
              {item.meta ? <span style={{ color: '#6b7280' }}> ({item.meta})</span> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
