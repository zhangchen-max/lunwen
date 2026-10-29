# P0 Regression Checklist

## 1. Startup Checks

- [ ] `python -m webapi.server --host 127.0.0.1 --port 8780` can start
- [ ] `GET /api/releases` returns `200`
- [ ] `GET /api/releases/:releaseId` returns `200`
- [ ] `GET /api/runs/options` returns `200`
- [ ] Frontend can start if `node` / `npm` is available

Recommended commands:

```bash
python -m webapi.server --host 127.0.0.1 --port 8780
curl -s http://127.0.0.1:8780/api/releases
curl -s http://127.0.0.1:8780/api/releases/v1.1.0-rc1
curl -s http://127.0.0.1:8780/api/runs/options
```

Frontend (optional):

```bash
cd apps/web
npm install
npm run dev
```

## 2. Route Checks

- [ ] `/releases`
- [ ] `/releases/:releaseId`
- [ ] `/runs/new`
- [ ] `/runs/:runId`
- [ ] `/runs/:runId/slices`
- [ ] `/runs/:runId/cases/:caseId`

## 3. Core API Contract Checks

### 3.1 Releases

- [ ] `GET /api/releases`
- [ ] `GET /api/releases/:releaseId`
- [ ] `POST /api/releases/validate-current`
- [ ] `POST /api/releases/freeze-current`
- [ ] `GET /api/jobs/:jobId`

### 3.2 Runs

- [ ] `GET /api/runs/options`
- [ ] `POST /api/runs`
- [ ] `GET /api/runs/:runId`
- [ ] `GET /api/runs/:runId/summary`
- [ ] `GET /api/runs/:runId/artifacts`

For `GET /api/runs/:runId/summary`, additionally validate:

- [ ] `process_score`
- [ ] `compliance_score`
- [ ] `final_diagnosis_score`
- [ ] `failure_attribution`
- [ ] `supplemental`

### 3.3 Slice and case projections

- [ ] `GET /api/runs/:runId/slices`
- [ ] `GET /api/runs/:runId/cases`
- [ ] `GET /api/runs/:runId/cases/:caseId`

For `GET /api/runs/:runId/slices`, additionally validate:

- [ ] `by_failure_source`
- [ ] `by_risk_positive`
- [ ] `by_personality_spectrum`
- [ ] `by_timeout_affected`
- [ ] `by_parse_affected`
- [ ] `by_protocol_clean_only`

For `GET /api/runs/:runId/cases/:caseId`, additionally validate:

- [ ] `failure_analysis.failure_sources`
- [ ] replay remains `partial` rather than `500` when missing

For `summary`, `slices`, `cases`, `case detail`, validate at least:

- [ ] ready
- [ ] partial (where applicable)
- [ ] failed / not found / not ready (where applicable)

## 4. Download Checks

- [ ] `metrics.json` can be downloaded
- [ ] `summary.csv` can be downloaded when present
- [ ] path traversal is rejected

Recommended commands:

```bash
curl -i 'http://127.0.0.1:8780/api/runs/run_20260309_045551_be9ba6b6/artifacts/download?path=results/static/heuristic/run_20260309_045551_be9ba6b6/run_001/metrics.json'
curl -s 'http://127.0.0.1:8780/api/runs/run_20260309_045551_be9ba6b6/artifacts/download?path=../release/benchmark_manifest.json'
```

## 5. Regression Test Commands

### 5.1 Core benchmark regression

```bash
python -m scripts.run_tests
```

### 5.2 WebAPI contract regression

```bash
python -m unittest \
  tests.test_webapi_releases_routes \
  tests.test_webapi_release_jobs \
  tests.test_webapi_runs_routes \
  tests.test_webapi_run_summary_routes \
  tests.test_webapi_case_projection_routes -v
```

### 5.3 Product regression

```bash
python -m unittest \
  tests.test_product_run_create_status_flow \
  tests.test_product_slice_failure_loop \
  tests.test_product_p0_happy_path_smoke -v
```

## 6. Pre-demo Completed Run Checks

Recommended completed runs for smoke/demo:

- dynamic: `run_20260309_050053_f3a6c6a0`
- static: `run_20260309_045551_be9ba6b6`

Validate before demo:

- [ ] summary endpoint returns ready/partial
- [ ] summary endpoint exposes three-part scores and failure attribution
- [ ] slices endpoint returns ready/partial
- [ ] slices endpoint exposes failure-source and protocol-clean-only groups
- [ ] filtered cases endpoint returns non-empty result for at least one failure bucket
- [ ] case detail returns ready/partial and does not 500
- [ ] case detail exposes `failure_sources`

## 7. Expected Degradation Behavior

- [ ] missing `summary.csv` -> `partial`, not crash
- [ ] missing replay -> `partial` or `Replay unavailable`, not crash
- [ ] run not completed -> `pending` or `run_not_ready`
- [ ] unknown `runId` / `caseId` -> structured error payload
- [ ] protocol/parse/timeout affected runs remain explorable through projection rather than collapsing into a blank page
