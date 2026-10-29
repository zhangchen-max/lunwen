# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree

OUT = Path(__file__).resolve().parents[1] / "output"
OUT.mkdir(parents=True, exist_ok=True)

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

doc = Document()

# ── 页边距 ────────────────────────────────────────────────────────
for sec in doc.sections:
    sec.top_margin    = Cm(2.54)
    sec.bottom_margin = Cm(2.54)
    sec.left_margin   = Cm(3.17)
    sec.right_margin  = Cm(3.17)

# ── 工具函数 ──────────────────────────────────────────────────────
def add_eq(doc, omml_str):
    """把 OMML 字符串插入为独立居中段落"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after  = Pt(6)
    p._p.append(etree.fromstring(omml_str.encode("utf-8")))
    return p

def body(doc, text, size=11):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    r.font.size = Pt(size)
    return p

def bold_body(doc, text, size=11):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    r.font.size  = Pt(size)
    r.font.bold  = True
    return p

def italic_body(doc, text, size=10.5):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size   = Pt(size)
    r.font.italic = True
    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    return p

def label_para(doc, label, size=10.5):
    """右对齐公式编号"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(label)
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    return p

def divider(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"),   "single")
    bottom.set(qn("w:sz"),    "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "AAAAAA")
    pBdr.append(bottom)
    pPr.append(pBdr)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after  = Pt(8)

# ── OMML 公式字符串 ───────────────────────────────────────────────

# 公式1：s_hybrid = α·s_dense + (1-α)·s_sparse
EQ1 = f'''<m:oMathPara xmlns:m="{M}">
<m:oMath>
  <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
    <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>s</m:t></m:r></m:e>
    <m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>hybrid</m:t></m:r></m:sub>
  </m:sSub>
  <m:r><m:t xml:space="preserve">(q, d) = &#x3B1; &#x22C5; </m:t></m:r>
  <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
    <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>s</m:t></m:r></m:e>
    <m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>dense</m:t></m:r></m:sub>
  </m:sSub>
  <m:r><m:t xml:space="preserve">(q, d) + (1 &#x2212; &#x3B1;) &#x22C5; </m:t></m:r>
  <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
    <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>s</m:t></m:r></m:e>
    <m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>sparse</m:t></m:r></m:sub>
  </m:sSub>
  <m:r><m:t>(q, d)</m:t></m:r>
</m:oMath>
</m:oMathPara>'''

# 公式2：s_dense = (e_q · e_d) / (||e_q|| · ||e_d||)
EQ2 = f'''<m:oMathPara xmlns:m="{M}">
<m:oMath>
  <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
    <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>s</m:t></m:r></m:e>
    <m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>dense</m:t></m:r></m:sub>
  </m:sSub>
  <m:r><m:t xml:space="preserve">(q, d) = </m:t></m:r>
  <m:f><m:fPr><m:ctrlPr/></m:fPr>
    <m:num>
      <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
        <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>e</m:t></m:r></m:e>
        <m:sub><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>q</m:t></m:r></m:sub>
      </m:sSub>
      <m:r><m:t xml:space="preserve"> &#x22C5; </m:t></m:r>
      <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
        <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>e</m:t></m:r></m:e>
        <m:sub><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>d</m:t></m:r></m:sub>
      </m:sSub>
    </m:num>
    <m:den>
      <m:r><m:t>&#x2016;</m:t></m:r>
      <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
        <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>e</m:t></m:r></m:e>
        <m:sub><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>q</m:t></m:r></m:sub>
      </m:sSub>
      <m:r><m:t xml:space="preserve">&#x2016; &#x22C5; &#x2016;</m:t></m:r>
      <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
        <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>e</m:t></m:r></m:e>
        <m:sub><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>d</m:t></m:r></m:sub>
      </m:sSub>
      <m:r><m:t>&#x2016;</m:t></m:r>
    </m:den>
  </m:f>
</m:oMath>
</m:oMathPara>'''

# 公式3：BM25(q,d) = Σ_{t∈q} IDF(t) · f(t,d)·(k1+1) / (f(t,d)+k1·(1-b+b·|d|/avgdl))
EQ3 = f'''<m:oMathPara xmlns:m="{M}">
<m:oMath>
  <m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t xml:space="preserve">BM25(q, d) = </m:t></m:r>
  <m:nary>
    <m:naryPr>
      <m:chr m:val="&#x2211;"/>
      <m:limLoc m:val="undOvr"/>
      <m:subHide m:val="0"/>
      <m:supHide m:val="1"/>
      <m:ctrlPr/>
    </m:naryPr>
    <m:sub><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t xml:space="preserve">t &#x2208; q</m:t></m:r></m:sub>
    <m:sup><m:r><m:t/></m:r></m:sup>
    <m:e>
      <m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t xml:space="preserve">IDF(t) &#x22C5; </m:t></m:r>
      <m:f><m:fPr><m:ctrlPr/></m:fPr>
        <m:num>
          <m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t xml:space="preserve">f (t, d) &#x22C5; (</m:t></m:r>
          <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
            <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>k</m:t></m:r></m:e>
            <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
          </m:sSub>
          <m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t xml:space="preserve"> + 1)</m:t></m:r>
        </m:num>
        <m:den>
          <m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t xml:space="preserve">f (t, d) + </m:t></m:r>
          <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
            <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>k</m:t></m:r></m:e>
            <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
          </m:sSub>
          <m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t xml:space="preserve"> &#x22C5; (1 &#x2212; b + b &#x22C5; </m:t></m:r>
          <m:f><m:fPr><m:ctrlPr/></m:fPr>
            <m:num><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>|d|</m:t></m:r></m:num>
            <m:den><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>avgdl</m:t></m:r></m:den>
          </m:f>
          <m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>)</m:t></m:r>
        </m:den>
      </m:f>
    </m:e>
  </m:nary>
</m:oMath>
</m:oMathPara>'''

# 公式4：RRF(d) = Σ_{i=1}^{N} 1/(k + r_i(d))
EQ4 = f'''<m:oMathPara xmlns:m="{M}">
<m:oMath>
  <m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t xml:space="preserve">RRF(d) = </m:t></m:r>
  <m:nary>
    <m:naryPr>
      <m:chr m:val="&#x2211;"/>
      <m:limLoc m:val="undOvr"/>
      <m:subHide m:val="0"/>
      <m:supHide m:val="0"/>
      <m:ctrlPr/>
    </m:naryPr>
    <m:sub>
      <m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t xml:space="preserve">i = 1</m:t></m:r>
    </m:sub>
    <m:sup>
      <m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>N</m:t></m:r>
    </m:sup>
    <m:e>
      <m:f><m:fPr><m:ctrlPr/></m:fPr>
        <m:num><m:r><m:t>1</m:t></m:r></m:num>
        <m:den>
          <m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t xml:space="preserve">k + </m:t></m:r>
          <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
            <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>r</m:t></m:r></m:e>
            <m:sub><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>i</m:t></m:r></m:sub>
          </m:sSub>
          <m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>(d)</m:t></m:r>
        </m:den>
      </m:f>
    </m:e>
  </m:nary>
</m:oMath>
</m:oMathPara>'''

# 公式5：s_hybrid = α(q)·s_dense + β(q)·s_sparse + γ(q)·s_graph
EQ5 = f'''<m:oMathPara xmlns:m="{M}">
<m:oMath>
  <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
    <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>s</m:t></m:r></m:e>
    <m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>hybrid</m:t></m:r></m:sub>
  </m:sSub>
  <m:r><m:t xml:space="preserve"> = &#x3B1;(q) &#x22C5; </m:t></m:r>
  <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
    <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>s</m:t></m:r></m:e>
    <m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>dense</m:t></m:r></m:sub>
  </m:sSub>
  <m:r><m:t xml:space="preserve"> + &#x3B2;(q) &#x22C5; </m:t></m:r>
  <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
    <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>s</m:t></m:r></m:e>
    <m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>sparse</m:t></m:r></m:sub>
  </m:sSub>
  <m:r><m:t xml:space="preserve"> + &#x3B3;(q) &#x22C5; </m:t></m:r>
  <m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>
    <m:e><m:r><m:rPr><m:sty m:val="i"/></m:rPr><m:t>s</m:t></m:r></m:e>
    <m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>graph</m:t></m:r></m:sub>
  </m:sSub>
</m:oMath>
</m:oMathPara>'''

# 约束条件 α+β+γ=1
EQ5b = f'''<m:oMathPara xmlns:m="{M}">
<m:oMath>
  <m:r><m:t xml:space="preserve">s.t.&#x2004; &#x3B1;(q) + &#x3B2;(q) + &#x3B3;(q) = 1,&#x2004; &#x3B1;,&#x3B2;,&#x3B3; &#x2265; 0</m:t></m:r>
</m:oMath>
</m:oMathPara>'''

# ═══════════════════════════════════════════════════════════════════
# 文档正文
# ═══════════════════════════════════════════════════════════════════

# 标题
t = doc.add_heading("RAG 混合检索策略：数学公式与方法综述", 0)
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.runs[0].font.size = Pt(18)

sub = doc.add_paragraph("Hybrid Retrieval Strategy in Retrieval-Augmented Generation")
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub.runs[0].font.size   = Pt(12)
sub.runs[0].font.italic = True
sub.runs[0].font.color.rgb = RGBColor(0x44, 0x44, 0x44)
doc.add_paragraph()

# 概述
doc.add_heading("概述", level=1)
body(doc,
    "RAG（Retrieval-Augmented Generation）混合检索策略通过融合密集检索（Dense Retrieval）与"
    "稀疏检索（Sparse Retrieval）的互补优势，有效提升文档召回率与语义匹配精度。"
    "密集检索依赖双塔神经网络将查询与文档编码为向量，捕捉深层语义；"
    "稀疏检索（如 BM25）则基于词频统计，擅长精确关键词匹配。"
    "二者融合的主流方法可分为以下三类范式。"
)
doc.add_paragraph()

divider(doc)

# ─────────────────────────────────────────────────────────────────
# 方案一
# ─────────────────────────────────────────────────────────────────
doc.add_heading("一、加权线性融合（Weighted Hybrid Score）", level=1)
italic_body(doc, "代表论文：Ma et al., arXiv:2310.08319 (2023)；Luan et al., TACL 2021")
doc.add_paragraph()

bold_body(doc, "▌ 综合得分公式")
add_eq(doc, EQ1)
label_para(doc, "（式 1）")

body(doc,
    "其中 α ∈ [0, 1] 为可调权重，控制语义检索与词法检索的相对贡献；"
    "两路得分在融合前需各自归一化至 [0, 1]（通常采用 min-max 归一化或 softmax）。"
)
doc.add_paragraph()

bold_body(doc, "▌ 密集检索得分（余弦相似度）")
add_eq(doc, EQ2)
label_para(doc, "（式 2）")

body(doc,
    "eₓ 为查询 q 或文档 d 经双塔编码器（如 BERT、BGE）生成的稠密向量表示；"
    "‖·‖ 表示 L2 范数。"
)
doc.add_paragraph()

bold_body(doc, "▌ 稀疏检索得分（BM25）")
add_eq(doc, EQ3)
label_para(doc, "（式 3）")

# 参数说明表格
table = doc.add_table(rows=6, cols=2)
table.style = "Table Grid"
hdr = table.rows[0].cells
hdr[0].text = "参数"
hdr[1].text = "含义"
rows_data = [
    ("f(t, d)",   "词项 t 在文档 d 中的词频"),
    ("IDF(t)",    "词项 t 的逆文档频率：log((N−n(t)+0.5)/(n(t)+0.5))"),
    ("|d|",       "文档 d 的词数"),
    ("avgdl",     "语料库平均文档词数"),
    ("k₁, b",     "超参数，通常取 k₁ = 1.5，b = 0.75"),
]
for i, (param, meaning) in enumerate(rows_data):
    row = table.rows[i+1].cells
    row[0].text = param
    row[1].text = meaning
for row in table.rows:
    for cell in row.cells:
        for para in cell.paragraphs:
            for run in para.runs:
                run.font.size = Pt(10)
doc.add_paragraph()

divider(doc)

# ─────────────────────────────────────────────────────────────────
# 方案二
# ─────────────────────────────────────────────────────────────────
doc.add_heading("二、倒数排名融合（Reciprocal Rank Fusion，RRF）", level=1)
italic_body(doc, "代表论文：Cormack et al., SIGIR 2009；Rackauckas, arXiv:2402.03367 (2024)")
doc.add_paragraph()

bold_body(doc, "▌ 公式")
add_eq(doc, EQ4)
label_para(doc, "（式 4）")

body(doc,
    "其中 N 为参与融合的检索器数量（如密集检索 + BM25 取 N = 2）；"
    "rᵢ(d) 为文档 d 在第 i 个检索器排名列表中的位次（从 1 开始）；"
    "k 为平滑常数，经验取值 k = 60，用于抑制头部排名权重过度集中。"
)
doc.add_paragraph()

bold_body(doc, "▌ 方法优势")
items = [
    "无需对不同检索系统的原始得分进行归一化处理，鲁棒性强；",
    "排名越靠前的文档权重越高，对噪声排名不敏感；",
    "实证表明在多数信息检索任务上优于直接得分加权融合（Cormack, 2009）；",
    "RAG-Fusion（2024）将 RRF 与多路查询改写（Query Rewriting）结合，进一步提升召回多样性。",
]
for item in items:
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run(item)
    r.font.size = Pt(11)
doc.add_paragraph()

divider(doc)

# ─────────────────────────────────────────────────────────────────
# 方案三
# ─────────────────────────────────────────────────────────────────
doc.add_heading("三、动态自适应融合（Query-Adaptive Fusion）", level=1)
italic_body(doc,
    "代表论文：Sarthi et al., ICLR 2024（RAPTOR）；"
    "Edge et al., arXiv:2404.16130 (2024)（GraphRAG, Microsoft）"
)
doc.add_paragraph()

bold_body(doc, "▌ 公式")
add_eq(doc, EQ5)
add_eq(doc, EQ5b)
label_para(doc, "（式 5）")

body(doc,
    "α(q)、β(q)、γ(q) 由查询路由器（Query Router）根据查询类型动态预测，"
    "满足三者之和为 1 的归一化约束。"
    "sₐᵣₐₚₕ 为图检索得分，由知识图谱（KG）或文档层次结构中的图游走算法计算得出，"
    "适用于需要多跳推理的复杂查询场景（如 GraphRAG）。"
)
doc.add_paragraph()

bold_body(doc, "▌ 查询路由器实现方式")
router_items = [
    "基于规则：关键词密度高 → 提升 β（BM25 权重）；语义模糊 → 提升 α（Dense 权重）；",
    "基于分类器：轻量 BERT 分类器预测查询类型标签，映射至权重组合；",
    "基于 LLM：由大模型直接输出结构化权重向量（适用于 Agent 场景）。",
]
for item in router_items:
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run(item)
    r.font.size = Pt(11)
doc.add_paragraph()

divider(doc)

# ─────────────────────────────────────────────────────────────────
# 三种方案对比
# ─────────────────────────────────────────────────────────────────
doc.add_heading("四、三种方案对比", level=1)

cmp = doc.add_table(rows=5, cols=4)
cmp.style = "Table Grid"
headers = ["对比维度", "加权线性融合", "RRF（式 4）", "动态自适应融合"]
data_rows = [
    ("归一化要求",   "需要",         "不需要",     "需要"),
    ("超参数数量",   "1（α）",       "1（k）",     "3（α, β, γ 函数）"),
    ("工程复杂度",   "低",           "低",         "高"),
    ("适用场景",     "通用检索",     "多路融合排序", "多跳推理 / Agent RAG"),
]
for j, h in enumerate(headers):
    cell = cmp.rows[0].cells[j]
    cell.text = h
    cell.paragraphs[0].runs[0].font.bold = True
for i, row_data in enumerate(data_rows):
    for j, val in enumerate(row_data):
        cmp.rows[i+1].cells[j].text = val
for row in cmp.rows:
    for cell in row.cells:
        for para in cell.paragraphs:
            for run in para.runs:
                run.font.size = Pt(10.5)
doc.add_paragraph()

divider(doc)

# ─────────────────────────────────────────────────────────────────
# 参考文献
# ─────────────────────────────────────────────────────────────────
doc.add_heading("参考文献", level=1)
refs = [
    "[1] Cormack, G. V., Clarke, C. L. A., & Buettcher, S. (2009). Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods. SIGIR 2009.",
    "[2] Robertson, S., & Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond. Foundations and Trends in Information Retrieval.",
    "[3] Luan, Y., Eisenstein, J., Toutanova, K., & Collins, M. (2021). Sparse, Dense, and Attentional Representations for Text Retrieval. TACL.",
    "[4] Ma, X., et al. (2023). Fine-Tuning LLaMA for Multi-Stage Text Retrieval. arXiv:2310.08319.",
    "[5] Rackauckas, Z. (2024). RAG-Fusion: A New Take on Retrieval-Augmented Generation. arXiv:2402.03367.",
    "[6] Sarthi, P., et al. (2024). RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval. ICLR 2024.",
    "[7] Edge, D., et al. (2024). From Local to Global: A Graph RAG Approach to Query-Focused Summarization. arXiv:2404.16130.",
]
for ref in refs:
    p = doc.add_paragraph(style="List Number")
    p.clear()
    r = p.add_run(ref)
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

# ── 保存 ─────────────────────────────────────────────────────────
out_path = OUT / "RAG混合检索策略公式说明.docx"
doc.save(out_path)
print(f"Saved: {out_path}")
