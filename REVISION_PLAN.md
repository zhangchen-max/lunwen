# SSM-Psychiatrist 修改清单与行动计划

> 针对 IEEE BIBM 2026 拒稿（B1563，4 份评审：R1 Weak Reject / R2 Weak Accept / R3 Weak Accept / R4 Reject）
> 制定日期：2026-10-27

---

## 一、现状诊断：改完了"话"，没改"实验"

对比 `原版.txt` 与 `main (3).tex`，已完成的修改**全部是措辞降级（claim softening）**：

| 修改 | 对应意见 |
|---|---|
| "clinical completeness as a formal property" → "procedural coverage w.r.t. an explicit slot taxonomy" | R4-3 / R4-4 |
| 新增 "state-transition coverage ≠ clinical correctness" 的限定 | R2-3 / R4-7 |
| Refused/Unknown 需走人工复核通路，不等于风险阴性 | R4-8 |
| T1–T3 声明为"手工编码的工作流控制，非临床推理" | R4-6 |
| 动态 Top-1 明确为"端到端协议分（含格式合规）" | R1 / R2-1 / R4-1 |
| 110 vs 22 声明为"asymmetric sampling，无法做对照显著性比较" | R1 / R2-2 / R4-2 |
| sleep medicine 系统由 "validated/confirming" 降级为 "evaluated / remains an empirical question" | R2-4 |
| Limitations 段扩充（合成偏差、构建偏差、需前瞻验证） | R1 |

**结论：措辞层面的欠债基本还清了。但实验层面的欠债一条都没补。**

这是致命的，因为 R4（唯一给 Reject 且 confidence = High）的原话是：

> "These issues make it difficult to conclude... I therefore recommend **rejection in the current form**."

R4 的两条核心理由——**baseline 0% 归因于 JSON 失败**、**benchmark 全合成**——都不是靠改措辞能解决的。
现在论文处在一种尴尬状态：**自己已经承认了所有弱点，但没有补上任何一条证据**。
"承认弱点"只会让审稿人更容易同意拒稿，除非同时给出"虽然有弱点，但补充实验后结论仍成立"。

---

## 二、关于"是不是现在要去找 benchmark"

**分三件事，benchmark 只占其中一件，而且不是最紧急的一件。**

1. **可比性修复（不需要任何外部资源，纯重跑）** ← 最紧急、性价比最高
2. **消融实验（不需要任何外部资源，纯重跑）** ← 最紧急
3. **外部效度证据（需要找真实数据 / 临床专家）** ← 需要但最慢，可延后

另外要先泼一盆冷水：**不存在"现成的精神科访谈 agent benchmark"可以直接拿来替换 PIB**。
公开的精神科语料（DAIC-WOZ、CIDH 等）都是**"评估患者"取向**（从访谈记录预测 PHQ/HAMD 分数），
不是**"评估访谈者覆盖度"取向**（有没有问全、该不该终止）。所以外部数据的用途不是"换 benchmark 跑分"，
而是做**外部效度验证**：证明 SSM 在真实（去标识）访谈上仍能工作，且暴露合成数据高估了多少。

---

## 三、P0 — 必做，直接决定能否从 Reject 翻到 Accept

### P0-1 同 22 例重跑 SSM，消除样本不对称
- **做法**：SSM-Psychiatrist 在 baseline 用的那 22 例上再跑一遍，与 110 例结果并列报告。
- **成本**：极低（约 1/5 的推理量）。
- **消掉**：R1-2、R2-2、R4-2（三位审稿人都点了这条）。
- **产出**：Table 新增一列 "SSM-Psy. (n=22)"。若 22 例上仍是 97%+，这条争议直接关闭。

### P0-2 给 baseline 加结构化输出保障，拆开报告"诊断正确率" vs "格式合规率"
这是**全文最关键的一个实验**。目前 0% vs 97.3% 的对比是审稿人最大的怒点。
- **做法**（三选一，建议全做）：
  - (a) **Output repair**：baseline 输出 JSON 失败时，允许 1–2 次带错误信息的重试（repair/retry protocol）；
  - (b) **Constrained decoding / structured output API**：用各家原生 JSON mode / tool calling；
  - (c) **Post-hoc 宽松解析**：从自由文本里正则抽取诊断标签，作为"诊断正确性"的独立指标。
- **报告方式**：把 dynamic Top-1 拆成三列
  1. `Format Compliance`（JSON schema 通过率）
  2. `Dx-Correct | Valid`（在合规输出上的诊断正确率）——这才是真正的诊断能力对比
  3. `Dx-Correct (unconstrained)`（不管格式，只看诊断对不对）
- **消掉**：R1-3、R2-1、R4-1。
- **预期**：baseline 的动态诊断正确率大概率在 60–85%，SSM 仍应显著更高，但会变成**可信的**数字而不是 0%。**不要怕这个数字变难看**——现在的 0% 反而让整篇文章不可信。

### P0-3 消融实验（R4-5 明确点名，四位审稿人都提到）
至少做 4 组，全部在**同一批 case、同一协议**下跑：

| 变体 | 去掉/改变什么 | 回答的问题 |
|---|---|---|
| A1 | 同样的 120-slot checklist 作为 prompt，但**无状态机强制执行** | 状态机本身 vs 清单知识的贡献（**最关键**） |
| A2 | 有状态机，**去掉 T1–T3** | 触发规则的贡献 |
| A3 | 有状态机，**去掉 Φ 终止准则**（改由 LLM 决定何时停） | 终止控制的贡献 |
| A4 | 四状态模型 → 传统二状态（Filled/Empty） | Refused/Unknown 状态的贡献 |
| A5（可选） | 去掉非信息性应答恢复序列 | 恢复机制的贡献 |

- **指标**：MustAsk、SVCL、Turns、动态 Top-1、冗余提问率。
- **产出**：新增一张 ablation table + 一小节分析。
- 额外收益：A1 是回答"是不是靠手工编码的临床知识"这个质疑的唯一方式。

---

## 四、P1 — 强烈建议做（决定是 Weak Accept 还是 Accept）

### P1-1 真实/去标识临床数据外测（就是你说的"找 benchmark"）
**推荐候选**（按对口程度排序）：

| 数据集 | 规模 | 标注 | 获取方式 | 适配度 |
|---|---|---|---|---|
| **DAIC-WOZ / E-DAIC** | 189 / 275 段真实半结构化精神科访谈 | PHQ-8 分项 + 总分 | 需签协议申请（USC） | ★★★★★ 英文、真实患者、半结构化访谈，最像 "真实访谈" |
| **CIDH** | 1,689 例真实临床访谈 | HAMD-13 | 需联系原作者（南京脑科医院合作） | ★★★★☆ 中文、规模大、真实医患 |
| **PDCH** | 99 例真实精神科医患问诊（多模态） | HAMD-17 | 公开 | ★★★★☆ 中文真实问诊，含文本转录 |
| **REALCBT / PsyDial / MusPsy** | 2k–8k 会话 | 部分有抑郁标签 | 部分公开 | ★★★☆☆ 咨询取向，非诊断访谈 |

**重要：不要指望在上面跑"诊断准确率"**（没有 slot 级金标注）。应该跑的是：

1. **安全性召回**：SSM 在真实转录上能否稳定识别/标记自杀意念、自伤等安全信号（可用 HAMD 的 Suicide 分项做金标，CIDH/PDCH 都有）。
2. **Slot 抽取填充率对比**：真实 vs 合成的填充率差异。真实数据必然更低、更多 Unknown——**这个"下降"本身就是有价值的发现**，正好用来证明"合成数据高估了性能"，把弱点变成贡献。
3. **外部效度相关性**：SSM 抽取的抑郁症状 slot 与 PHQ-8 / HAMD 总分的相关性（Spearman）。这是能被审稿人接受的"真实数据证据"。

**如果拿不到任何真实数据**（申请周期长是常态），走**降级方案**：
  - 在 PIB 上构造 **adversarial 变体子集**（约 30 例）：模糊回答、前后矛盾、拒绝回答、答非所问、情绪突变、意外话题跳转、共病披露。
  - 报告 SSM 与 baseline 在该子集上的性能衰减曲线。
  - 这直接回应 R1 的"ambiguous / contradictory / refusal / unexpected behavior"，且不需要任何外部数据。

### P1-2 临床专家评估（R1 / R2-5 / R4-10 三位点名）
找 **2–3 名精神科医师**（最好有医院合作资源）做三件事，每件事半小时内能完成：
1. **Taxonomy 完整性评审**：120 个 slot + 9 个 SVCL 域，逐项评定"是否必要 / 是否遗漏 DSM-5-TR 关键条目"，给出覆盖率评分与遗漏清单。
2. **生成病历临床可接受度**：随机抽 20–30 份 SSM 生成病历，Likert 5 分制评"是否可作为初诊记录草稿"。
3. **提问适当性**：抽 20 段访谈，评"提问是否恰当 / 是否冗余 / 是否缺乏共情"。
- **必须在文中写明**：专家人数、资质、是否参与过 PIB 构建（避免"自评"质疑，R1 专门问了这点）。

### P1-3 效率 / 患者负担指标（R4-9）
SSM 平均 11.2 轮 vs baseline 4–8 轮，这是明确的成本。必须正面回应：
- **冗余提问率**（同一 slot 被重复问的比例）
- **每轮信息增益**（新增 Filled slot 数 / 总轮数）
- **关键 slot 首次触达轮次**（安全性 slot 应最早）
- 可做一张 "coverage vs turns" 的帕累托曲线，说明多出的轮次换来的是什么。

### P1-4 补充图示（R3 明确说"too concise, only one end-to-end schematic"）
R3 给 Weak Accept 的理由就是图不够。建议补：
- 一张 **SSM 状态转移图**（E → F/R/U 的完整转移条件与触发规则）
- 一张 **T1–T3 触发时序示例**（真实访谈片段 + 议程重排前后对比）
- 一张 **消融结果条形图**
目前 `fig1–fig6.pdf` 都在目录里但**正文一张都没引用**，可以直接用起来（fig1_dynamic_task、fig3_dissociation、fig5_cost_performance、fig6_slot_taxonomy 都能直接对应上面几条）。

---

## 五、P2 — 锦上添花

- PIB 公开化：release benchmark + 标注协议 + 评测脚本（R1-4）。至少给个匿名仓库链接或声明"under release upon acceptance"。
- 安全/伦理专节：临床监督、人工介入通路、隐私治理、危机处理流程、自主部署的明确禁止（R1-12）。
- Refused/Unknown 在安全 slot 上的处置策略，写成明确规则并给出病例示例（R4-8）。

---

## 六、投稿路径（需要你这周就确认）

| 路径 | 说明 | 状态 |
|---|---|---|
| **BIBM 2026 Workshop 转移** | 拒稿邮件给了转移链接，paper ID `B1563`，password `p15637985`。**workshop 录用后与主会同一 proceedings、同样进 IEEE Xplore**。这是成本最低的"保底"路径。 | ⚠️ 会议 12/1–4 开幕，**必须立刻登录 cyberchair 确认 workshop 是否还开放、截止日期** |
| 转投期刊 | JAMIA、IEEE JBHI、Artificial Intelligence in Medicine、BMC MIDM、JMIR AI | 周期长，但实验补齐后最稳 |
| 转投其他会议 | IEEE EMBC 2027、ACM CHIL 2027、AAAI/ACL 的 health workshop | 需重新适配格式与篇幅 |

**建议**：先花 10 分钟登录 cyberchair 查 workshop 状态——如果还开着，就按 workshop 标准做 P0 + P1-4（篇幅可能要压到 short paper）；如果关了，就按期刊标准把 P0 + P1 全做完，投 IEEE JBHI 或 AIIM。

---

## 七、这周的执行顺序

1. **今天**：登录 cyberchair 确认 workshop 转移是否还开放（决定后面所有工作的标准与体量）。
2. **第 1–3 天**：跑 P0-1（22 例）+ P0-3（消融 A1–A4）。这两个都是"改配置重跑"，不需要新资源。
3. **第 4–7 天**：跑 P0-2（baseline 输出修复 + 三列指标拆分）。这是工作量最大但价值最高的一项。
4. **并行推进**：同步申请 DAIC-WOZ（或联系 CIDH/PDCH 作者），因为**数据申请审批慢，必须最早启动**；同时联系精神科医师排期 P1-2。
5. **第 2 周**：补 P1-3 效率指标、P1-4 图示，改写 Results/Discussion/Limitations。

---

## 八、一句话总结

**不要先去找 benchmark。先把"实验公平性"这个洞补上（22 例同测 + 输出修复 + 消融），
这三个实验不依赖任何外部资源，却能直接消掉 R4 拒稿的两条主因中的一条。
真实数据外测同时并行启动申请（审批慢），拿到了就做外部效度，拿不到就用 adversarial 变体子集降级替代。**
