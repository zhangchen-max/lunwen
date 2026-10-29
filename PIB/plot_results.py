"""
从 6.23result/ 读取所有模型的 summary.json，生成论文图像。

用法：
  python plot_results.py                  # 生成全部图
  python plot_results.py --figs 1 2 4     # 只生成指定图

输出目录：6.23result/figures/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# ── 样式 ─────────────────────────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "font.size": 7,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
    "legend.fontsize": 6,
    "figure.dpi": 150,
})

C_BLUE   = "#4878CF"
C_ORANGE = "#D65F00"
C_GREEN  = "#6ACC65"
C_RED    = "#D62728"
C_GREY   = "#888888"
C_LBLUE  = "#A8C4E0"
RISK_COLORS = {"Low": C_GREEN, "Moderate": C_ORANGE, "High": C_RED}

ROOT = Path(__file__).parent / "6.23result"
OUT  = ROOT / "figures"

# ── 数据加载 ──────────────────────────────────────────────────────────────────

def load_summaries() -> tuple[list[dict], list[dict]]:
    """返回 (static_summaries, dynamic_summaries)，按 top1 降序排列"""
    static, dynamic = [], []
    for model_dir in sorted(ROOT.iterdir()):
        if not model_dir.is_dir() or model_dir.name == "figures":
            continue
        s_path = model_dir / "static" / "summary.json"
        d_path = model_dir / "dynamic" / "summary.json"
        if s_path.exists():
            static.append(json.loads(s_path.read_text(encoding="utf-8")))
        if d_path.exists():
            dynamic.append(json.loads(d_path.read_text(encoding="utf-8")))
    static.sort(key=lambda x: x["top1"], reverse=True)
    dynamic.sort(key=lambda x: x["top1"], reverse=True)
    return static, dynamic


def save_pub(fig, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "pdf", "tiff"):
        kw = {"bbox_inches": "tight"}
        if ext == "tiff":
            kw["dpi"] = 600
        fig.savefig(OUT / f"{stem}.{ext}", **kw)
    print(f"  saved {stem}.*")


# ── Fig 1 — Dynamic: MustAsk / SVCL / Turns ──────────────────────────────────

def fig1_dynamic(dynamic: list[dict]) -> None:
    if not dynamic:
        print("  [跳过 Fig1] 无 dynamic 数据")
        return

    models  = [d["model_label"] for d in dynamic]
    mustask = [d["must_ask_hit_rate"] for d in dynamic]
    svcl    = [d["svcl_domain_coverage"] for d in dynamic]
    turns   = [d["avg_turns"] for d in dynamic]
    risks   = [d["cf1_risk"] for d in dynamic]

    n = len(models)
    x = np.arange(n)
    w = 0.35

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8),
                             gridspec_kw={"width_ratios": [2.8, 1]})
    fig.subplots_adjust(wspace=0.35)

    ax = axes[0]
    ax.bar(x - w/2, mustask, w, label="MustAsk", color=C_BLUE,   alpha=0.85, linewidth=0)
    ax.bar(x + w/2, svcl,    w, label="SVCL",    color=C_ORANGE, alpha=0.85, linewidth=0)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=6)
    ax.set_ylim(0.60, 1.04)
    ax.set_ylabel("Score", fontsize=7)
    ax.set_title("Dynamic task — coverage metrics", fontsize=7, fontweight="bold", pad=4)
    ax.axhline(1.0, color=C_GREY, lw=0.6, ls="--", zorder=0)
    ax.legend(loc="lower left", fontsize=6, ncol=2)
    for i, risk in enumerate(risks):
        if risk != "Low":
            ax.annotate(risk, xy=(x[i], max(mustask[i], svcl[i]) + 0.008),
                        ha="center", va="bottom", fontsize=5.5,
                        color=RISK_COLORS[risk], fontweight="bold")

    ax2 = axes[1]
    bar_colors = [RISK_COLORS[r] for r in risks]
    ax2.barh(x, turns, color=bar_colors, alpha=0.85, linewidth=0)
    ax2.set_yticks(x)
    ax2.set_yticklabels(models, fontsize=6)
    ax2.set_xlabel("Avg turns", fontsize=7)
    ax2.set_title("Turn count\n(by CF-1 risk)", fontsize=7, fontweight="bold", pad=4)
    ax2.invert_yaxis()
    legend_els = [mpatches.Patch(color=v, label=k) for k, v in RISK_COLORS.items()]
    ax2.legend(handles=legend_els, loc="lower right", fontsize=5.5)
    for i, t in enumerate(turns):
        ax2.text(t + 0.05, i, f"{t:.1f}", va="center", fontsize=6)

    save_pub(fig, "fig1_dynamic_task")
    plt.close(fig)


# ── Fig 2 — Per-label heatmap (Static) ────────────────────────────────────────

def fig2_heatmap(static: list[dict]) -> None:
    if not static:
        print("  [跳过 Fig2] 无 static 数据")
        return

    # 取所有模型都有的 label 集合
    all_labels = sorted({lb for s in static for lb in s["per_label"]})
    # 论文优先展示顺序
    priority = ["OCD", "BDD", "BPD", "OS_OCRD", "IED", "OTHER"]
    labels = [l for l in priority if l in all_labels] + \
             [l for l in all_labels if l not in priority]

    models = [s["model_label"] for s in static]
    matrix = np.array([
        [s["per_label"].get(lb, {}).get("top1", 0.0) for lb in labels]
        for s in static
    ])

    fig, ax = plt.subplots(figsize=(max(4.5, len(labels) * 0.7), max(3.2, len(models) * 0.45)))
    cmap = mpl.cm.get_cmap("RdYlGn")
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models, fontsize=6)
    ax.set_title("Per-label Top-1 accuracy (static task)", fontsize=7,
                 fontweight="bold", pad=4)

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix[i, j]
            tc = "white" if val < 0.3 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=5.5, color=tc)

    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("Accuracy", fontsize=6)
    cb.ax.tick_params(labelsize=6)

    fig.tight_layout()
    save_pub(fig, "fig2_perlabel_heatmap")
    plt.close(fig)


# ── Fig 3 — Dissociation scatter (Static) ────────────────────────────────────

def fig3_dissociation(static: list[dict]) -> None:
    if len(static) < 2:
        print("  [跳过 Fig3] static 数据不足 2 个模型")
        return

    models   = [s["model_label"] for s in static]
    slotcov  = [s["slot_coverage"] for s in static]
    top1     = [s["top1"] for s in static]

    fig, ax = plt.subplots(figsize=(3.5, 3.0))
    ax.scatter(slotcov, top1, s=55, color=C_BLUE, alpha=0.85,
               edgecolors="white", linewidths=0.5, zorder=3)

    for name, x, y in zip(models, slotcov, top1):
        ax.annotate(name, xy=(x, y), xytext=(x + 0.005, y + 0.010), fontsize=5.5)

    # 高亮最高 SlotCov 和最高 Top-1
    best_slot_idx = int(np.argmax(slotcov))
    best_top1_idx = int(np.argmax(top1))
    ax.scatter([slotcov[best_slot_idx]], [top1[best_slot_idx]], s=80,
               color=C_ORANGE, zorder=4, label="Highest SlotCov")
    ax.scatter([slotcov[best_top1_idx]], [top1[best_top1_idx]], s=80,
               color=C_GREEN, zorder=4, label="Highest Top-1")
    if best_slot_idx != best_top1_idx:
        ax.annotate("", xy=(slotcov[best_top1_idx], top1[best_top1_idx]),
                    xytext=(slotcov[best_slot_idx], top1[best_slot_idx]),
                    arrowprops=dict(arrowstyle="<->", color=C_RED, lw=1.0))
        mid_x = (slotcov[best_slot_idx] + slotcov[best_top1_idx]) / 2
        mid_y = (top1[best_slot_idx] + top1[best_top1_idx]) / 2
        ax.text(mid_x + 0.005, mid_y, "dissociation", fontsize=6, color=C_RED, style="italic")

    ax.set_xlabel("Slot Coverage (SlotCov)", fontsize=7)
    ax.set_ylabel("Top-1 Diagnostic Accuracy", fontsize=7)
    ax.set_title("Accuracy–depth dissociation\n(static task)", fontsize=7, fontweight="bold", pad=4)
    ax.legend(fontsize=6, loc="lower right")
    fig.tight_layout()
    save_pub(fig, "fig3_dissociation")
    plt.close(fig)


# ── Fig 4 — Bootstrap CI forest plot (Static) ────────────────────────────────

def fig4_forest(static: list[dict]) -> None:
    if not static:
        print("  [跳过 Fig4] 无 static 数据")
        return

    models = [s["model_label"] for s in static]
    means  = [s["bootstrap_top1"]["mean"]  for s in static]
    lo     = [s["bootstrap_top1"]["ci_lo"] for s in static]
    hi     = [s["bootstrap_top1"]["ci_hi"] for s in static]

    order  = np.argsort(means)[::-1]
    models = [models[i] for i in order]
    means  = [means[i]  for i in order]
    lo     = [lo[i]     for i in order]
    hi     = [hi[i]     for i in order]

    n = len(models)
    y = np.arange(n)

    fig, ax = plt.subplots(figsize=(5.0, max(3.0, n * 0.45)))
    for i in range(n):
        ax.plot([lo[i], hi[i]], [y[i], y[i]], color=C_LBLUE, lw=1.4, zorder=2)
        ax.scatter(means[i], y[i], s=30, color=C_BLUE, zorder=3,
                   edgecolors="white", linewidths=0.5)
        ax.text(hi[i] + 0.005, y[i],
                f"{means[i]:.3f} [{lo[i]:.3f}, {hi[i]:.3f}]",
                va="center", fontsize=5.5, color="#333333")

    ax.set_yticks(y)
    ax.set_yticklabels(models, fontsize=6)
    ax.set_xlim(0.0, 1.4)
    ax.set_xlabel("Top-1 Accuracy (95% bootstrap CI)", fontsize=7)
    ax.set_title("Static task — bootstrap confidence intervals", fontsize=7,
                 fontweight="bold", pad=4)
    ax.axvline(0.5, color=C_GREY, lw=0.6, ls="--", zorder=0, label="chance = 0.5")
    ax.legend(fontsize=6, loc="lower right")
    ax.invert_yaxis()
    fig.tight_layout()
    save_pub(fig, "fig4_bootstrap_ci")
    plt.close(fig)


# ── Fig 6 — Slot taxonomy（benchmark 固定数据）────────────────────────────────

def fig6_slots() -> None:
    cats = [
        "Basic demographics", "Safety & emergency", "Personality (AMPD)",
        "Sleep complaint", "Quantitative sleep", "Sleep differential Dx",
        "Psychiatric differential", "Substance use", "Psychiatric history",
        "Prior investigations", "Medical history", "Family & function",
    ]
    counts = [6, 5, 5, 6, 8, 5, 7, 5, 4, 2, 2, 3]
    safety = [False, True, False, False, False, False, False,
              False, False, False, False, False]
    colors = [C_RED if s else C_BLUE for s in safety]

    n = len(cats)
    y = np.arange(n)
    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    ax.barh(y, counts, color=colors, alpha=0.85, linewidth=0)
    ax.set_yticks(y)
    ax.set_yticklabels(cats, fontsize=6)
    ax.set_xlabel("Number of slots", fontsize=7)
    ax.set_title("Slot taxonomy (12 categories)", fontsize=7, fontweight="bold", pad=4)
    ax.invert_yaxis()
    for i, v in enumerate(counts):
        ax.text(v + 0.08, i, str(v), va="center", fontsize=6)
    legend_els = [
        mpatches.Patch(color=C_RED,  label="Safety-critical"),
        mpatches.Patch(color=C_BLUE, label="Standard slots"),
    ]
    ax.legend(handles=legend_els, fontsize=6, loc="lower right")
    fig.tight_layout()
    save_pub(fig, "fig6_slot_taxonomy")
    plt.close(fig)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--figs", nargs="*", type=int, default=[1, 2, 3, 4, 6],
                   help="要生成的图编号，默认全部 1 2 3 4 6")
    args = p.parse_args()

    static, dynamic = load_summaries()
    print(f"加载到 static 数据: {len(static)} 个模型")
    print(f"加载到 dynamic 数据: {len(dynamic)} 个模型")
    print(f"输出目录: {OUT}")
    print()

    figs = set(args.figs)
    if 1 in figs: fig1_dynamic(dynamic)
    if 2 in figs: fig2_heatmap(static)
    if 3 in figs: fig3_dissociation(static)
    if 4 in figs: fig4_forest(static)
    if 6 in figs: fig6_slots()

    print("\n全部完成。")


if __name__ == "__main__":
    main()
