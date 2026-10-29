# CHANGELOG

## 1.1.0-rc1

### Benchmark Freeze
- 冻结 `BENCHMARK_VERSION = 1.1.0-rc1`
- 冻结 `SCORING_POLICY_VERSION = 1.1.0-rc1`
- 冻结 release manifest、dataset hash、scoring hash、cases/rubrics/splits SHA256
- 增加 `requirements.lock` 并纳入 release manifest

### Evaluation And Scoring
- ambiguous case 主评分改为 ambiguity-aware：主评分接受 `gold_ddx_top5[:3]`，同时保留 strict 单 gold 指标
- 新增 canonical `metrics.json`，作为每次 run 的标准汇总产物
- 修复 artifact 覆盖问题：每次 run 写入独立 `run_xxx/` 目录
- runner 默认按 `test` split 运行，避免整库混跑

### Safety And Rubrics
- 补齐 suicide / violence 阳性 case 的高风险 must-ask slot
- safety scorer 新增漏问高风险 slot 的处罚逻辑
- 扩充 psychosis / substance 阳性风险样本覆盖

### Baselines
- 修复 dynamic dummy 的 no-oracle 泄漏问题，不再向 dummy 传入 `rubric.must_ask_slots`
- 确认 static heuristic 与 dynamic dummy 只接收 no-oracle 运行时输入
- 将 guided LLM baseline 从 pure baseline 主表中拆出，单独汇报
- 将 pre-no-oracle-fix 的 dynamic dummy 结果标记为 deprecated

### Audits
- 新增 no-oracle baseline 审计，证明 `allowed_slots` 为全局 ontology 列表，而非 case-specific 裁剪
- 新增文本污染扫描，检查 `minimal_cc / self_report / chart_full / patient_script` 中是否直接出现 gold label 或 gold ddx 标签名
- 当前文本污染扫描结果为 `0` 命中

### Release Materials
- 生成 release candidate bundle：`release/PIB-Benchmark-v1.1.0-rc1/`
- 收录 manifest、README、DATASET_CARD、lockfile、baseline tables、audit reports、canonical metrics 与 predictions
