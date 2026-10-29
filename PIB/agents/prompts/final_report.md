根据已获得的信息，请输出 FINAL 的 final_output（严格 JSON），包含：
- diagnosis_topk（含 OTHER）
- risk_flags
- justification（support_slots 必须来自 asked_slots）
- calibration（包含不确定性表达）
- next_steps（仅“建议进一步评估/转介/面谈”等非处方内容）

注意：不得给出处方或剂量。
