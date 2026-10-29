# PIB Benchmark (DSM-5-TR Psychiatric Interview Benchmark)

PIB 是一个面向研究评测的精神科诊断性访谈 benchmark，覆盖：
- Static 任务：文本 -> slot 抽取 -> 鉴别诊断
- Dynamic 任务：`ASK(slot_id)` 结构化问诊 -> `FINAL` 输出

当前发布冻结候选版本：
- `BENCHMARK_VERSION = 1.1.0-rc1`
- `SCORING_POLICY_VERSION = 1.1.0-rc1`
- `cases_sha256 = d2816dbeb52b88aa4d8316c58594b4287397606f34e3cf3694d91b094a2ab809`
- `rubrics_sha256 = a30e9ea50e890bacad83e91ba1768cd8da334d41244c64867b4b8ec235505587`
- `splits_sha256 = 3f8bc6de50792df3a8ef210e92eefdcc2d4245787add8679a26f822086645dd5`
- 完整冻结清单见 [`release/benchmark_manifest.json`](/Users/xie/Documents/New%20project/release/benchmark_manifest.json)

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install -e .
```

校验数据契约：

```bash
python -m scripts.validate_all \
  --cases data/cases.jsonl \
  --rubrics data/rubrics.jsonl \
  --ontology ontology/
```

运行 dynamic benchmark（DummyDoctor，默认只跑 `test` split）：

```bash
python -m eval.run_dynamic \
  --split test \
  --output results/dynamic/test_dynamic.jsonl
```

运行 dynamic LLM baseline（OpenAI API，默认只跑 `test` split）：

```bash
OPENAI_API_KEY=... python -m eval.run_dynamic \
  --doctor llm \
  --provider openai \
  --model gpt-4o-mini \
  --split test \
  --output results/dynamic/openai_test_dynamic.jsonl
```

运行 dynamic LLM baseline（Anthropic API）：

```bash
ANTHROPIC_API_KEY=... python -m eval.run_dynamic \
  --doctor llm \
  --provider anthropic \
  --model claude-3-5-sonnet-latest \
  --split test \
  --output results/dynamic/anthropic_test_dynamic.jsonl
```

运行 dynamic LLM baseline（本地 OpenAI-compatible 服务，如 vLLM / llama.cpp）：

```bash
python -m eval.run_dynamic \
  --doctor llm \
  --provider local_llama \
  --endpoint http://localhost:8000/v1/chat/completions \
  --model local-llama \
  --split test \
  --output results/dynamic/local_llama_test_dynamic.jsonl
```

运行 static benchmark（rule heuristic，默认只跑 `test` split）：

```bash
python -m eval.run_static \
  --split test \
  --output results/static/test_static.jsonl
```

运行 static LLM baseline（两阶段：slot filling -> ddx）：

```bash
OPENAI_API_KEY=... python -m eval.run_static \
  --mode llm \
  --provider openai \
  --model gpt-4o-mini \
  --input-variant self_report \
  --split test \
  --output results/static/openai_test_static.jsonl
```

从表格模板编译数据：

```bash
python -m scripts.build_cases \
  --template authoring/cases_template.csv \
  --cases-out data/cases.jsonl \
  --rubrics-out data/rubrics.jsonl
```

生成 `110` 例 seed casebank 并编译：

```bash
python -m scripts.generate_seed_casebank --output authoring/pilot_casebank_v11.csv
python -m scripts.build_cases \
  --template authoring/pilot_casebank_v11.csv \
  --cases-out data/cases.jsonl \
  --rubrics-out data/rubrics.jsonl
python -m scripts.build_splits --cases data/cases.jsonl --ontology ontology --out-dir data/splits
```

运行测试：

```bash
python -m scripts.run_tests
```

启动 localhost 控制台：

```bash
python -m scripts.serve_localhost --host 127.0.0.1 --port 8765
```

然后在浏览器访问：

```text
http://127.0.0.1:8765/
```

常用本地验证接口：
- `http://127.0.0.1:8765/api/status`
- `http://127.0.0.1:8765/api/manifest`
- `http://127.0.0.1:8765/api/static`
- `http://127.0.0.1:8765/api/dynamic`
- `http://127.0.0.1:8765/api/audits`
- `http://127.0.0.1:8765/api/baselines`

一键验收：

```bash
python -m scripts.check_all --cases data/cases.jsonl --rubrics data/rubrics.jsonl --ontology ontology --config pib_config.yaml
```

冻结 release manifest：

```bash
python -m scripts.freeze_release
python -m scripts.freeze_release --check
```

LLM adapter 缓存：

```text
cache/<model_name>/<prompt_hash>.json
```

同一模型、同一消息、同一 temperature 会命中同一个缓存文件，便于离线复核与重复实验复现。

`eval.run_dynamic` 的 LLM 参数：
- `--doctor llm`
- `--provider openai|anthropic|local_llama`
- `--model <provider model id>`
- `--endpoint <override base url or local endpoint>`
- `--cache-root <dir>`
- `--no-cache`
- `--temperature <float>`

`eval.run_static` 的 LLM 参数：
- `--mode llm`
- `--provider openai|anthropic|local_llama`
- `--model <provider model id>`
- `--endpoint <override base url or local endpoint>`
- `--cache-root <dir>`
- `--no-cache`
- `--temperature <float>`
- `--oracle-slots` 可跳过 slot filling，直接做 ddx ablation

每次 runner 执行都会在输出文件同名目录下创建独立 run artifact 目录，例如：

```text
results/static/test_static.jsonl
results/static/test_static/run_001/predictions.jsonl
results/static/test_static/run_001/summary.csv
results/static/test_static/run_001/metrics.json
results/static/test_static/run_001/stage_breakdown.csv
```

再次运行同一命令会创建 `run_002/`，不会覆盖前一次的 `predictions.jsonl` / `summary.csv` / `summary.tex` / `metrics.json`。

`metrics.json` 是 canonical 汇总产物，包含：
- `release`（benchmark/scoring 版本与 dataset/scoring/cases/rubrics/splits 哈希）
- `task`
- `n_cases`
- `run_config`
- `artifacts`
- `summary`
- `static_stage_breakdown`（仅 static）

`summary.csv` 现在额外按阶段汇总：
- `slot_stage_error_rate`
- `slot_stage_success_rate`
- `ddx_stage_error_rate`
- `ddx_stage_success_rate`
- `predicted_slot_count`
- `diagnosis_count`

`results/reports/static_stage_breakdown.csv` 提供更细的 failure buckets：
- `label`
- `ambiguity`
- `input_variant`
- `mode`

对应的论文表输出：
- `results/reports/tables_static_stage.tex`

## v1.2 Failure Attribution Layer

当前 workspace 额外提供一层 **v1.2 dev-only failure attribution / layered scoring projection**。这层能力：

- 不修改 frozen `v1.1.0-rc1` benchmark score semantics
- 不回写 canonical release artifacts
- 只在产品/API projection 层解释 dynamic 失败

主要新增视角：

- `process_score`
- `compliance_score`
- `final_diagnosis_score`
- `failure_attribution`
- supplemental `oracle_final_*`

新增 slices：

- `by_failure_source`
- `by_risk_positive`
- `by_personality_spectrum`
- `by_timeout_affected`
- `by_parse_affected`
- `by_protocol_clean_only`

推荐使用这个真实 completed dynamic run 做验收与演示：

- `run_20260309_050053_f3a6c6a0`

更完整的 v1.2 验收口径见：

- [`docs/V1_2_FAILURE_ATTRIBUTION_ACCEPTANCE.md`](/Users/xie/Documents/New%20project/docs/V1_2_FAILURE_ATTRIBUTION_ACCEPTANCE.md)

## Hard Constraints

- `slot_count` 固定为 `120`（`ontology/slots.yaml` 与 `pib_config.yaml` 强校验）
- `dynamic.max_turns` 全局上限固定为 `15`（rubric 不能超过）
- `OS_OCRD` 必须提供 `label_subtype`，且 subtype 仅允许：
  - `OS_OCRD_BFRB`
  - `OS_OCRD_JEAL`
  - `OS_OCRD_OTHER`

## Baseline Groups

pure baseline 主表只保留 no-oracle baseline：
- `static_heuristic`
- `dynamic_dummy`

guided LLM baseline 已从 pure baseline 主表拆出，单独汇报：
- [`results/reports/pure_baselines.csv`](/Users/xie/Documents/New%20project/results/reports/pure_baselines.csv)
- [`results/reports/guided_llm_baselines.csv`](/Users/xie/Documents/New%20project/results/reports/guided_llm_baselines.csv)
- [`results/reports/baseline_groups.json`](/Users/xie/Documents/New%20project/results/reports/baseline_groups.json)

pre-no-oracle-fix 的 dynamic dummy 结果已废弃：
- [`results/reports/deprecated_results.json`](/Users/xie/Documents/New%20project/results/reports/deprecated_results.json)
- 例如 [`results/dynamic/test_dynamic/run_001/DEPRECATED.txt`](/Users/xie/Documents/New%20project/results/dynamic/test_dynamic/run_001/DEPRECATED.txt)

## No-Oracle And Contamination Audits

- no-oracle baseline 审计：[`results/audit/no_oracle_baselines.json`](/Users/xie/Documents/New%20project/results/audit/no_oracle_baselines.json)
  - 证明 `allowed_slots` 是全局 ontology 列表，非 case-specific 裁剪
- 文本污染扫描：[`results/audit/text_contamination_scan.json`](/Users/xie/Documents/New%20project/results/audit/text_contamination_scan.json)
  - 当前结果：`contaminated_case_count = 0`

## Repository Layout

- `ontology/`: labels / slots / SVCL 映射
- `data/`: casebank 与 rubrics
- `agents/`: patient 与 doctor
- `models/`: 适配器与 JSON parsing
- `eval/`: harness、scorers、report
- `scripts/`: 校验、sanity、split
- `results/`: 输出目录
- `tests/`: 单元测试

## P0 Web Product

P0 产品闭环固定为以下页面：

- `/releases`
- `/releases/:releaseId`
- `/runs/new`
- `/runs/:runId`
- `/runs/:runId/slices`
- `/runs/:runId/cases/:caseId`

P0 用户闭环：

```text
/releases
  -> /runs/new
  -> /runs/:runId
  -> /runs/:runId/slices
  -> /runs/:runId/cases/:caseId
```

P0 不包含：

- export
- public share
- 复杂权限
- 高级图表
- raw JSON viewer

### Start P0 WebAPI

```bash
python -m webapi.server --host 127.0.0.1 --port 8780
```

常用接口：

- `http://127.0.0.1:8780/api/releases`
- `http://127.0.0.1:8780/api/releases/v1.1.0-rc1`
- `http://127.0.0.1:8780/api/runs/options`

### Start P0 Frontend

如果本机有 `node` / `npm`：

```bash
cd apps/web
npm install
npm run dev
```

如果当前机器没有 `node` / `npm`，可直接用 WebAPI 做 API 级演示与验收。

### P0 Demo Entry

推荐演示对象：

- frozen release: `v1.1.0-rc1`
- completed dynamic run: `run_20260309_050053_f3a6c6a0`
- completed static run: `run_20260309_045551_be9ba6b6`

收口文档：

- [`docs/P0_ACCEPTANCE_CHECKLIST.md`](/Users/xie/Documents/New%20project/docs/P0_ACCEPTANCE_CHECKLIST.md)
- [`docs/P0_DEMO_SCRIPT.md`](/Users/xie/Documents/New%20project/docs/P0_DEMO_SCRIPT.md)
- [`docs/P0_REGRESSION_CHECKLIST.md`](/Users/xie/Documents/New%20project/docs/P0_REGRESSION_CHECKLIST.md)
- [`docs/P0_KNOWN_LIMITATIONS.md`](/Users/xie/Documents/New%20project/docs/P0_KNOWN_LIMITATIONS.md)

## Compliance Notes

- 不在仓库中包含 DSM-5-TR 原文条款。
- 数据应使用合成或去标识化文本。
- 本项目仅用于研究评测，不构成临床建议系统。
