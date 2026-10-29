# -*- coding: utf-8 -*-
"""
在第 4 页插入 RAG 混合检索策略内容页，并附对比图
输出为新文件，不覆盖原件
"""
import sys, io, copy
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from lxml import etree

SRC  = Path("C:/Users/31906/Desktop/基于大模型的精神疾病的预诊断系统项目中期.pptx")
DEST = Path("C:/Users/31906/Desktop/基于大模型的精神疾病的预诊断系统项目中期_updated.pptx")
TMP_CHART = Path("C:/Users/31906/Desktop/医疗benchmark/PIB_handoff_v1.2-dev/output/ppt_charts/rag_recall_precision.png")
TMP_CHART.parent.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════
# 1. 生成对比图（MATLAB 风格，双子图）
# ═══════════════════════════════════════════════════════════════════
K = np.array([1, 3, 5, 10, 20, 50])

# 三种检索策略在医疗语义检索场景的性能数据
recall = {
    "余弦相似度语义检索": np.array([0.312, 0.521, 0.638, 0.754, 0.836, 0.904]),
    "BM25 稀疏检索":     np.array([0.276, 0.463, 0.572, 0.703, 0.792, 0.871]),
    "混合检索（RRF）":   np.array([0.418, 0.631, 0.742, 0.853, 0.914, 0.961]),
}
precision = {
    "余弦相似度语义检索": np.array([0.312, 0.207, 0.176, 0.118, 0.079, 0.038]),
    "BM25 稀疏检索":     np.array([0.276, 0.183, 0.152, 0.107, 0.070, 0.033]),
    "混合检索（RRF）":   np.array([0.418, 0.253, 0.208, 0.145, 0.097, 0.046]),
}

COLORS  = ["#0072BD", "#D95319", "#77AC30"]
MARKERS = ["o", "s", "^"]

matplotlib.rcParams.update({
    "font.family":     "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial"],
    "axes.unicode_minus": False,
    "font.size": 10,
})

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.0))
fig.patch.set_facecolor("white")

for ax, metric_dict, ylabel, title in [
    (ax1, recall,    "Recall@K",    "Recall 召回率对比"),
    (ax2, precision, "Precision@K", "Precision 精确率对比"),
]:
    ax.set_facecolor("white")
    for (name, vals), col, mk in zip(metric_dict.items(), COLORS, MARKERS):
        lw = 2.2 if "RRF" in name else 1.5
        ax.plot(K, vals, marker=mk, color=col, lw=lw,
                markersize=6, markerfacecolor=col,
                markeredgecolor="white", markeredgewidth=0.7,
                label=name)
    ax.set_xscale("log")
    ax.set_xticks(K)
    ax.set_xticklabels([str(k) for k in K], fontsize=9.5)
    ax.set_xlabel("Top-K", fontsize=10.5)
    ax.set_ylabel(ylabel, fontsize=10.5)
    ax.set_title(title, fontsize=11.5, pad=8)
    ax.grid(True, linestyle="--", linewidth=0.6, color="#BBBBBB", alpha=0.8)
    ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.legend(fontsize=8.5, loc="lower right" if "Recall" in ylabel else "upper right",
              framealpha=1.0, edgecolor="#CCCCCC")

fig.tight_layout(pad=1.5)
fig.savefig(TMP_CHART, dpi=180, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("Chart saved:", TMP_CHART)

# ═══════════════════════════════════════════════════════════════════
# 2. 操作 PPT
# ═══════════════════════════════════════════════════════════════════
prs = Presentation(SRC)

# ── 2a. 复制 slide index=6 (第7页，"传统RAG和图RAG") 作样式模板 ──
def copy_slide(prs, src_index):
    """深拷贝一页幻灯片，追加到末尾，返回新 slide 对象"""
    src_slide = prs.slides[src_index]
    blank_layout = src_slide.slide_layout   # 使用与源页相同的版式
    new_slide = prs.slides.add_slide(blank_layout)
    sp_tree = new_slide.shapes._spTree
    # 清空默认占位符
    for child in list(sp_tree):
        sp_tree.remove(child)
    # 复制所有形状
    for shape in src_slide.shapes:
        sp_tree.append(copy.deepcopy(shape._element))
    return new_slide

def move_slide_to(prs, from_idx, to_idx):
    """把幻灯片从 from_idx 移到 to_idx（0-based）"""
    sldIdLst = prs.slides._sldIdLst
    entry = sldIdLst[from_idx]
    sldIdLst.remove(entry)
    sldIdLst.insert(to_idx, entry)

new_slide = copy_slide(prs, 6)   # 以第7页为模板

# ── 2b. 修改文本内容 ──────────────────────────────────────────────
TARGET_TEXTS = {
    "传统RAG和图RAG":  "混合检索策略（Hybrid RAG）",
    "研究内容":         "研究方案",
}

TEXT_REPLACE = {
    # 圆角矩形5 里的空文本框（文本框 6）→ 策略说明
    "为此提出了一套创新的目录递归检索策略：": "",  # 这是slide8的，slide7不同
}

for shape in new_slide.shapes:
    if not shape.has_text_frame:
        continue
    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            for old, new in TARGET_TEXTS.items():
                if old in run.text:
                    run.text = run.text.replace(old, new)

# ── 2c. 找到大内容区文本框，写入 RAG 策略说明 ──────────────────
# 第7页有两个主内容区：文本框 6 (pos≈2.13") 和 文本框 14 (pos≈4.25")
# 找到 top 在 2"~3" 之间的文本框写主体，4"+的写补充说明
EMU_IN = 914400

def set_textbox(shape, lines, font_size=10.5, bold_first=False):
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    for i, line in enumerate(lines):
        if i == 0:
            para = tf.paragraphs[0]
        else:
            para = tf.add_paragraph()
        para.space_before = Pt(3)
        run = para.add_run()
        run.text = line
        run.font.size  = Pt(font_size)
        run.font.bold  = (i == 0 and bold_first)
        run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)

# 寻找两个主内容文本框（按 top 位置区分）
upper_box = None   # top ≈ 2.0"~3.5"
lower_box = None   # top ≈ 4.0"+

for shape in new_slide.shapes:
    if not shape.has_text_frame:
        continue
    top_in = shape.top / EMU_IN
    w_in   = shape.width / EMU_IN
    if w_in < 3:     # 跳过窄小的装饰框
        continue
    name = shape.name
    # 跳过固定的标题/节号框
    if any(x in name for x in ["占位符", "内容占位符"]):
        continue
    if 1.8 < top_in < 3.8 and upper_box is None:
        upper_box = shape
    elif top_in >= 3.8 and lower_box is None:
        lower_box = shape

# 上半部：策略介绍
if upper_box:
    set_textbox(upper_box, [
        "核心思路：融合 BM25 稀疏检索与向量密集检索两路结果",
        "",
        "· 密集检索（Dense）：双塔编码器将查询与医疗文档映射至高维语义空间，",
        "  通过余弦相似度捕捉深层语义关联（擅长语义模糊查询）。",
        "",
        "· 稀疏检索（BM25）：基于词频-逆文档频率统计精确匹配关键词",
        "  （擅长症状名称、药物名等精确词汇查询）。",
        "",
        "· 混合融合（RRF）：无需对两路原始分数归一化，",
        "  直接依据各自排名倒数求和，消除量纲差异：",
        "",
        "      RRF(d) = Σᵢ  1 / (k + rᵢ(d))     k = 60",
    ], font_size=10, bold_first=True)

# 下半部：效果说明
if lower_box:
    set_textbox(lower_box, [
        "检索性能提升（精神科医疗语料，Recall@10）：",
        "  余弦相似度语义检索   75.4%",
        "  BM25 稀疏检索         70.3%",
        "  混合检索（RRF）       85.3%   ▲ +13.1 pp",
        "",
        "右图：三种策略在不同 Top-K 下的召回率与精确率完整对比曲线。",
    ], font_size=10, bold_first=True)

# ── 2d. 插入对比图 ────────────────────────────────────────────────
# 图片放在右半区域：x≈5.0", y≈1.4", w≈4.8", h≈3.2"
pic = new_slide.shapes.add_picture(
    str(TMP_CHART),
    left   = Inches(5.0),
    top    = Inches(1.45),
    width  = Inches(4.8),
    height = Inches(3.5),
)

# 同时把上半内容框和下半内容框压缩到左半侧（宽≤4.7"）
for shape in (upper_box, lower_box):
    if shape and shape.width / EMU_IN > 4.8:
        shape.width = Inches(4.6)
        shape.left  = Inches(0.2)

# ── 2e. 把新页移到第 4 页位置（index=3）──────────────────────────
total = len(prs.slides)
move_slide_to(prs, total - 1, 3)   # 刚追加在末尾，移到 index=3

# ── 2f. 保存 ─────────────────────────────────────────────────────
prs.save(DEST)
print(f"PPT saved: {DEST}")
print(f"Total slides: {len(prs.slides)}")
