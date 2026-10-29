# -*- coding: utf-8 -*-
"""学术风格图表（两张独立图），模拟 MATLAB / matplotlib 论文图风格"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

OUT = Path(__file__).resolve().parents[1] / "output" / "ppt_charts"
OUT.mkdir(parents=True, exist_ok=True)

matplotlib.rcParams.update({
    "font.family":        "sans-serif",
    "font.sans-serif":    ["Microsoft YaHei", "SimHei", "Arial"],
    "axes.unicode_minus": False,
    "font.size":          11,
})

# ── MATLAB default 色板 ───────────────────────────────────────────
C = ["#0072BD", "#D95319", "#EDB120", "#77AC30"]
# 蓝=PsychCounsel, 红=PIB(Ours), 橙=CounselBench-Eval, 绿=CounselBench-Adv

MODELS = [
    "ChatGLM3-6B",
    "Qwen-7B",
    "Baichuan2-13B",
    "Llama-3-8B",
    "Qwen2-72B",
    "GPT-4o-mini",
    "GPT-4o",
    "Claude-3.5-Sonnet",
]
x = np.arange(len(MODELS))

PSYCH_ZH   = np.array([61.2, 64.8, 67.5, 71.3, 79.8, 84.1, 87.3, 88.6])
COUNSEL_EV = np.array([55.4, 58.9, 63.2, 67.8, 75.2, 80.4, 84.2, 85.9])
COUNSEL_ADV= np.array([41.7, 46.3, 51.8, 57.2, 67.4, 73.8, 79.5, 81.2])
PIB        = np.array([18.2, 23.7, 31.5, 41.8, 60.6, 73.1, 81.9, 86.4])

# ═══════════════════════════════════
# 图 1：折线对比图（主图）
# ═══════════════════════════════════
fig1, ax = plt.subplots(figsize=(7.5, 5.0))
fig1.patch.set_facecolor("white")
ax.set_facecolor("white")

markers = ["o", "D", "s", "^"]
labels  = [
    "PsychCounsel-Bench_zh",
    "PIB (Ours)",
    "CounselBench-Eval",
    "CounselBench-Adv",
]
data    = [PSYCH_ZH, PIB, COUNSEL_EV, COUNSEL_ADV]
lws     = [1.5, 2.2, 1.5, 1.5]   # PIB 稍粗以突出

for yv, mk, col, lab, lw in zip(data, markers, C, labels, lws):
    ax.plot(x, yv, marker=mk, color=col, lw=lw,
            markersize=6, markerfacecolor=col,
            markeredgecolor="white", markeredgewidth=0.8,
            label=lab)

ax.set_xticks(x)
ax.set_xticklabels(MODELS, fontsize=9, rotation=20, ha="right")
ax.set_yticks(range(10, 100, 10))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_ylim(10, 98)
ax.set_ylabel("Overall Score (%)", fontsize=11)
ax.set_xlabel("Model", fontsize=11)
ax.set_title(
    "Performance Comparison across Psychiatric Benchmarks",
    fontsize=12, pad=10
)

ax.grid(True, linestyle="--", linewidth=0.6, color="#BBBBBB", alpha=0.8)
ax.set_axisbelow(True)
for sp in ["top", "right"]:
    ax.spines[sp].set_visible(False)
ax.spines["left"].set_linewidth(0.8)
ax.spines["bottom"].set_linewidth(0.8)

ax.legend(loc="upper left", fontsize=9, framealpha=1.0,
          edgecolor="#CCCCCC", borderpad=0.7, labelspacing=0.4,
          handlelength=2.0)

fig1.tight_layout()
fig1.savefig(OUT / "fig_compare_line.png", dpi=200, bbox_inches="tight")
print("Saved: fig_compare_line.png")

# ═══════════════════════════════════
# 图 2：区分度柱状对比图（辅图）
# ═══════════════════════════════════
bench_labels = [
    "PsychCounsel-Bench_zh",
    "CounselBench-Eval",
    "CounselBench-Adv",
    "PIB (Ours)",
]
spreads = [
    float(PSYCH_ZH.max()    - PSYCH_ZH.min()),
    float(COUNSEL_EV.max()  - COUNSEL_EV.min()),
    float(COUNSEL_ADV.max() - COUNSEL_ADV.min()),
    float(PIB.max()         - PIB.min()),
]
bar_cols = ["#0072BD", "#EDB120", "#77AC30", "#D95319"]

fig2, ax2 = plt.subplots(figsize=(5.5, 4.0))
fig2.patch.set_facecolor("white")
ax2.set_facecolor("white")

y_pos = np.arange(len(bench_labels))
bars  = ax2.barh(y_pos, spreads, height=0.5,
                 color=bar_cols, edgecolor="white", linewidth=0.8)

for bar, val in zip(bars, spreads):
    ax2.text(bar.get_width() + 0.6, bar.get_y() + bar.get_height() / 2,
             f"{val:.1f} pp", va="center", fontsize=10,
             color=bar.get_facecolor())

ax2.set_yticks(y_pos)
ax2.set_yticklabels(bench_labels, fontsize=9.5)
ax2.set_xlim(0, 90)
ax2.set_xlabel("Score Range (max − min, pp)", fontsize=11)
ax2.set_title("Model Discriminability by Benchmark", fontsize=12, pad=10)

ax2.grid(True, axis="x", linestyle="--", linewidth=0.6,
         color="#BBBBBB", alpha=0.8)
ax2.set_axisbelow(True)
ax2.invert_yaxis()
for sp in ["top", "right"]:
    ax2.spines[sp].set_visible(False)
ax2.spines["left"].set_linewidth(0.8)
ax2.spines["bottom"].set_linewidth(0.8)

fig2.tight_layout()
fig2.savefig(OUT / "fig_discriminability.png", dpi=200, bbox_inches="tight")
print("Saved: fig_discriminability.png")
