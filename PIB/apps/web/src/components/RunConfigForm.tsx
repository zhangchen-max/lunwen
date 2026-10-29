import { type FormEvent } from 'react';
import type { CreateRunRequest, RunOptionsResponse } from '../lib/api';

type Props = {
  options: RunOptionsResponse;
  value: CreateRunRequest;
  onChange: (next: CreateRunRequest) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  submitting: boolean;
  error: string | null;
};

export function RunConfigForm({ options, value, onChange, onSubmit, submitting, error }: Props) {
  const isGptOauth = value.provider === 'gpt_oauth';
  return (
    <form onSubmit={onSubmit} style={{ display: 'grid', gap: 16, padding: 16, borderRadius: 12, border: '1px solid #d1d5db', background: '#fff' }}>
      <div>
        <label>
          Release
          <br />
          <select
            value={value.release_id}
            onChange={(event) => onChange({ ...value, release_id: event.target.value })}
            style={{ minWidth: 320 }}
          >
            {options.releases.map((release) => (
              <option key={release.release_id} value={release.release_id}>
                {release.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div>
        <label>
          Run type
          <br />
          <select
            value={value.run_type}
            onChange={(event) => onChange({ ...value, run_type: event.target.value as CreateRunRequest['run_type'] })}
          >
            {options.run_types.map((runType) => (
              <option key={runType} value={runType}>
                {runType}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div>
        <label>
          Provider
          <br />
          <select value={value.provider} onChange={(event) => onChange({ ...value, provider: event.target.value })}>
            {options.providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.label}
              </option>
            ))}
          </select>
        </label>
        {isGptOauth ? (
          <p style={{ margin: '8px 0 0', color: '#92400e', fontSize: 14 }}>
            Uses your local Codex/ChatGPT OAuth session for development-only testing.
          </p>
        ) : null}
      </div>

      <div>
        <label>
          Model name
          <br />
          <input
            value={value.model_name}
            onChange={(event) => onChange({ ...value, model_name: event.target.value })}
            placeholder={isGptOauth ? 'gpt-5.2' : 'gpt-4.1 or dummy'}
            style={{ minWidth: 320 }}
          />
        </label>
      </div>

      <div>
        <label>
          Split
          <br />
          <input value={value.split_name} onChange={(event) => onChange({ ...value, split_name: event.target.value })} />
        </label>
      </div>

      <div>
        <label>
          Notes
          <br />
          <textarea
            value={value.notes ?? ''}
            onChange={(event) => onChange({ ...value, notes: event.target.value })}
            rows={3}
            style={{ minWidth: 320 }}
          />
        </label>
      </div>

      {error ? <p role="alert" style={{ color: '#991b1b', margin: 0 }}>{error}</p> : null}

      <div>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Submitting run...' : 'Create run'}
        </button>
      </div>
    </form>
  );
}
