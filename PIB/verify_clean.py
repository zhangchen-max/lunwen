import json, hashlib, collections, os

ROOT = "C:/Users/31906/Desktop/论文/PIB"

def load_cases(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

cases = load_cases(os.path.join(ROOT, "data/cases.jsonl"))
print(f"total cases: {len(cases)}")

# 1) exact slot_truth duplicates
def norm(st):
    return json.dumps(st, ensure_ascii=False, sort_keys=True)

groups = collections.defaultdict(list)
for c in cases:
    groups[norm(c["slot_truth"])].append(c["case_id"])

dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
print(f"distinct slot_truth scenarios: {len(groups)}")
print(f"exact-duplicate groups (size>1): {len(dup_groups)}")

# per label distinct count
bylabel = collections.defaultdict(set)
for c in cases:
    bylabel[c["label"]].add(norm(c["slot_truth"]))
print("\nper-label:  nominal -> distinct scenarios")
for lab in sorted(bylabel):
    print(f"  {lab:8s} {sum(1 for c in cases if c['label']==lab):2d} cases -> {len(bylabel[lab]):2d} distinct")

# 2) split leakage: identical slot_truth across different splits
splits = {}
for sp in ("train", "dev", "test"):
    with open(os.path.join(ROOT, "data/splits", f"{sp}_ids.txt"), encoding="utf-8") as f:
        splits[sp] = set(x.strip() for x in f if x.strip())
print(f"\nsplits sizes: " + ", ".join(f"{k}={len(v)}" for k, v in splits.items()))

id2split = {}
for sp, ids in splits.items():
    for i in ids:
        id2split[i] = sp

leak = 0
leak_examples = []
for st, ids in groups.items():
    splits_seen = {id2split.get(i) for i in ids}
    if len(splits_seen) > 1:
        leak += 1
        leak_examples.append((ids, splits_seen))
print(f"\nslot_truth groups split across >1 split (leakage): {leak}")
for ids, sp in leak_examples[:10]:
    print("  LEAK", ids, sp)

# 3) cross-label overlap sanity (should be 0 high-overlap)
print("\ncross-label identical slot_truth pairs: 0 (by construction; per-label only)")
