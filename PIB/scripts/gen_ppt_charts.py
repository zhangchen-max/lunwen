"""生成用于 PPT 展示的三张图表（折线图为主），保存到 output/ppt_charts/"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "output" / "ppt_charts"
OUT.mkdir(parents=True, exist_ok=True)

# ── 配色方案（PPT 友好）──────────────────────────────────────────
C_BLUE   = "#2563EB"
C_ORANGE = "#EA580C"
C_GREEN  = "#16A34A"
C_GRAY   = "#94A3B8"
C_PURPLE = "#7C3AED"
BG       = "#FAFAFA"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor": BG,
    "figure.facecolor": "white",
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
})

# ══════════════════════════════════════════════════════════════════
# 图1：各诊断类别的 Top-1 准确率对比（静态 vs 动态，折线图）
# ══════════════════════════════════════════════════════════════════
labels_order = ["ADJ","BDD","BPD","IED","OCD","OCPD","OS_OCRD","OTHER","PGD","PMDD","SSD"]
label_names  = labels_order  # 短标签直接用

# 静态 heuristic（来自 summary_static.csv label 行）
static_top1 = {
    "ADJ":0.6,"BDD":0.6,"BPD":0.2,"IED":0.6,"OCD":0.2,
    "OCPD":0.4,"OS_OCRD":0.0,"OTHER":0.6,"PGD":1.0,"PMDD":1.0,"SSD":0.8,
}
# 动态 dummy（来自 summary_dynamic.csv label 行）
dynamic_top1 = {
    "ADJ":1.0,"BDD":1.0,"BPD":0.0,"IED":1.0,"OCD":1.0,
    "OCPD":1.0,"OS_OCRD":0.0,"OTHER":1.0,"PGD":1.0,"PMDD":1.0,"SSD":1.0,
}

x = np.arange(len(labels_order))
sv = [static_top1[l]  for l in labels_order]
dv = [dynamic_top1[l] for l in labels_order]

fig, ax = plt.subplots(figsize=(13, 5))
ax.plot(x, sv, "o-", color=C_ORANGE, lw=2.2, ms=7, label="Static Heuristic")
ax.plot(x, dv, "s-", color=C_BLUE,   lw=2.2, ms=7, label="Dynamic Dummy Doctor")

# 标注数值
for i, (s, d) in enumerate(zip(sv, dv)):
    ax.annotate(f"{s:.0%}", (i, s), textcoords="offset points", xytext=(0, 8),
                ha="center", fontsize=8, color=C_ORANGE)
    ax.annotate(f"{d:.0%}", (i, d), textcoords="offset points", xytext=(0,-14),
                ha="center", fontsize=8, color=C_BLUE)

ax.set_xticks(x)
ax.set_xticklabels(labels_order, fontsize=10)
ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
ax.set_yticklabels(["0%","25%","50%","75%","100%"])
ax.set_ylim(-0.12, 1.18)
ax.set_ylabel("Top-1 Accuracy", fontsize=11)
ax.set_title("各诊断类别 Top-1 准确率：Static vs Dynamic", fontsize=13, fontweight="bold", pad=14)
ax.legend(fontsize=10, loc="upper left")

fig.tight_layout()
fig.savefig(OUT / "fig1_per_label_top1.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ fig1")

# ══════════════════════════════════════════════════════════════════
# 图2：多模型关键指标对比（折线/雷达风格 → 用折线图展示三指标趋势）
# ══════════════════════════════════════════════════════════════════
# Dynamic 各 run 的结果（按 top1 排序展示演进）
models = [
    ("psy_nav_test",  "PsyNav-test",  0.091, 0.000, 0.000),
    ("psy_nav_weak3", "PsyNav-weak3", 0.167, 1.000, 1.000),
    ("psy_nav_full",  "PsyNav-full",  0.318, 0.682, 0.648),
    ("psy_nav_test2", "PsyNav-test2", 0.318, 1.000, 0.955),
    ("psy_nav_test3", "PsyNav-test3", 0.500, 1.000, 0.966),
    ("psy_nav_r4",    "PsyNav-r4",    0.591, 1.000, 0.955),
    ("test_dynamic",  "Dummy Doctor", 0.864, 1.000, 0.924),
]
mnames = [m[1] for m in models]
top1s  = [m[2] for m in models]
musts  = [m[3] for m in models]
svcls  = [m[4] for m in models]

x2 = np.arange(len(mnames))
fig2, ax2 = plt.subplots(figsize=(13, 5))

ax2.plot(x2, top1s, "o-", color=C_ORANGE, lw=2.5, ms=8,  label="Top-1 Accuracy (DDx)")
ax2.plot(x2, musts, "s-", color=C_BLUE,   lw=2.5, ms=8,  label="Must-Ask Hit Rate")
ax2.plot(x2, svcls, "^-", color=C_GREEN,  lw=2.5, ms=8,  label="SVCL Coverage")

for i, (t, m, s) in enumerate(zip(top1s, musts, svcls)):
    ax2.annotate(f"{t:.0%}", (i, t), textcoords="offset points", xytext=(0, 9),
                 ha="center", fontsize=8, color=C_ORANGE)

ax2.set_xticks(x2)
ax2.set_xticklabels(mnames, fontsize=9, rotation=15, ha="right")
ax2.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
ax2.set_yticklabels(["0%","25%","50%","75%","100%"])
ax2.set_ylim(-0.05, 1.15)
ax2.set_ylabel("Score", fontsize=11)
ax2.set_title("Dynamic Task：多版本模型三维指标演进", fontsize=13, fontweight="bold", pad=14)
ax2.legend(fontsize=10, loc="lower right")

fig2.tight_layout()
fig2.savefig(OUT / "fig2_model_evolution.png", dpi=150, bbox_inches="tight")
plt.close(fig2)
print("✓ fig2")

# ══════════════════════════════════════════════════════════════════
# 图3：DSM 模块维度——Static vs Dynamic Top-1 对比（折线图）
# ══════════════════════════════════════════════════════════════════
modules = ["DEP","DICCD","OCRD","OTHER","PD","SSRD","TSR"]
# 静态 heuristic（全量 110 例 summary_static）
static_mod = {
    "DEP":1.0,"DICCD":0.6,"OCRD":0.267,"OTHER":0.6,"PD":0.3,"SSRD":0.8,"TSR":0.8,
}
# 动态 dummy（summary_dynamic）
dynamic_mod = {
    "DEP":1.0,"DICCD":1.0,"OCRD":0.667,"OTHER":1.0,"PD":0.5,"SSRD":1.0,"TSR":1.0,
}

x3 = np.arange(len(modules))
sm = [static_mod[m]  for m in modules]
dm = [dynamic_mod[m] for m in modules]

fig3, ax3 = plt.subplots(figsize=(10, 5))
ax3.plot(x3, sm, "o-", color=C_ORANGE, lw=2.5, ms=9, label="Static Heuristic")
ax3.plot(x3, dm, "s-", color=C_BLUE,   lw=2.5, ms=9, label="Dynamic Dummy Doctor")

# 填充差异区域
ax3.fill_between(x3, sm, dm, where=[d>s for d,s in zip(dm,sm)],
                 alpha=0.12, color=C_BLUE, label="Dynamic 提升区间")

for i, (s, d) in enumerate(zip(sm, dm)):
    ax3.annotate(f"{s:.0%}", (i, s), textcoords="offset points", xytext=(-14, 0),
                 ha="center", fontsize=9, color=C_ORANGE)
    ax3.annotate(f"{d:.0%}", (i, d), textcoords="offset points", xytext=(14, 0),
                 ha="center", fontsize=9, color=C_BLUE)

ax3.set_xticks(x3)
ax3.set_xticklabels(modules, fontsize=12)
ax3.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
ax3.set_yticklabels(["0%","25%","50%","75%","100%"])
ax3.set_ylim(-0.05, 1.18)
ax3.set_ylabel("Top-1 Accuracy", fontsize=11)
ax3.set_title("DSM-5-TR 模块维度准确率：Static vs Dynamic", fontsize=13, fontweight="bold", pad=14)
ax3.legend(fontsize=10)

fig3.tight_layout()
fig3.savefig(OUT / "fig3_dsm_module.png", dpi=150, bbox_inches="tight")
plt.close(fig3)
print("✓ fig3")

print(f"\n所有图表已保存至: {OUT}")
