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

## Compliance Notes

- 不在仓库中包含 DSM-5-TR 原文条款。
- 数据应使用合成或去标识化文本。
- 本项目仅用于研究评测，不构成临床建议系统。
