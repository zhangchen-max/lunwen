# PIB v1.2 Failure Attribution Acceptance

## Scope

This document freezes the acceptance surface for the **v1.2 failure attribution layer** built on top of the existing PIB product shell and benchmark core.

It does **not** change:

- frozen benchmark scoring semantics for `v1.1.0-rc1`
- benchmark core runners or scorers in `eval/`
- release artifacts under `release/`
- canonical result artifacts under `results/`

It does add a new interpretation layer in the product/API projection chain so the system can distinguish:

- `bridge / infra`
- `protocol / compliance`
- `capability / clinical process`

The acceptance target is **explainability**, not a new leaderboard.

## Frozen Rules

- Keep `v1.1.0-rc1` frozen artifacts unchanged.
- Keep headline `top1/top3/top5` semantics unchanged.
- Keep `oracle_final_*` strictly supplemental.
- Keep failure attribution in the projection/report layer only.

## Evidence Run To Preserve

Use this completed dynamic run as the canonical acceptance example:

- `run_20260309_050053_f3a6c6a0`

This run is the reference object for:

- summary three-part scoring
- failure attribution
- expanded slices
- case-level attribution
- replay rendering

## Expected Summary Surface

`GET /api/runs/:runId/summary` must return, for a completed dynamic run:

- `process_score`
- `compliance_score`
- `final_diagnosis_score`
- `failure_attribution`
- `supplemental`

For the preserved evidence run, the projection should satisfy:

- `state = ready`
- `process_score` is non-empty
- `compliance_score` is non-empty
- `final_diagnosis_score` is non-empty
- `failure_attribution` is present
- `supplemental.oracle_final_metrics` is present

Direct verification example:

```bash
python - <<'PY'
from pathlib import Path
from webapi.routes import runs as run_routes

repo = Path('/Users/xie/Documents/New project')
status, payload = run_routes.get_run_summary('run_20260309_050053_f3a6c6a0', repo_root=repo)
print(status, payload['state'])
print(bool(payload['process_score']))
print(bool(payload['compliance_score']))
print(bool(payload['final_diagnosis_score']))
print(bool(payload['failure_attribution']))
print(bool(payload['supplemental']))
PY
```

## Expected Failure Attribution Semantics

The projection layer must keep these three sources distinct:

- `bridge`
- `protocol`
- `capability`

The system must be able to explain:

- bridge-affected failures
- protocol/compliance failures
- capability/process failures

At summary level:

- `failure_attribution.failure_source_counts` must be present

At case level:

- `failure_analysis.failure_sources.bridge`
- `failure_analysis.failure_sources.protocol`
- `failure_analysis.failure_sources.capability`

## Expected Slices Surface

`GET /api/runs/:runId/slices` must include the following groups:

- `by_module`
- `by_label`
- `by_ambiguity`
- `by_required_svcl_domains_count`
- `by_failure_bucket`
- `by_failure_source`
- `by_risk_positive`
- `by_personality_spectrum`
- `by_timeout_affected`
- `by_parse_affected`
- `by_protocol_clean_only`

For the preserved evidence run, these groups must all be present and queryable.

Direct verification example:

```bash
python - <<'PY'
from pathlib import Path
from webapi.routes import cases as case_routes

repo = Path('/Users/xie/Documents/New project')
status, payload = case_routes.get_run_slices('run_20260309_050053_f3a6c6a0', repo_root=repo)
print(status, payload['state'])
print(sorted(payload['slices'].keys()))
PY
```

## Expected Case Detail Surface

`GET /api/runs/:runId/cases/:caseId` must return:

- `case_meta`
- `run_output`
- `failure_analysis`
- `dynamic_replay`

And specifically:

- `failure_analysis.failure_sources`
- `failure_analysis.missing_must_ask_slots`
- `failure_analysis.missing_svcl_domains`
- `dynamic_replay.available`
- `dynamic_replay.turns`
- `dynamic_replay.final_output`

Replay may be unavailable, but that must degrade to `partial` rather than a server error.

For the preserved evidence run and case `PIB_0013`:

- `state = ready`
- `failure_sources.bridge = clean`
- `failure_sources.protocol = clean`
- `failure_sources.capability = affected`
- `dynamic_replay.available = true`

Direct verification example:

```bash
python - <<'PY'
from pathlib import Path
from webapi.routes import cases as case_routes

repo = Path('/Users/xie/Documents/New project')
status, payload = case_routes.get_run_case_detail('run_20260309_050053_f3a6c6a0', 'PIB_0013', repo_root=repo)
print(status, payload['state'])
print(payload['failure_analysis']['failure_sources'])
print(payload['dynamic_replay']['available'])
PY
```

## UI Acceptance

### Run Summary

The page must visibly separate:

- Process score
- Structure / compliance score
- Final diagnosis score
- Failure attribution
- Supplemental oracle-finalization

### Slice Analysis

The page must visibly expose:

- failure-source slices
- protocol-clean-only slices
- risk-positive slices
- personality-spectrum slices

### Case Detail

The page must visibly expose:

- bridge/protocol/capability attribution
- missing must-ask slots
- missing SVCL domains
- chat-style replay
- `FINAL` summary card

## Regression Requirements

These test suites must stay green:

```bash
python -m unittest \
  tests.test_webapi_run_summary_routes \
  tests.test_webapi_case_projection_routes \
  tests.test_product_slice_failure_loop -v
```

And the full suite must remain green:

```bash
python -m scripts.run_tests
```

## Non-Goals

This layer does **not** do the following:

- rewrite benchmark scoring
- rewrite benchmark core runners
- replace formal leaderboard metrics
- promote `oracle_final_*` into official benchmark score
- add new product pages
- add export or public-share features

## Release Note Guidance

When presenting this layer externally, use wording like:

> PIB now distinguishes process quality, protocol/compliance quality, and final diagnosis quality in dynamic runs, while preserving the frozen `v1.1.0-rc1` benchmark score semantics.

Avoid wording like:

> PIB changed the benchmark score.

