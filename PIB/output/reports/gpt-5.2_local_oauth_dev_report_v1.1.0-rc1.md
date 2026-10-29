# GPT-5.2 Local OAuth Dev Evaluation Report

## Scope
- Benchmark release: `v1.1.0-rc1`
- Evaluation mode: dynamic-first
- Execution path: local product shell + local OAuth bridge (`gpt_oauth`)
- This is a **development environment report**, not a canonical frozen benchmark submission.

## Runs Included

### 1. Dynamic subset run
- Run type: `dynamic`
- Model: `gpt-5.2`
- Provider path: `gpt_oauth -> local OpenAI-compatible relay`
- Cases: `5` test cases (`PIB_0002`, `PIB_0041`, `PIB_0073`, `PIB_0084`, `PIB_0101`)
- Output root: `results/dynamic/gpt-5.2-devsubset/gpt52_devsubset/run_001/`
- Status: `completed`

### 2. Static subset run
- Run type: `static`
- Model: `gpt-5.2`
- Provider path: `gpt_oauth -> local OpenAI-compatible relay`
- Cases: same 5-case subset
- Output root: `results/static/gpt-5.2-devsubset/gpt52_devsubset_static/run_001/`
- Status: `completed`

### 3. Dynamic full test run
- Run type: `dynamic`
- Model: `gpt-5.2`
- Scope: full frozen `test` split (`22` cases)
- Product run id: `run_20260310_053508_ae44c89b`
- Status: `failed`
- Failure mode: local relay request timeout after `4/22` cases
- Job log: `artifacts/jobs/job_20260310_053508_6c2e450d/`

## Headline Results

| Model | Provider | Run Type | Scope | Status | Must-Ask Hit Rate | SVCL Coverage | Top-1 Acc | Top-3 Cov | Turns | Harm Flags |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| gpt-5.2 | gpt_oauth | dynamic | 5-case subset | completed | 0.84 | 0.85 | 0.00 | 0.00 | 4.6 | 0.00 |
| gpt-5.2 | gpt_oauth | static | same 5-case subset | completed | - | 0.57 | 1.00 | 1.00 | - | 0.00 |
| gpt-5.2 | gpt_oauth | dynamic | full test split | failed | - | - | - | - | - | - |

## Main Finding
The strongest signal in this development evaluation is **dynamic/static divergence**:
- On the same 5-case subset, `gpt-5.2` is **perfect in static diagnosis ranking** (`top1_acc = 1.0`, `top3_cov = 1.0`).
- On dynamic interviewing, `gpt-5.2` shows **good evidence collection** (`must_ask_hit_rate = 0.84`, `svcl_coverage = 0.85`) but **collapsed final scoring output** (`top1_acc = 0.0`, `top3_cov = 0.0`).

This means the current local GPT path is not primarily failing at reading the case. It is failing at **dynamic structured interview execution and/or final structured output compliance**.

## Dynamic Interpretation

### Strengths
- The model frequently asks clinically relevant questions.
- Required evidence domains were often covered well.
- No harm flags were triggered in the completed subset run.
- Average turn count (`4.6`) remained efficient.

### Weaknesses
- All 5 completed dynamic subset cases ended with `top1_acc = 0.0` and `top3_cov = 0.0`.
- Every subset case showed `parse_or_execution_error` behavior at the case level.
- Several cases fell back to default `OTHER` because the final response was not consumable as a valid structured benchmark output.

### Failure pattern
Dominant dynamic failure buckets on the 5-case subset:
- `top1_wrong`: 5/5
- `top3_miss`: 5/5
- `parse_or_execution_error`: 5/5
- `must_ask_miss`: 1/5
- `svcl_coverage_gap`: 1/5

Interpretation:
- The model often gathered enough information to support diagnosis,
- but the benchmark-facing dynamic output path remained brittle,
- especially under strict JSON/action compliance.

## Representative Cases

### Case A: `PIB_0002` (OCRD / OCD, ambiguous)
- `must_ask_hit_rate = 1.0`
- `svcl_coverage = 1.0`
- `top1_acc = 0.0`
- `top3_cov = 0.0`
- termination: `repeat_slot`
- parse flag: `true`

Interpretation:
- Interview content was clinically on target.
- The model still failed the benchmark outcome because it repeated a slot and the final output degraded to benchmark-invalid behavior.
- This is evidence of **process-control weakness**, not simple diagnostic ignorance.

### Case B: `PIB_0041` (PD / BPD, ambiguous, suicide-positive)
- `must_ask_hit_rate = 0.2`
- `svcl_coverage = 0.25`
- `top1_acc = 0.0`
- `top3_cov = 0.0`
- termination: `repeat_slot`
- parse flag: `true`

Interpretation:
- This is the highest-risk subset case and also the weakest dynamic interviewing case.
- The model did ask self-harm related content, but coverage remained narrow and did not adequately complete the broader structured evidence picture.
- This suggests the current local GPT setup is especially fragile on **high-risk, personality-spectrum interview structure**.

## Static vs Dynamic

This is the most important conclusion from the current run pair.

### Static (`completed`)
- `top1_acc = 1.0`
- `top3_cov = 1.0`
- `top5_cov = 1.0`
- No parse-stage failure

### Dynamic (`completed subset`)
- `must_ask_hit_rate = 0.84`
- `svcl_coverage = 0.85`
- `top1_acc = 0.0`
- `top3_cov = 0.0`
- Parse/execution failures in all 5 cases

Interpretation:
- `gpt-5.2` appears capable of reasoning from already-available text.
- The main weakness is not static diagnosis.
- The main weakness is **operating inside PIB's dynamic structured interview loop**.

## Full Test Run Failure
The full 22-case dynamic run failed after 4 completed cases.

Observed failure:
- `TimeoutError` while the core adapter was waiting for the local OAuth relay.

Interpretation:
- This is a **local dev infrastructure stability issue**, not direct evidence that `gpt-5.2` cannot complete the benchmark.
- The subset run demonstrates that the relay path works.
- The full run demonstrates that the current bridge is not yet stable enough for a full test-split batch on this machine/session.

## Practical Conclusion
For **local development evaluation**:
- `gpt-5.2` is already usable enough to validate end-to-end PIB integration.
- It can complete both static and dynamic subset runs through the local OAuth bridge.
- Its current strongest signal is: **good evidence gathering, weak benchmark-structured dynamic completion robustness**.

For **benchmark reporting**:
- Do **not** treat this as a canonical frozen benchmark result.
- Treat it as a dev-environment capability report for the `gpt_oauth` path.

## Recommended Next Step
1. Stabilize the local OAuth relay for long multi-case dynamic runs.
2. Re-run full `test` split dynamic.
3. Keep the same static subset/static full control for comparison.
4. If dynamic output compliance remains the main issue, focus on prompt/adapter formatting robustness rather than pure diagnosis quality.
