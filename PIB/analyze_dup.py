import json, hashlib, itertools
from collections import defaultdict, Counter

path = "data/cases.jsonl"
cases = []
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            cases.append(json.loads(line))

print(f"TOTAL cases: {len(cases)}")

# ---- 1. per-label count ----
by_label = defaultdict(list)
for c in cases:
    by_label[c["label"]].append(c)
print("\n=== cases per label ===")
for lab, lst in sorted(by_label.items(), key=lambda x:-len(x[1])):
    print(f"  {lab:12s} {len(lst)}")

# ---- 2. exact duplicate hashes per category ----
def norm_slot_truth(st):
    # normalize: sort keys, value only
    return json.dumps({k: st[k].get("value") for k in sorted(st.keys())}, ensure_ascii=False, sort_keys=True)

def norm_script(sc):
    flat = {}
    for k, v in sc.items():
        flat[k] = tuple(v)
    return json.dumps(flat, ensure_ascii=False, sort_keys=True)

print("\n=== EXACT duplicates within same label ===")
dup_found = False
for lab, lst in sorted(by_label.items()):
    # hashes
    h_cc = defaultdict(list)
    h_st = defaultdict(list)
    h_prof = defaultdict(list)
    h_script = defaultdict(list)
    for c in lst:
        cc = c["info_variants"]["minimal_cc"]
        st = norm_slot_truth(c["slot_truth"])
        prof = (c["patient_profile"]["age_band"], c["patient_profile"]["gender"], c["patient_profile"]["context"])
        sc = norm_script(c["patient_script"])
        h_cc[cc].append(c["case_id"])
        h_st[st].append(c["case_id"])
        h_prof[prof].append(c["patient_profile"])
        h_script[sc].append(c["case_id"])
    exact_cc = {k:v for k,v in h_cc.items() if len(v)>1}
    exact_st = {k:v for k,v in h_st.items() if len(v)>1}
    exact_sc = {k:v for k,v in h_script.items() if len(v)>1}
    if exact_cc or exact_st or exact_sc:
        dup_found = True
        print(f"\n[{lab}] EXACT DUP:")
        for k,v in exact_cc.items():
            print(f"   minimal_cc identical: {v}")
        for k,v in exact_st.items():
            print(f"   slot_truth identical: {v}")
        for k,v in exact_sc.items():
            print(f"   patient_script identical: {v}")
    else:
        print(f"[{lab}] no exact dup (cc/st/script)")

# ---- 3. near-duplicate (Jaccard on slot_truth value-set + profile) within category ----
print("\n=== NEAR-duplicate pairs (Jaccard of slot-value sets, within label) ===")
def slot_value_set(st):
    return frozenset((k, str(st[k].get("value"))) for k in st)
def profile_tuple(c):
    return (c["patient_profile"]["age_band"], c["patient_profile"]["gender"], c["patient_profile"]["context"], c["info_variants"]["minimal_cc"])

for lab, lst in sorted(by_label.items()):
    pairs = []
    for a, b in itertools.combinations(lst, 2):
        sa = slot_value_set(a["slot_truth"])
        sb = slot_value_set(b["slot_truth"])
        if len(sa | sb) == 0:
            j = 0.0
        else:
            j = len(sa & sb) / len(sa | sb)
        # also compare minimal_cc text similarity (substring containment)
        cca = a["info_variants"]["minimal_cc"]
        ccb = b["info_variants"]["minimal_cc"]
        contain = (cca in ccb) or (ccb in cca)
        if j >= 0.8 or contain:
            pairs.append((j, a["case_id"], b["case_id"], cca, ccb, contain))
    if pairs:
        pairs.sort(reverse=True)
        print(f"\n[{lab}] {len(pairs)} near-dup candidate(s):")
        for j, ida, idb, cca, ccb, contain in pairs[:8]:
            print(f"   J={j:.2f} contain={contain} {ida} vs {idb}")
            print(f"      A: {cca}")
            print(f"      B: {ccb}")

# ---- 4. diversity stats per label ----
print("\n=== diversity per label (distinct profiles / age bands / genders / contexts / distinct minimal_cc) ===")
for lab, lst in sorted(by_label.items()):
    profs = set(profile_tuple(c) for c in lst)
    ages = set(c["patient_profile"]["age_band"] for c in lst)
    genders = set(c["patient_profile"]["gender"] for c in lst)
    ctx = set(c["patient_profile"]["context"] for c in lst)
    ccs = set(c["info_variants"]["minimal_cc"] for c in lst)
    print(f"  {lab:12s} n={len(lst):2d} profs={len(profs):2d} ages={len(ages)} genders={len(genders)} ctx={len(ctx)} distinct_cc={len(ccs)}")

# ---- 5. cross-label near-dup (a case in label X looks like label Y) ----
print("\n=== CROSS-label near-dup (slot-value Jaccard >=0.85, different label) ===")
allpairs=[]
for a, b in itertools.combinations(cases, 2):
    if a["label"] == b["label"]:
        continue
    sa = slot_value_set(a["slot_truth"]); sb = slot_value_set(b["slot_truth"])
    if len(sa|sb)==0: continue
    j = len(sa&sb)/len(sa|sb)
    if j >= 0.85:
        allpairs.append((j, a["case_id"], a["label"], b["case_id"], b["label"]))
allpairs.sort(reverse=True)
print(f"  found {len(allpairs)} cross-label high-overlap pairs")
for j,ia,la,ib,lb in allpairs[:15]:
    print(f"   J={j:.2f} {ia}({la}) <-> {ib}({lb})")
