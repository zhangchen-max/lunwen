# DATASET_CARD

## Release Identity

- Benchmark version: `1.1.0-rc1`
- Dataset version: `1.1.0-rc1`
- Scoring policy version: `1.1.0-rc1`
- No-oracle policy version: `1.1.0-rc1`
- Release manifest: [`release/benchmark_manifest.json`](/Users/xie/Documents/New%20project/release/benchmark_manifest.json)
- Runtime lockfile: [`requirements.lock`](/Users/xie/Documents/New%20project/requirements.lock)

## Frozen Hashes

- Dataset hash (`SHA256`): `c42e6f02ba2c749a74888f99a07ad1d7e0267a9b35e698cb4400882cf3792c5e`
- Scoring hash (`SHA256`): `e08ed5d9c5026ed2b7336f4f683d62d61656ca3fb0742c223f8e2793f328533b`
- Lockfile hash (`SHA256`): `ca0ee9e0f9f1b796ef127929204a354d6692d2500d4397dc119c887bf465ab8b`
- Cases hash (`SHA256`): `d2816dbeb52b88aa4d8316c58594b4287397606f34e3cf3694d91b094a2ab809`
- Rubrics hash (`SHA256`): `a30e9ea50e890bacad83e91ba1768cd8da334d41244c64867b4b8ec235505587`
- Splits hash (`SHA256`): `3f8bc6de50792df3a8ef210e92eefdcc2d4245787add8679a26f822086645dd5`

哈希来源：
- [`release/benchmark_manifest.json`](/Users/xie/Documents/New%20project/release/benchmark_manifest.json)

## Overview

- Name: PIB CaseBank
- Purpose: 评测 LLM 在 DSM-5-TR 相关诊断性访谈中的结构化能力
- Current size: `110` synthetic cases / `110` rubrics
- Hard parameters:
  - `slot_count=120`
  - `dynamic_max_turns_cap=15`
  - `OS_OCRD subtype count=3`

## Label Space

- ADJ, PGD, OCD, BDD, OS_OCRD, SSD, PMDD, IED, BPD, OCPD, OTHER

## Current Distribution

- `110` cases total
- `10` cases per label
- `44 ambiguous / 66 unambiguous`
- OS_OCRD subtype coverage:
  - `OS_OCRD_BFRB` x4
  - `OS_OCRD_JEAL` x4
  - `OS_OCRD_OTHER` x2

## Risk Coverage

- `suicide_positive = 4`
- `violence_positive = 10`
- `psychosis_positive = 2`
- `substance_positive = 2`

高风险 rubric 现在要求风险阳性 case 覆盖对应风险 slot，校验入口：
- [`scripts/validate_all.py`](/Users/xie/Documents/New%20project/scripts/validate_all.py)
- [`eval/load.py`](/Users/xie/Documents/New%20project/eval/load.py)

## Data Fields

每个病例包含：
- `info_variants`: `minimal_cc`, `self_report`, `chart_full`
- `slot_truth`: 真值 slot
- `gold_ddx_top5`: 金标准 top5
- `risk_flags`
- `required_svcl_domains`
- `patient_script`（含 `unknown_default`）

## Rubrics

- `must_ask_slots`
- `must_ask_svcl_domains`
- `avoid_harm_rules`
- `stop_rules.max_turns`

## Scoring Policy

- ambiguous case 主评分使用 `gold_ddx_top5[:3]` 作为 accepted gold set
- strict 单 gold 分数仍保留为 `strict_top1_acc / strict_top3_cov / strict_top5_cov`
- 主评分字段为 `top1_acc / top3_cov / top5_cov`
- safety 规则包含：
  - `overconfident_dx`
  - `prescriptive_treatment`
  - `missing_high_risk_*`

评分实现：
- [`eval/scorers/ddx_metrics.py`](/Users/xie/Documents/New%20project/eval/scorers/ddx_metrics.py)
- [`eval/scorers/static_metrics.py`](/Users/xie/Documents/New%20project/eval/scorers/static_metrics.py)
- [`eval/scorers/dynamic_metrics.py`](/Users/xie/Documents/New%20project/eval/scorers/dynamic_metrics.py)
- [`eval/scorers/safety_rules.py`](/Users/xie/Documents/New%20project/eval/scorers/safety_rules.py)

## No-Oracle Baselines

- 审计文件：[`results/audit/no_oracle_baselines.json`](/Users/xie/Documents/New%20project/results/audit/no_oracle_baselines.json)
- 测试文件：[`tests/test_no_oracle_baselines.py`](/Users/xie/Documents/New%20project/tests/test_no_oracle_baselines.py)
- 当前结论：`static heuristic` 与 `dynamic dummy` 均不接收以下字段作为运行时输入：
  - `case.label`
  - `gold_ddx_top5`
  - `rubrics.must_ask_slots`
  - `slot_truth`
  - `risk_flags`

当前 no-oracle 测试结果：
- `python -m scripts.run_tests` -> `Ran 35 tests`, `OK`
- `allowed_slots` 审计结果：
  - `expected_slot_count = 120`
  - `matches_global_ontology_for_all_contexts = true`
  - `case_specific_cropping_detected = false`

## Baseline Grouping

- pure baseline 主表：
  - [`results/reports/pure_baselines.csv`](/Users/xie/Documents/New%20project/results/reports/pure_baselines.csv)
- guided LLM baseline 单独汇报：
  - [`results/reports/guided_llm_baselines.csv`](/Users/xie/Documents/New%20project/results/reports/guided_llm_baselines.csv)
- baseline 分组总清单：
  - [`results/reports/baseline_groups.json`](/Users/xie/Documents/New%20project/results/reports/baseline_groups.json)
- 已废弃 pre-no-oracle-fix dynamic dummy 结果：
  - [`results/reports/deprecated_results.json`](/Users/xie/Documents/New%20project/results/reports/deprecated_results.json)

## Text Contamination Audit

- 审计文件：[`results/audit/text_contamination_scan.json`](/Users/xie/Documents/New%20project/results/audit/text_contamination_scan.json)
- 扫描范围：
  - `info_variants.minimal_cc`
  - `info_variants.self_report`
  - `info_variants.chart_full`
  - `patient_script.*`
- 当前结果：
  - `contaminated_case_count = 0`
  - `hit_count = 0`

## Reproducibility

- release manifest 冻结 benchmark version / scoring policy version / dataset hash / lockfile hash
- canonical metrics artifact:
  - `results/static/<name>/run_xxx/metrics.json`
  - `results/dynamic/<name>/run_xxx/metrics.json`
- 每次 runner 执行都会创建独立 `run_xxx/` 目录，避免覆盖

## Safety and Compliance

- 文本为合成/去标识化示例
- 禁止输出处方、剂量、治疗承诺
- 仅用于研究评测，不构成临床建议

## Known Limitations

- 数据仍为合成 casebank，未附 clinician adjudication 记录
- `OS_OCRD_OTHER` 数量仍偏少
- psychosis / substance 风险样本已覆盖，但规模仍然较小
