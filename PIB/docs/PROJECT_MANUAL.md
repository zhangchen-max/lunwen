# PIB 项目说明书

## 1. 项目概述

PIB（Psychiatric Interview Benchmark）是一个面向研究评测的精神科诊断性访谈 benchmark 及其 Web 产品外壳。

项目目标不是提供临床诊断服务，而是为大语言模型提供一套：

- 可冻结的 benchmark 定义
- 可重复运行的 static / dynamic 评测流程
- 可结构化评分的结果体系
- 可在浏览器中完成评测、查看结果、定位失败模式的产品闭环

当前项目已经完成两层能力：

1. `benchmark core`
   - 负责数据契约、病例库、static / dynamic 跑道、评分器与 release 冻结
2. `P0 web product`
   - 负责 release 浏览、run 提交、run summary、slice analysis、case detail / replay

当前冻结 release 为：

- `BENCHMARK_VERSION = 1.1.0-rc1`
- `SCORING_POLICY_VERSION = 1.1.0-rc1`

冻结清单见：

- [`/Users/xie/Documents/New project/release/benchmark_manifest.json`](/Users/xie/Documents/New%20project/release/benchmark_manifest.json)

## 2. 项目定位

PIB 评测的是：

- 模型会不会问
- 是否问到关键问题
- 是否覆盖关键证据域
- 是否在有限轮数内完成合理访谈
- 是否能把访谈结果转成结构化诊断输出

因此，PIB 的主评估任务是 `dynamic run`，而不是 `static run`。

### 2.1 Static 与 Dynamic 的区别

`static`

- 输入：已有患者文本
- 任务：slot 抽取 + 鉴别诊断
- 更像“读完材料后答题”

`dynamic`

- 输入：最小主诉
- 任务：通过 `ASK(slot_id)` 逐轮访谈，再输出 `FINAL`
- 更接近“真实访谈能力”

## 3. 当前用户角色

PIB Web 产品面向三类用户：

1. `Benchmark Maintainer`
   - 冻结 release
   - 校验数据健康度
   - 查看 release manifest / reports / audits

2. `Model Evaluator / Researcher`
   - 提交 static / dynamic run
   - 查看 summary
   - 查看 slices
   - 分析失败 case

3. `External Replicator / Reviewer`
   - 浏览 frozen release
   - 查看结果与 artifacts
   - 核对 benchmark 评测逻辑与输出

## 4. Benchmark Core 组成

### 4.1 Ontology

核心文件：

- [`/Users/xie/Documents/New project/ontology/labels.yaml`](/Users/xie/Documents/New%20project/ontology/labels.yaml)
- [`/Users/xie/Documents/New project/ontology/slots.yaml`](/Users/xie/Documents/New%20project/ontology/slots.yaml)
- [`/Users/xie/Documents/New project/ontology/svcl_domains.yaml`](/Users/xie/Documents/New%20project/ontology/svcl_domains.yaml)
- [`/Users/xie/Documents/New project/ontology/svcl_map.yaml`](/Users/xie/Documents/New%20project/ontology/svcl_map.yaml)

当前冻结硬约束：

- slot 总数必须为 `120`
- dynamic 全局 `max_turns cap = 15`
- `OS_OCRD` subtype 固定为 3 个枚举

### 4.2 CaseBank 与 Rubrics

核心文件：

- [`/Users/xie/Documents/New project/data/cases.jsonl`](/Users/xie/Documents/New%20project/data/cases.jsonl)
- [`/Users/xie/Documents/New project/data/rubrics.jsonl`](/Users/xie/Documents/New%20project/data/rubrics.jsonl)
- [`/Users/xie/Documents/New project/data/splits/train_ids.txt`](/Users/xie/Documents/New%20project/data/splits/train_ids.txt)
- [`/Users/xie/Documents/New project/data/splits/dev_ids.txt`](/Users/xie/Documents/New%20project/data/splits/dev_ids.txt)
- [`/Users/xie/Documents/New project/data/splits/test_ids.txt`](/Users/xie/Documents/New%20project/data/splits/test_ids.txt)

当前数据规模：

- `110` cases
- `110` rubrics
- `22` test cases

### 4.3 Static / Dynamic Harness

核心执行入口：

- [`/Users/xie/Documents/New project/eval/run_static.py`](/Users/xie/Documents/New%20project/eval/run_static.py)
- [`/Users/xie/Documents/New project/eval/run_dynamic.py`](/Users/xie/Documents/New%20project/eval/run_dynamic.py)

Dynamic 动作空间固定为：

- `ASK(slot_id)`
- `FINAL`

这保证了 dynamic 过程可以被结构化评分，而不是自由聊天后事后解释。

### 4.4 Scorers

核心评分模块：

- [`/Users/xie/Documents/New project/eval/scorers/static_metrics.py`](/Users/xie/Documents/New%20project/eval/scorers/static_metrics.py)
- [`/Users/xie/Documents/New project/eval/scorers/dynamic_metrics.py`](/Users/xie/Documents/New%20project/eval/scorers/dynamic_metrics.py)
- [`/Users/xie/Documents/New project/eval/scorers/safety_rules.py`](/Users/xie/Documents/New%20project/eval/scorers/safety_rules.py)
- [`/Users/xie/Documents/New project/eval/scorers/ddx_metrics.py`](/Users/xie/Documents/New%20project/eval/scorers/ddx_metrics.py)

主要指标：

- `top1_acc`
- `top3_cov`
- `top5_cov`
- `must_ask_hit_rate`
- `svcl_coverage`
- `turns`
- `harm_flags_count`

## 5. Web 产品 P0 范围

P0 只包含以下页面闭环：

- `/releases`
- `/releases/:releaseId`
- `/runs/new`
- `/runs/:runId`
- `/runs/:runId/slices`
- `/runs/:runId/cases/:caseId`

闭环路径为：

`/releases`
→ `/runs/new`
→ `/runs/:runId`
→ `/runs/:runId/slices`
→ `/runs/:runId/cases/:caseId`

P0 不包含：

- raw JSON viewer
- slice export
- replay export
- public share
- 复杂权限
- 高级图表
- 多用户协作

## 6. 当前仓库结构

### 6.1 Benchmark Core

- `ontology/`
- `data/`
- `eval/`
- `models/`
- `agents/`
- `scripts/`
- `results/`
- `release/`

### 6.2 Product Layer

- `apps/web/`
- `webapi/`
- `artifacts/`
- `mocks/`

### 6.3 测试

- `tests/`
- `tests/webapi/`
- `tests/product/`

## 7. 当前产品架构原则

### 7.1 冻结边界

以下目录/文件视为 benchmark 真源，不在产品层中重写：

- `ontology/`
- `data/`
- `eval/`
- `models/`
- `agents/`
- `release/`
- `results/`
- `scripts/validate_all.py`
- `scripts/freeze_release.py`
- `scripts/freeze_release_reports.py`

### 7.2 WebAPI 的职责

`webapi/` 只负责：

- projection
- registry
- orchestration

不负责：

- 重写 benchmark 逻辑
- 重算评分
- 改写 benchmark artifacts

### 7.3 SQLite 的职责

`/Users/xie/Documents/New project/artifacts/state.sqlite3`

只存：

- release registry
- jobs
- run registry

不存：

- ontology 真源
- cases / rubrics 真源
- canonical metrics 真值
- release bundle 内容

## 8. 主要运行入口

### 8.1 Benchmark Core CLI

校验：

```bash
python -m scripts.validate_all \
  --cases data/cases.jsonl \
  --rubrics data/rubrics.jsonl \
  --ontology ontology \
  --config pib_config.yaml
```

static：

```bash
python -m eval.run_static \
  --split test \
  --output results/static/test_static.jsonl
```

dynamic：

```bash
python -m eval.run_dynamic \
  --split test \
  --output results/dynamic/test_dynamic.jsonl
```

测试：

```bash
python -m scripts.run_tests
```

### 8.2 WebAPI

启动：

```bash
python -m webapi.server --host 127.0.0.1 --port 8780
```

关键接口：

- `/api/releases`
- `/api/releases/:releaseId`
- `/api/releases/validate-current`
- `/api/releases/freeze-current`
- `/api/runs/options`
- `/api/runs`
- `/api/runs/:runId`
- `/api/runs/:runId/summary`
- `/api/runs/:runId/artifacts`
- `/api/runs/:runId/slices`
- `/api/runs/:runId/cases`
- `/api/runs/:runId/cases/:caseId`

### 8.3 Web 前端

前端目录：

- [`/Users/xie/Documents/New project/apps/web`](/Users/xie/Documents/New%20project/apps/web)

若本机具备 Node.js：

```bash
cd apps/web
npm install
npm run dev
```

默认访问：

- `http://127.0.0.1:4173`

## 9. 结果产物

### 9.1 Release 产物

- [`/Users/xie/Documents/New project/release/benchmark_manifest.json`](/Users/xie/Documents/New%20project/release/benchmark_manifest.json)
- [`/Users/xie/Documents/New project/release/PIB-Benchmark-v1.1.0-rc1`](/Users/xie/Documents/New%20project/release/PIB-Benchmark-v1.1.0-rc1)

### 9.2 Run 产物

每次 run 都会写入独立目录，例如：

- `results/static/<stem>/run_xxx/`
- `results/dynamic/<stem>/run_xxx/`

典型文件：

- `predictions.jsonl`
- `summary.csv`
- `metrics.json`
- `stage_breakdown.csv`（仅 static）

### 9.3 报表产物

- [`/Users/xie/Documents/New project/results/reports/pure_baselines.csv`](/Users/xie/Documents/New%20project/results/reports/pure_baselines.csv)
- [`/Users/xie/Documents/New project/results/reports/guided_llm_baselines.csv`](/Users/xie/Documents/New%20project/results/reports/guided_llm_baselines.csv)
- [`/Users/xie/Documents/New project/results/reports/deprecated_results.json`](/Users/xie/Documents/New%20project/results/reports/deprecated_results.json)

### 9.4 审计产物

- [`/Users/xie/Documents/New project/results/audit/no_oracle_baselines.json`](/Users/xie/Documents/New%20project/results/audit/no_oracle_baselines.json)
- [`/Users/xie/Documents/New project/results/audit/text_contamination_scan.json`](/Users/xie/Documents/New%20project/results/audit/text_contamination_scan.json)

## 10. 当前项目状态

### 10.1 已完成

- frozen benchmark release
- no-oracle baseline 审计
- ambiguity-aware scoring
- high-risk rubric 补齐
- safety scorer 接高风险漏问处罚
- static / dynamic run
- web product P0 闭环
- release / run / summary / slices / case detail 页面链路
- P0 验收文档与演示脚本

### 10.2 当前最适合的用途

这个项目当前最适合做：

- 大模型精神科访谈能力评测
- dynamic-first benchmark 对比
- baseline vs external model 对比
- case-level failure analysis

### 10.3 当前最重要的评测建议

如果要测“访谈能力”，优先跑：

- `dynamic run`

再用 `static run` 做对照，判断模型是：

- 不会问
- 还是不会整合

## 11. 已知限制

### 11.1 数据限制

- casebank 为合成/模板增强数据
- 没有 clinician adjudication 记录
- `OS_OCRD_OTHER` 子集偏少
- psychosis / substance 阳性样本数量仍有限

### 11.2 产品限制

- P0 仍不支持 export / public share / 复杂 auth
- 前端若缺少 Node.js，只能做 API 级演示
- 部分 case detail / replay 依赖 per-case artifacts 完整性，可能以 `partial` 降级返回

### 11.3 评测限制

PIB 测的是：

- 在 frozen release 和固定 scoring policy 下的 benchmark 表现

它不等于：

- 真实临床部署表现
- 临床安全认证
- 真实世界全部能力

## 12. 合规与使用边界

PIB 仅用于研究评测。

禁止将其结果解读为：

- 临床诊断能力证明
- 治疗建议能力证明
- 危机干预能力证明

PIB 不应被用于：

- diagnosis
- triage
- crisis assessment
- treatment selection
- prescribing

## 13. 推荐阅读顺序

如果你第一次接触这个项目，建议按以下顺序读：

1. [`/Users/xie/Documents/New project/README.md`](/Users/xie/Documents/New%20project/README.md)
2. [`/Users/xie/Documents/New project/DATASET_CARD.md`](/Users/xie/Documents/New%20project/DATASET_CARD.md)
3. [`/Users/xie/Documents/New project/docs/P0_ACCEPTANCE_CHECKLIST.md`](/Users/xie/Documents/New%20project/docs/P0_ACCEPTANCE_CHECKLIST.md)
4. [`/Users/xie/Documents/New project/docs/P0_DEMO_SCRIPT.md`](/Users/xie/Documents/New%20project/docs/P0_DEMO_SCRIPT.md)
5. [`/Users/xie/Documents/New project/release/benchmark_manifest.json`](/Users/xie/Documents/New%20project/release/benchmark_manifest.json)

## 14. 一句话总结

PIB 现在不是一个“只看最终诊断结果”的脚本仓库，而是一个围绕 frozen benchmark release 构建的、可在浏览器中完成 `release -> run -> summary -> slices -> case detail` 的标准化 LLM 访谈能力测评台。
