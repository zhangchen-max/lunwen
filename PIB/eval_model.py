"""
模型评测脚本（Static / Dynamic 两种模式）
==========================================
用法：

  # Static 静态评测
  python eval_model.py --api-key sk-xxx --model-label DeepSeek-V3 --mode static

  # Dynamic 动态评测（先跑 test split 省 token）
  python eval_model.py --api-key sk-xxx --model-label DeepSeek-V3 --mode dynamic --split test

  # 全量 110 条
  python eval_model.py --api-key sk-xxx --model-label DeepSeek-V3 --mode dynamic

  # 换模型（Qwen）
  python eval_model.py --api-key sk-xxx --model-label Qwen-Max \\
    --model qwen-max --endpoint https://dashscope.aliyuncs.com/compatible-mode/v1 --mode static

结果保存在：6.23result/{model_label}/static/ 或 dynamic/
  results.jsonl   原始逐案例结果
  summary.json    汇总指标（用于绘图）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).parent.resolve()
RESULTS_ROOT = PROJECT_ROOT / "6.23result"
sys.path.insert(0, str(PROJECT_ROOT))


# ──────────────────────────────────────────────
# 参数解析
# ──────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model-label", required=True,
                   help="模型显示名称，用作结果文件夹名，例如 DeepSeek-V3、Qwen-Max")
    p.add_argument("--mode", choices=["static", "dynamic"], default="static")
    p.add_argument("--api-key", default=None)
    p.add_argument("--model", default="deepseek-chat")
    p.add_argument("--endpoint", default="https://api.deepseek.com/v1")
    p.add_argument("--split", choices=["all", "train", "dev", "test"], default="all")
    p.add_argument("--input-variant", choices=["minimal_cc", "self_report", "chart_full"],
                   default="self_report")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--max-cases", type=int, default=None)
    p.add_argument("--disable-thinking", action="store_true",
                   help="禁用模型 thinking 模式（Qwen3 等需要）")
    p.add_argument("--provider", default="openai",
                   choices=["openai", "anthropic"],
                   help="API 提供商（默认 openai，Anthropic 模型用 anthropic）")
    return p.parse_args()


# ──────────────────────────────────────────────
# Bootstrap CI
# ──────────────────────────────────────────────

def bootstrap_ci(values: list[float], n_boot: int = 5000, alpha: float = 0.05) -> dict:
    arr = np.array(values)
    rng = random.Random(42)
    boot = [np.mean(rng.choices(arr.tolist(), k=len(arr))) for _ in range(n_boot)]
    return {
        "mean": float(np.mean(arr)),
        "ci_lo": float(np.percentile(boot, 100 * alpha / 2)),
        "ci_hi": float(np.percentile(boot, 100 * (1 - alpha / 2))),
    }


# ──────────────────────────────────────────────
# CF-1 风险等级
# ──────────────────────────────────────────────

def compute_cf1_risk(rows: list[dict]) -> str:
    def has_violation(harm_flags) -> bool:
        if isinstance(harm_flags, dict):
            return any(v is True for v in harm_flags.values())
        if isinstance(harm_flags, list):
            return any(
                (v is True or (isinstance(v, dict) and v.get("violated") is True))
                for v in harm_flags
            )
        return False

    violations = sum(1 for r in rows if has_violation(r.get("harm_flags", {})))
    rate = violations / len(rows) if rows else 0
    if rate == 0:
        return "Low"
    elif rate < 0.1:
        return "Moderate"
    return "High"


# ──────────────────────────────────────────────
# Summary 生成
# ──────────────────────────────────────────────

def make_static_summary(rows: list[dict], model_label: str, model_id: str) -> dict:
    def get(row, key):
        return row.get("metrics", {}).get(key, 0.0)

    by_label = defaultdict(list)
    for r in rows:
        by_label[r.get("label", "?")].append(r)

    per_label = {}
    for label, grp in sorted(by_label.items()):
        per_label[label] = {
            "n": len(grp),
            "top1": float(np.mean([get(r, "top1_acc") for r in grp])),
            "top3": float(np.mean([get(r, "top3_cov") for r in grp])),
        }

    top1_vals = [get(r, "top1_acc") for r in rows]
    return {
        "model_label": model_label,
        "model_id": model_id,
        "eval_date": str(date.today()),
        "mode": "static",
        "n_cases": len(rows),
        "top1": float(np.mean(top1_vals)),
        "top3": float(np.mean([get(r, "top3_cov") for r in rows])),
        "top5": float(np.mean([get(r, "top5_cov") for r in rows])),
        "slot_coverage": float(np.mean([get(r, "required_slot_coverage") for r in rows])),
        "slot_exact_match": float(np.mean([get(r, "slot_exact_match") for r in rows])),
        "bootstrap_top1": bootstrap_ci(top1_vals),
        "per_label": per_label,
    }


def make_dynamic_summary(rows: list[dict], model_label: str, model_id: str) -> dict:
    def get(row, key):
        return row.get("metrics", {}).get(key, 0.0)

    by_label = defaultdict(list)
    for r in rows:
        by_label[r.get("label", "?")].append(r)

    per_label = {}
    for label, grp in sorted(by_label.items()):
        per_label[label] = {
            "n": len(grp),
            "top1": float(np.mean([get(r, "top1_acc") for r in grp])),
            "must_ask_hit_rate": float(np.mean([get(r, "must_ask_hit_rate") for r in grp])),
            "svcl_domain_coverage": float(np.mean([get(r, "svcl_domain_coverage") for r in grp])),
            "avg_turns": float(np.mean([get(r, "turns") for r in grp])),
        }

    return {
        "model_label": model_label,
        "model_id": model_id,
        "eval_date": str(date.today()),
        "mode": "dynamic",
        "n_cases": len(rows),
        "top1": float(np.mean([get(r, "top1_acc") for r in rows])),
        "top3": float(np.mean([get(r, "top3_cov") for r in rows])),
        "must_ask_hit_rate": float(np.mean([get(r, "must_ask_hit_rate") for r in rows])),
        "svcl_domain_coverage": float(np.mean([get(r, "svcl_domain_coverage") for r in rows])),
        "avg_turns": float(np.mean([get(r, "turns") for r in rows])),
        "parse_error_rate": float(sum(1 for r in rows if r.get("parse_error")) / len(rows)),
        "cf1_risk": compute_cf1_risk(rows),
        "per_label": per_label,
    }


# ──────────────────────────────────────────────
# 报告打印
# ──────────────────────────────────────────────

def print_static_report(s: dict) -> None:
    W = 64
    print()
    print("=" * W)
    print(f"  PIB Benchmark — Static  |  {s['model_label']}  |  {s['n_cases']} 条")
    print("=" * W)
    print(f"\n  {'病症':<10} {'n':>3}  {'Top-1':>6}  {'Top-3':>6}")
    print("  " + "-" * 35)
    for label, m in sorted(s["per_label"].items()):
        print(f"  {label:<10} {m['n']:>3}  {m['top1']:>6.1%}  {m['top3']:>6.1%}")
    print("  " + "-" * 35)
    print(f"\n  Top-1       {s['top1']:>7.1%}")
    print(f"  Top-3       {s['top3']:>7.1%}")
    print(f"  SlotCov     {s['slot_coverage']:>7.1%}")
    ci = s["bootstrap_top1"]
    print(f"  Bootstrap   {ci['mean']:.3f} [{ci['ci_lo']:.3f}, {ci['ci_hi']:.3f}]")
    print("=" * W)


def print_dynamic_report(s: dict) -> None:
    W = 68
    print()
    print("=" * W)
    print(f"  PIB Benchmark — Dynamic  |  {s['model_label']}  |  {s['n_cases']} 条")
    print("=" * W)
    print(f"\n  {'病症':<10} {'n':>3}  {'Top-1':>6}  {'必问命中':>8}  {'SVCL':>6}  {'轮次':>5}")
    print("  " + "-" * 50)
    for label, m in sorted(s["per_label"].items()):
        print(f"  {label:<10} {m['n']:>3}  {m['top1']:>6.1%}  "
              f"{m['must_ask_hit_rate']:>8.1%}  {m['svcl_domain_coverage']:>6.1%}  {m['avg_turns']:>5.1f}")
    print("  " + "-" * 50)
    print(f"\n  Top-1            {s['top1']:>7.1%}")
    print(f"  MustAsk 命中率   {s['must_ask_hit_rate']:>7.1%}")
    print(f"  SVCL 覆盖率      {s['svcl_domain_coverage']:>7.1%}")
    print(f"  平均轮次         {s['avg_turns']:>7.1f}")
    print(f"  解析错误率       {s['parse_error_rate']:>7.1%}")
    print(f"  CF-1 风险        {s['cf1_risk']:>7}")
    print("=" * W)


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[错误] 请通过 --api-key 或环境变量 OPENAI_API_KEY 提供 API Key")
        sys.exit(1)
    if args.provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = api_key
    else:
        os.environ["OPENAI_API_KEY"] = api_key
    if args.disable_thinking:
        os.environ["OPENAI_EXTRA_BODY"] = '{"enable_thinking": false}'
        print("Thinking 模式已禁用")

    out_dir = RESULTS_ROOT / args.model_label / args.mode
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    summary_path = out_dir / "summary.json"
    split_arg = None if args.split == "all" else args.split

    print(f"\n模型标签 : {args.model_label}")
    print(f"模型 ID  : {args.model}")
    print(f"模式     : {args.mode}  |  Split: {args.split}")
    print(f"结果目录 : {out_dir}")
    print()

    if args.mode == "static":
        from eval.run_static import run_static
        run_static(
            cases_path=PROJECT_ROOT / "data" / "cases.jsonl",
            rubrics_path=PROJECT_ROOT / "data" / "rubrics.jsonl",
            ontology_dir=PROJECT_ROOT / "ontology",
            output_path=results_path,
            input_variant=args.input_variant,
            oracle_slots=False,
            mode="llm",
            provider=args.provider,
            model=args.model,
            endpoint=args.endpoint if args.provider == "openai" else None,
            cache_root=PROJECT_ROOT / ".cache",
            use_cache=not args.no_cache,
            temperature=args.temperature,
            split=split_arg,
            splits_dir=PROJECT_ROOT / "data" / "splits",
        )
    else:
        from eval.run_dynamic import run_dynamic
        run_dynamic(
            cases_path=PROJECT_ROOT / "data" / "cases.jsonl",
            rubrics_path=PROJECT_ROOT / "data" / "rubrics.jsonl",
            ontology_dir=PROJECT_ROOT / "ontology",
            output_path=results_path,
            doctor_kind="llm",
            provider=args.provider,
            model=args.model,
            endpoint=args.endpoint if args.provider == "openai" else None,
            cache_root=PROJECT_ROOT / ".cache",
            use_cache=not args.no_cache,
            temperature=args.temperature,
            split=split_arg,
            splits_dir=PROJECT_ROOT / "data" / "splits",
            max_cases=args.max_cases,
        )

    rows = [json.loads(l) for l in results_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    if args.mode == "static":
        summary = make_static_summary(rows, args.model_label, args.model)
        print_static_report(summary)
    else:
        summary = make_dynamic_summary(rows, args.model_label, args.model)
        print_dynamic_report(summary)

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsummary.json 已保存至: {summary_path}\n")


if __name__ == "__main__":
    main()
