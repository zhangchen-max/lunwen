from __future__ import annotations

import argparse
import random
from collections import defaultdict
from pathlib import Path

from eval.load import load_cases, load_ontology


def main() -> int:
    parser = argparse.ArgumentParser(description="Build train/dev/test splits")
    parser.add_argument("--cases", type=Path, default=Path("data/cases.jsonl"))
    parser.add_argument("--ontology", type=Path, default=Path("ontology"))
    parser.add_argument("--train-ratio", type=float, default=0.6)
    parser.add_argument("--dev-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--out-dir", type=Path, default=Path("data/splits"))
    args = parser.parse_args()

    if args.train_ratio + args.dev_ratio >= 1.0:
        raise SystemExit("train_ratio + dev_ratio must be < 1.0")

    ont = load_ontology(args.ontology)
    case_records = load_cases(args.cases, ont)

    by_label = defaultdict(list)
    for case in case_records:
        by_label[case.label].append(case.case_id)

    rng = random.Random(args.seed)
    train_ids, dev_ids, test_ids = [], [], []

    for _, ids in by_label.items():
        rng.shuffle(ids)
        n = len(ids)
        n_train = max(1, int(n * args.train_ratio)) if n >= 3 else max(0, int(n * args.train_ratio))
        n_dev = max(1, int(n * args.dev_ratio)) if n - n_train >= 2 else max(0, int(n * args.dev_ratio))

        train_ids.extend(ids[:n_train])
        dev_ids.extend(ids[n_train : n_train + n_dev])
        test_ids.extend(ids[n_train + n_dev :])

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "train_ids.txt").write_text("\n".join(sorted(train_ids)) + "\n", encoding="utf-8")
    (args.out_dir / "dev_ids.txt").write_text("\n".join(sorted(dev_ids)) + "\n", encoding="utf-8")
    (args.out_dir / "test_ids.txt").write_text("\n".join(sorted(test_ids)) + "\n", encoding="utf-8")

    print(
        f"Splits written to {args.out_dir} (train/dev/test = {len(train_ids)}/{len(dev_ids)}/{len(test_ids)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
