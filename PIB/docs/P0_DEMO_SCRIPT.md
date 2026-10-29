# P0 Demo Script

## 1. Demo Goal

本演示用于证明 PIB Web 产品的 P0 闭环已经成立：

`/releases -> /runs/new -> /runs/:runId -> /runs/:runId/slices -> /runs/:runId/cases/:caseId`

## 2. Demo Setup

### 2.1 Start webapi

```bash
python -m webapi.server --host 127.0.0.1 --port 8780
```

### 2.2 Start frontend (if Node/npm is available)

```bash
cd apps/web
npm install
npm run dev
```

### 2.3 API-only fallback

如果当前机器没有 `node` / `npm`，使用 API 级演示：

- `http://127.0.0.1:8780/api/releases`
- `http://127.0.0.1:8780/api/releases/v1.1.0-rc1`
- `http://127.0.0.1:8780/api/runs/options`
- `http://127.0.0.1:8780/api/runs/:runId`
- `http://127.0.0.1:8780/api/runs/:runId/summary`
- `http://127.0.0.1:8780/api/runs/:runId/slices`
- `http://127.0.0.1:8780/api/runs/:runId/cases`
- `http://127.0.0.1:8780/api/runs/:runId/cases/:caseId`

### 2.4 Recommended demo artifacts

优先演示：

- frozen release: `v1.1.0-rc1`
- completed dynamic run: `run_20260309_050053_f3a6c6a0`
- completed static run: `run_20260309_045551_be9ba6b6`（可选）

## 3. Main Demo Flow

### Step A. Start from releases

1. 打开 `/releases`
2. 说明这里展示 frozen benchmark releases
3. 点击 `v1.1.0-rc1`
4. 展示：
   - manifest
   - bundle
   - reports
   - audits

推荐话术：

- “这里展示的是 frozen benchmark release，而不是可变工作目录。”
- “产品层只读取 manifest、bundle、reports 和 audits，不改变 benchmark 真源。”

### Step B. Create a run

1. 进入 `/runs/new`
2. 选择：
   - `release_id = v1.1.0-rc1`
   - `run_type = dynamic`
   - `provider = baseline`
   - `model_name = dummy`
   - `split_name = test`
3. 提交 run
4. 自动跳转 `/runs/:runId`

推荐话术：

- “这里提交的不是新逻辑，而是对现有 benchmark harness 的产品化编排。”
- “run 仍然由现有 static/dynamic runner 执行，webapi 只做 registry 和 orchestration。”

### Step C. Show run status

1. 若是新 run，展示 `queued / running`
2. 若演示时间有限，直接打开已完成 run
3. 说明：
   - PR3 解决的是 run create + status
   - 这里先看状态流，不讲 case 细节

### Step D. Show summary

在 `/runs/:runId` 展示：

- overall metrics
- baseline compare
- artifact downloads

推荐话术：

- “summary 是从 frozen artifacts 做 projection，不重算 benchmark 语义。”
- “baseline compare 只做 best-effort 对照，不修改 baseline 表。”

### Step E. Enter slices

1. 点击 `View slices`
2. 进入 `/runs/:runId/slices`
3. 展示：
   - by module
   - by label
   - by ambiguity
   - by required SVCL domains count
   - by failure bucket

推荐话术：

- “这里不是重新评分，而是对已完成 run 的 per-case artifacts 做聚合投影。”
- “P0 固定只做这几个 slice 维度，不做任意 pivot。”

### Step F. Drill into a failure case

1. 点击 `top1_wrong`
2. 展示过滤后的 case list
3. 点击一个 case，例如 `PIB_0013`
4. 进入 `/runs/:runId/cases/:caseId`
5. 展示：
   - case meta
   - pred/gold 对照
   - failure buckets
   - missing must-ask
   - missing SVCL domains
   - replay

推荐话术：

- “这里的 case detail 是 casebank + rubrics + per-case run artifact 的 join projection。”
- “如果 replay 缺失，会降级成 partial，而不会整页崩溃。”

## 4. Demo Fallbacks

### 4.1 If a new run is still pending

直接打开已完成 run：

- `/runs/run_20260309_050053_f3a6c6a0`

然后继续演示：

- summary
- slices
- case detail

### 4.2 If replay is unavailable for a case

继续展示 partial 语义：

- warning banner
- `Replay unavailable`
- 仍然能看到 case meta / pred-gold / failure buckets

### 4.3 If frontend is unavailable

用 API 级演示替代：

```bash
curl -s http://127.0.0.1:8780/api/releases
curl -s http://127.0.0.1:8780/api/releases/v1.1.0-rc1
curl -s http://127.0.0.1:8780/api/runs/run_20260309_050053_f3a6c6a0/summary
curl -s http://127.0.0.1:8780/api/runs/run_20260309_050053_f3a6c6a0/slices
curl -s 'http://127.0.0.1:8780/api/runs/run_20260309_050053_f3a6c6a0/cases?failure_bucket=top1_wrong&limit=5&offset=0'
curl -s http://127.0.0.1:8780/api/runs/run_20260309_050053_f3a6c6a0/cases/PIB_0013
```

## 5. Key Messages To Say Out Loud

- “产品层是 benchmark 的外壳，不是第二个 benchmark core。”
- “所有 validate、freeze、run、summary、slice、case detail 都依赖现有 benchmark core 和 frozen artifacts。”
- “SQLite 只保存 release/run/job 状态索引，不保存 canonical dataset truth。”
- “summary、slices、case detail 都是 best-effort projection；缺失时返回 partial，不伪造数据。”
