# 任务：用 WorkBuddy 免密钥多模型 LLM 跑完 PIB baseline 测试

> 下面是一份自包含任务简报。复制全部内容发给一个**上下文空白**的 WorkBuddy（企业版账号，已接入 GPT/Claude/Gemini 等模型），它应能独立理解并完成。

## 目标
在 PIB 基准项目里，用 WorkBuddy 自带的 cloud-service LLM 接口（免密钥、可指定模型名）作为模型后端，重跑论文里的 9 个前沿 LLM baseline（覆盖 dynamic 任务），并把结果以"三列拆分"格式填回论文表格。
企业版账号的 cloud-service 模型目录包含 GPT / Claude / Gemini / DeepSeek 等，足以覆盖原论文 9 个 baseline。

## 项目结构（关键文件）
- 评测入口：`PIB/eval_model.py`
- 模型适配器目录：`PIB/models/adapters/`，现有 `openai_chat.py`、`anthropic.py`，由 `PIB/models/adapters/factory.py` 按 `--provider` 分发。
- 评测数据：`PIB/data/cases.jsonl`（已清洗的 110 个独立病例，可直接测）。
- 评分准则：`PIB/data/rubrics.jsonl`。

## 执行步骤（按顺序）

**1. 激活 cloud-service 拿到 applicationId**
调用 cloud-service 激活（action=activate），为当前 PIB 项目创建一个应用，记下返回的 `applicationId`（格式 `wbapp_xxx`）。该 id 与账号+项目绑定，本任务全程复用。
> 提示：可先加载 `cloud-service` 技能查看 LLM 模块用法与参数 schema。

**2. 列出可用模型，确认 baseline 阵容**
调用 `workbuddy_cloudservice_llm_list_models(applicationId)`，从返回目录中挑出原论文的 9 个 baseline 对应模型 id（GPT 系列 / Claude 系列 / Gemini 系列 / DeepSeek 等）。记下它们的 id。

**3. 新增 WorkBuddy 适配器**
在 `PIB/models/adapters/` 新建 `workbuddy.py`，实现与 `openai_chat.py` 相同的 `ChatAdapter` 接口（方法签名保持一致，factory 才能统一调用）。内部实现：调用 `workbuddy_cloudservice_llm_chat`，入参包含：
- `model`：步骤 2 记下的模型 id
- `messages`：对话历史
- `response_format`: `{ "type": "json_object" }`（**必须支持**，这是解决原 9 个 baseline 全 0% 的关键）
- `temperature`：按论文设定（建议 0）
- `stream`: `true`（**接口强制要求流式**）
解析流式/SSE 返回，提取 `content` 字段作为模型回复。
然后在 `factory.py` 注册 `workbuddy` 这个 provider，使其可被 `--provider workbuddy` 选中。

**4. 批量跑 9 个 baseline（全部跑满 110 例）**
对步骤 2 挑出的每个 baseline 模型，执行：
```
python PIB/eval_model.py --provider workbuddy --model <模型id> --application-id <appId> --mode dynamic
```
务必**全部在 110 例上跑**（不要只跑 22 例），以关闭审稿人提出的"SSM 跑 110、baseline 只跑 22"样本不对称争议。
> 若单次运行易中断，写成循环脚本（bash 或 python），逐个模型串行跑，结果分别落盘到 `PIB/results/dynamic/<model_id>.jsonl`。

**5. 表格改造（必做，否则重跑白做）**
原 `tab:dynamic` 里 9 个 baseline 因 JSON 校验失败全是 0%。拿到真实返回后，把 dynamic Top-1 拆成三列：
- `Format Compliance`：schema 通过率
- `Dx-Correct|Valid`：仅在 schema 合规输出上算诊断正确率
- `Dx-Correct (unconstrained)`：在全部 110 例上算
把 9 个 baseline + SSM 都填入这三列，替换原 0% 占位。

**6. 同步论文数字**
将新分数同步到 `论文/main (3).tex` 的摘要、评估协议段、CF 段、Summary、Conclusion、消融表（所有 83.6 / 93.8 / 10.9 / 89.1 / 93.9 等数字按真实结果更新）。

## 关键约束 / 坑
- `stream: true` 是接口硬要求，缺了会报错。
- cloud-service 目录里很多模型是 **reasoning / thinking 模型**，临床诊断任务要关闭 thinking 或调低 effort，否则输出风格和速度异常。
- `applicationId` 换账号/换项目需重新激活获取。
- 9 个 baseline 必须全跑满 110 例，不能沿用旧 22 例子集。

## 交付物
1. `PIB/models/adapters/workbuddy.py` + `factory.py` 注册
2. `PIB/results/dynamic/<model_id>.jsonl`（9 个 baseline 各一份）
3. 更新后的 `tab:dynamic`（三列拆分，无 0% 占位）
4. `论文/main (3).tex` 数字同步
