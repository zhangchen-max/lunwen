# P0 Acceptance Checklist

## 1. Scope Statement

P0 页面范围固定为以下路径：

- `/releases`
- `/releases/:releaseId`
- `/runs/new`
- `/runs/:runId`
- `/runs/:runId/slices`
- `/runs/:runId/cases/:caseId`

说明：

- `/releases/:releaseId` 和 `/runs/:runId` 属于 detail/summary 页，不额外算新的独立产品模块。
- P0 不包含 export、public share、复杂权限、高级图表、raw JSON viewer、slice export、case export、replay export。

## 2. Closed-Loop Acceptance Path

P0 用户闭环必须能完成这条路径：

`/releases`  
→ 查看 frozen release  
→ `/runs/new`  
→ 提交 run  
→ `/runs/:runId`  
→ 查看 summary / baseline / artifacts  
→ `/runs/:runId/slices`  
→ 查看 slices / failure buckets  
→ `/runs/:runId/cases/:caseId`  
→ 查看 case detail / replay

## 3. Page-by-Page Acceptance

### 3.1 Release Center

- [ ] 能显示 frozen release 列表
- [ ] 能进入 release detail
- [ ] 能显示 manifest / bundle / reports / audits
- [ ] 能触发 validate current workspace
- [ ] 能触发 freeze current workspace
- [ ] validate / freeze job 能显示 `queued -> running -> succeeded/failed`
- [ ] 失败时有结构化错误或最小失败提示

### 3.2 New Run Wizard

- [ ] 能读取 releases/options
- [ ] 能提交 static run
- [ ] 能提交 dynamic run
- [ ] 提交后返回 `run_id`
- [ ] 提交后自动跳转 `/runs/:runId`

### 3.3 Run Summary

- [ ] 能显示 run 状态流转
- [ ] completed 时显示 overall metrics
- [ ] completed 时显示 baseline compare
- [ ] completed 时显示 artifact downloads
- [ ] failed 时显示 `error_summary`
- [ ] partial 时显示 partial warning
- [ ] completed/partial 时能进入 `View slices`

### 3.4 Slice Analysis

- [ ] 能显示 `by_module`
- [ ] 能显示 `by_label`
- [ ] 能显示 `by_ambiguity`
- [ ] 能显示 `by_required_svcl_domains_count`
- [ ] 能显示 `by_failure_bucket`
- [ ] 点击 slice 能过滤 case list
- [ ] 点击 failure bucket 能过滤 case list
- [ ] 点击 case row 能进入 case detail

### 3.5 Case Detail

- [ ] 能显示 case meta
- [ ] 能显示 pred/gold 对照
- [ ] 能显示 failure buckets
- [ ] 能显示 missing must-ask slots（若可得）
- [ ] 能显示 missing SVCL domains（若可得）
- [ ] replay 可得时展示 turn timeline
- [ ] replay 不可得时显示 partial/unavailable，不整页崩溃

## 4. Out of Scope

以下内容明确不属于 P0：

- raw JSON drawer
- slice export
- case export
- replay download
- 复杂 auth / RBAC
- 多用户协作
- 远程 job worker
- provider/model 高级参数面板
- 高级图表与 dashboard polishing

## 5. Evidence Checklist

以下证据应可用于 P0 验收：

- `/api/releases`
- `/api/releases/:releaseId`
- `/api/releases/validate-current`
- `/api/releases/freeze-current`
- `/api/runs/options`
- `/api/runs/:runId`
- `/api/runs/:runId/summary`
- `/api/runs/:runId/artifacts`
- `/api/runs/:runId/slices`
- `/api/runs/:runId/cases`
- `/api/runs/:runId/cases/:caseId`

## 6. Acceptance Decision

P0 只有在以下条件同时满足时才算通过：

- [ ] PR1–PR5 相关测试继续通过
- [ ] 至少一条最小闭环 smoke test 可跑
- [ ] 页面与 API 能支撑完整闭环
- [ ] 未引入任何超出 P0 范围的新产品功能
