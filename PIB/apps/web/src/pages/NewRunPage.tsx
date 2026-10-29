import { type FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { RunConfigForm } from '../components/RunConfigForm';
import { apiErrorMessage, createRun, fetchRunOptions, type CreateRunRequest, type RunOptionsResponse } from '../lib/api';

function defaultForm(options: RunOptionsResponse, releaseId: string | null): CreateRunRequest {
  const defaultProvider = options.providers[0]?.id || 'baseline';
  return {
    release_id: releaseId || options.releases[0]?.release_id || '',
    run_type: 'dynamic',
    provider: defaultProvider,
    model_name: defaultProvider === 'gpt_oauth' ? 'gpt-5.2' : '',
    split_name: options.default_split || 'test',
    notes: '',
  };
}

export function NewRunPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [options, setOptions] = useState<RunOptionsResponse | null>(null);
  const [form, setForm] = useState<CreateRunRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function handleFormChange(next: CreateRunRequest) {
    if (next.provider === 'gpt_oauth' && next.model_name !== 'gpt-5.2') {
      setForm({ ...next, model_name: 'gpt-5.2' });
      return;
    }
    setForm(next);
  }

  useEffect(() => {
    let active = true;
    fetchRunOptions()
      .then((response) => {
        if (!active) return;
        setOptions(response);
        setForm(defaultForm(response, searchParams.get('release_id')));
      })
      .catch((err) => {
        if (!active) return;
        setError(apiErrorMessage(err));
      });
    return () => {
      active = false;
    };
  }, [searchParams]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await createRun(form);
      navigate(created.redirect_url);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: 24, fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}>
      <p><Link to="/releases">Back to releases</Link></p>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ marginBottom: 8 }}>New Run</h1>
        <p style={{ margin: 0, color: '#4b5563' }}>Create one static or dynamic benchmark run.</p>
      </header>
      {!options || !form ? <p>Loading run options...</p> : null}
      {options && form ? (
        <RunConfigForm
          options={options}
          value={form}
          onChange={handleFormChange}
          onSubmit={handleSubmit}
          submitting={submitting}
          error={error}
        />
      ) : null}
      {!options && error ? <p role="alert">Failed to load run options: {error}</p> : null}
    </main>
  );
}
