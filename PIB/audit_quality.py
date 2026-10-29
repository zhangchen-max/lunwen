import json, collections
with open("data/cases.jsonl",encoding="utf-8") as f:
    cases=[json.loads(l) for l in f if l.strip()]

# ---- 1. 脚本-真值覆盖度 + 内部一致性 ----
truth_keywords = {
    # slot_id -> (肯定词, 否定/缺如词) 仅用于布尔/存在类槽的粗判
    "ritual_behavior_present": (["洗手","仪式","反复做","检查"],["不","没"]),
    "contamination_fear": (["脏","污染","怕"],["不","没"]),
    "intrusive_thoughts": (["念头","想法会冒"],["没有这种"]),
    "self_harm_ideation": (["自伤","伤害自己"],["没","不"]),
    "violence_ideation": (["伤人","打人","暴力"],["没","不"]),
    "substance_misuse": (["喝酒","用","药","吸"],["不","没","戒"]),
    "stressor_present": (["因为","事","压力","冲突"],["没有","不清楚","记不清"]),
}
mismatch=[]; uncovered=[]
script_turns=[]; script_chars=[]
for c in cases:
    st=c["slot_truth"]; ps=c["patient_script"]
    # 覆盖度：slot_truth 的每个 slot_id 是否都有脚本应答
    for sid in st:
        if sid not in ps or not ps[sid]:
            uncovered.append((c["case_id"],sid))
    # 一致性：对已知布尔槽做粗判
    for sid,(pos,neg) in truth_keywords.items():
        if sid in st and sid in ps:
            val=st[sid]
            v = val.get("value") if isinstance(val,dict) else val
            text=" ".join(ps[sid])
            is_true = (v is True) or (isinstance(v,str) and v.lower() in ("true","present","yes"))
            is_false= (v is False) or (isinstance(v,str) and v.lower() in ("false","absent","no","none","unknown"))
            if is_true and any(w in text for w in neg) and not any(w in text for w in pos):
                mismatch.append((c["case_id"],sid,"truth=True但脚本偏否定",text[:30]))
            if is_false and any(w in text for w in pos) and not any(w in text for w in neg):
                mismatch.append((c["case_id"],sid,"truth=False但脚本偏肯定",text[:30]))
    # 脚本丰富度
    n=sum(len(v) for v in ps.values()); ch=sum(len(x) for v in ps.values() for x in v)
    script_turns.append(n); script_chars.append(ch)

print("=== 1. 脚本-真值覆盖 ===")
print("slot_truth 有但脚本缺失的条目数:",len(uncovered))
if uncovered[:10]: print("  样例:",uncovered[:10])
print("\n=== 2. 内部一致性粗判（可能误报，需人工）===")
print("疑似不一致条目数:",len(mismatch))
for m in mismatch[:15]: print("  ",m)

print("\n=== 3. 脚本丰富度（质量 proxy）===")
import statistics as st_
print(f"每例平均应答条数: {st_.mean(script_turns):.1f}  中位数: {st_.median(script_turns)}")
print(f"每例平均脚本字数: {st_.mean(script_chars):.0f}  中位数: {st_.median(script_chars)}")
print(f"最短的5例:",sorted(zip([c['case_id'] for c in cases],script_chars),key=lambda x:x[1])[:5])

# ---- 4. 类内异质性：每类 distinct slot_truth 组合数 ----
print("\n=== 4. 类内异质性 ===")
by_label=collections.defaultdict(list)
for c in cases: by_label[c["label"]].append(c)
for lab,cs in by_label.items():
    combos=set()
    for c in cs:
        key=tuple(sorted((k, (v.get("value") if isinstance(v,dict) else v)) for k,v in c["slot_truth"].items()))
        combos.add(key)
    print(f"  {lab:8s} n={len(cs)}  不同槽值组合={len(combos)}")

# ---- 5. OTHER 类鉴别诊断质量 ----
print("\n=== 5. OTHER 类（CF-3 鉴别诊断论据）===")
others=[c for c in cases if c["label"]=="OTHER"]
print(f"OTHER 例数={len(others)}")
amb=[c for c in others if c.get("ambiguity")=="ambiguous"]
print(f"  标注 ambiguous 的:{len(amb)}")
ddx_spread=set()
for c in others: ddx_spread.update(c.get("gold_ddx_top5",[]))
print(f"  ddx_top5 涵盖的诊断类别:{sorted(ddx_spread)}")
# OTHER 是否真的'阴性'——看 slot_truth 是否多为 unknown/弱
weak=0
for c in others:
    vals=[ (v.get("value") if isinstance(v,dict) else v) for v in c["slot_truth"].values()]
    if any(v in ("unknown","low","mild","none") for v in vals): weak+=1
print(f"  槽值偏'未知/轻度/无'的例数:{weak}/{len(others)}")
