import json, itertools, re
from collections import defaultdict

cases=[]
with open("data/cases.jsonl",encoding="utf-8") as f:
    for line in f:
        line=line.strip()
        if line: cases.append(json.loads(line))

def norm_st(st):
    return json.dumps({k:st[k].get("value") for k in sorted(st)},ensure_ascii=False,sort_keys=True)
def norm_script(sc):
    return json.dumps({k:tuple(v) for k,v in sorted(sc.items())},ensure_ascii=False,sort_keys=True)

by_label=defaultdict(list)
for c in cases: by_label[c["label"]].append(c)

print("=== DISTINCT clinical scenarios per label (by identical slot_truth) ===")
total_distinct=0
for lab,lst in sorted(by_label.items()):
    groups=defaultdict(list)
    for c in lst:
        groups[norm_st(c["slot_truth"])].append(c)
    nd=len(groups)
    total_distinct+=nd
    # count groups that are 'true dup' (script also identical)
    true_dup_groups=0
    for g,members in groups.items():
        if len(members)>1:
            scripts={norm_script(m["patient_script"]) for m in members}
            if len(scripts)==1:
                true_dup_groups+=1
    print(f"  {lab:10s} n=10  distinct_slot_truth={nd:2d}  (fully-identical-case groups={true_dup_groups})")
print(f"  --> TOTAL distinct slot_truth across 110 = {total_distinct} (vs 110 claimed)")

# show the duplication groups explicitly
print("\n=== slot_truth-identical groups (size>1) with script-identical flag ===")
for lab,lst in sorted(by_label.items()):
    groups=defaultdict(list)
    for c in lst:
        groups[norm_st(c["slot_truth"])].append(c)
    for g,members in groups.items():
        if len(members)>1:
            scripts={norm_script(m["patient_script"]) for m in members}
            flag="SCRIPT-IDENTICAL(true dup)" if len(scripts)==1 else f"script-variants({len(scripts)})"
            ids=[m["case_id"] for m in members]
            # show one minimal_cc
            print(f"  [{lab}] {ids}  -> {flag}")

# check split leakage
print("\n=== SPLIT membership of duplicate pairs ===")
splits={}
for sp in ["train_ids","test_ids","dev_ids"]:
    try:
        with open(f"data/splits/{sp}.txt") as f:
            splits[sp]=set(x.strip() for x in f if x.strip())
    except FileNotFoundError:
        pass
# build global slot_truth map
st_map=defaultdict(list)
for c in cases: st_map[norm_st(c["slot_truth"])].append(c["case_id"])
leak=0
for g,ids in st_map.items():
    if len(ids)>1:
        for a,b in itertools.combinations(ids,2):
            sets=[s for s,name in [("train",splits.get("train_ids")),("test",splits.get("test_ids")),("dev",splits.get("dev_ids"))] if name and a in name]
            setb=[s for s,name in [("train",splits.get("train_ids")),("test",splits.get("test_ids")),("dev",splits.get("dev_ids"))] if name and b in name]
            if sets and setb and sets[0]!=setb[0]:
                leak+=1
                print(f"  LEAK: {a}({sets[0]}) <-> {b}({setb[0]}) share identical slot_truth")
print(f"  duplicate pairs split across different sets: {leak}")

# appended-phrase augmentation pattern detection
print("\n=== block-2 augmentation pattern (minimal_cc = block1 cc + suffix) ===")
suffixes=defaultdict(int)
for c in cases:
    cc=c["info_variants"]["minimal_cc"]
    m=re.search(r"(这半年更明显了|最近更影响日常安排|这段时间我更难忽视它)$",cc)
    if m: suffixes[m.group(1)]+=1
print("  trailing suffixes found:",dict(suffixes))
# show a concrete block1/block2 pair
print("  example PIB_0001 cc:", cases[0]["info_variants"]["minimal_cc"])
for c in cases:
    if c["case_id"]=="PIB_0056":
        print("  example PIB_0056 cc:", c["info_variants"]["minimal_cc"])
