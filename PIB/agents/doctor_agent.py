from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from models.adapters.base import ChatAdapter
from models.parsing import JsonParseError, parse_with_retry, parse_with_retry_diagnostics


ALL_LABELS = [
    "ADJ",
    "PGD",
    "OCD",
    "BDD",
    "OS_OCRD",
    "SSD",
    "PMDD",
    "IED",
    "BPD",
    "OCPD",
    "OTHER",
]


@dataclass
class DoctorState:
    asked_slots: List[str] = field(default_factory=list)
    observations: Dict[str, Any] = field(default_factory=dict)
    turn: int = 0


def _duration_to_months(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(day|days|week|weeks|month|months|year|years)\s*$", value)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    if unit.startswith("day"):
        return num / 30.0
    if unit.startswith("week"):
        return num / 4.0
    if unit.startswith("month"):
        return num
    return num * 12.0


class BaseDoctorAgent:
    def next_action(
        self,
        minimal_cc: str,
        state: DoctorState,
        allowed_slots: Sequence[str],
        must_ask_slots: Sequence[str] | None = None,
        forbidden_slots: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class DummyDoctorAgent(BaseDoctorAgent):
    """No-oracle baseline: only sees chief complaint, current state, and ontology slots."""

    SCREENING_PRIORITY = [
        "duration",
        "onset_time",
        "impairment_school",
        "impairment_work",
        "impairment_social",
        "self_harm_ideation",
        "violence_ideation",
        "substance_misuse",
        "psychosis_like_symptom",
        "stressor_present",
        "loss_event_present",
        "intrusive_thoughts",
        "ritual_behavior_present",
        "appearance_preoccupation",
        "somatic_symptom_distress",
        "menstrual_cycle_link",
        "anger_outbursts",
        "longstanding_pattern",
        "perfectionism_trait",
    ]

    KEYWORD_PRIORITIES = [
        (r"脏|污染|洗手|仪式|反复", ["intrusive_thoughts", "ritual_behavior_present"]),
        (r"外貌|鼻子|脸|难看|皮肤|身材", ["appearance_preoccupation", "mirror_checking"]),
        (r"月经|经前|周期", ["menstrual_cycle_link", "mood_lability"]),
        (r"愤怒|暴怒|发火|砸东西", ["anger_outbursts", "aggression_property_damage"]),
        (r"自伤|伤害自己|活着没意思", ["self_harm_ideation", "abandonment_sensitivity"]),
        (r"丧失|去世|离世|哀伤", ["loss_event_present", "grief_intensity"]),
        (r"压力|应激|换岗|分手", ["stressor_present", "duration"]),
        (r"身体|疼|疲劳|不适", ["somatic_symptom_distress", "medical_reassurance_seeking"]),
        (r"完美|秩序|控制", ["perfectionism_trait", "longstanding_pattern"]),
    ]

    def __init__(self, seed: int = 1234, max_asks_before_final: int = 6):
        self.seed = seed
        self.max_asks_before_final = max_asks_before_final

    @staticmethod
    def visible_input_context(
        minimal_cc: str,
        state: DoctorState,
        allowed_slots: Sequence[str],
    ) -> Dict[str, Any]:
        return {
            "minimal_cc": minimal_cc,
            "state": {
                "asked_slots": list(state.asked_slots),
                "observations": dict(state.observations),
                "turn": state.turn,
            },
            "allowed_slots": list(allowed_slots),
        }

    @classmethod
    def _candidate_order(cls, minimal_cc: str, allowed_slots: Sequence[str]) -> List[str]:
        ordered: List[str] = []
        allowed_set = set(allowed_slots)

        def add(slot_id: str) -> None:
            if slot_id in allowed_set and slot_id not in ordered:
                ordered.append(slot_id)

        for pattern, slots in cls.KEYWORD_PRIORITIES:
            if re.search(pattern, minimal_cc):
                for slot_id in slots:
                    add(slot_id)

        for slot_id in cls.SCREENING_PRIORITY:
            add(slot_id)

        for slot_id in allowed_slots:
            add(slot_id)

        return ordered

    def next_action(
        self,
        minimal_cc: str,
        state: DoctorState,
        allowed_slots: Sequence[str],
        must_ask_slots: Sequence[str] | None = None,
        forbidden_slots: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        context = self.visible_input_context(minimal_cc, state, allowed_slots)
        visible_slots = [
            slot_id for slot_id in context["allowed_slots"]
            if slot_id not in set(forbidden_slots or [])
        ]
        candidate_order = self._candidate_order(
            minimal_cc=context["minimal_cc"],
            allowed_slots=visible_slots,
        )

        for slot_id in candidate_order:
            if slot_id not in state.asked_slots:
                if state.turn >= self.max_asks_before_final:
                    break
                return {"action": "ASK", "slot_id": slot_id, "utterance": f"请描述一下关于 {slot_id} 的情况。"}

        if state.turn >= self.max_asks_before_final:
            return {"action": "FINAL", "final_output": self._build_final(state.observations)}

        candidates = [s for s in candidate_order if s not in state.asked_slots]
        if not candidates:
            return {"action": "FINAL", "final_output": self._build_final(state.observations)}

        rng = random.Random(self.seed + len(state.asked_slots) * 17)
        slot_id = candidates[rng.randrange(len(candidates))]
        return {"action": "ASK", "slot_id": slot_id, "utterance": f"我想继续了解 {slot_id}。"}

    def _build_final(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        ranked = self._rank_labels(observations)
        confidences = [0.56, 0.18, 0.12, 0.08, 0.06]
        diagnosis_topk = [
            {"label": label, "confidence": conf}
            for label, conf in zip(ranked[:5], confidences)
        ]

        risk_flags = {
            "suicide": bool(observations.get("self_harm_ideation") is True),
            "violence": bool(observations.get("anger_outbursts") is True),
            "psychosis": bool(observations.get("psychosis_like_symptom") is True),
            "substance": bool(observations.get("substance_misuse") is True),
        }

        justifications: List[Dict[str, Any]] = []
        for slot_id, value in observations.items():
            if value in (True, "moderate", "severe", "clear_link"):
                justifications.append(
                    {"claim": f"观察到 {slot_id} 异常", "support_slots": [slot_id]}
                )
            if len(justifications) >= 3:
                break

        if not justifications:
            justifications = [{"claim": "信息有限，需进一步评估", "support_slots": []}]

        return {
            "diagnosis_topk": diagnosis_topk,
            "slot_predictions": observations,
            "risk_flags": risk_flags,
            "justification": justifications,
            "next_steps": [
                {
                    "type": "suggest_assessment",
                    "text": "建议进一步结构化评估与面谈确认。",
                }
            ],
            "calibration": {
                "uncertainty_statement": "当前结论基于有限访谈信息，需进一步评估。"
            },
        }

    def _rank_labels(self, obs: Dict[str, Any]) -> List[str]:
        duration_months = _duration_to_months(obs.get("duration"))

        if obs.get("menstrual_cycle_link") == "clear_link":
            return ["PMDD", "BPD", "ADJ", "IED", "OTHER"]
        if obs.get("appearance_preoccupation") is True:
            return ["BDD", "OCD", "OS_OCRD", "SSD", "OTHER"]
        if obs.get("intrusive_thoughts") is True and obs.get("ritual_behavior_present") is True:
            return ["OCD", "OCPD", "BDD", "SSD", "OTHER"]
        if obs.get("ritual_behavior_present") is True and obs.get("intrusive_thoughts") is False:
            return ["OS_OCRD", "OCD", "BDD", "ADJ", "OTHER"]
        if obs.get("somatic_symptom_distress") in {"moderate", "severe"}:
            return ["SSD", "ADJ", "OCD", "PMDD", "OTHER"]
        if obs.get("loss_event_present") is True and duration_months is not None and duration_months >= 12:
            return ["PGD", "ADJ", "BPD", "PMDD", "OTHER"]
        if obs.get("stressor_present") is True:
            return ["ADJ", "SSD", "PMDD", "PGD", "OTHER"]
        if obs.get("anger_outbursts") is True:
            return ["IED", "BPD", "ADJ", "PMDD", "OTHER"]
        if obs.get("self_harm_ideation") is True and obs.get("longstanding_pattern") is True:
            return ["BPD", "PMDD", "IED", "ADJ", "OTHER"]
        if obs.get("perfectionism_trait") is True and obs.get("longstanding_pattern") is True:
            return ["OCPD", "OCD", "ADJ", "BDD", "OTHER"]
        return ["OTHER", "ADJ", "SSD", "PMDD", "OCD"]


class LLMDoctorAgent(BaseDoctorAgent):
    def __init__(self, adapter: ChatAdapter, temperature: float = 0.0):
        self.adapter = adapter
        self.temperature = temperature

    def next_action(
        self,
        minimal_cc: str,
        state: DoctorState,
        allowed_slots: Sequence[str],
        must_ask_slots: Sequence[str] | None = None,
        forbidden_slots: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        visible_slots = [
            slot_id for slot_id in allowed_slots
            if slot_id not in set(forbidden_slots or [])
        ]
        action_prompt = self._build_action_prompt(minimal_cc, state, visible_slots, must_ask_slots or [])

        def _call(p: str) -> str:
            return self.adapter.complete([
                {"role": "system", "content": "你是精神科诊断访谈助手，只能输出JSON。"},
                {"role": "user", "content": p},
            ], temperature=self.temperature)

        action_result = parse_with_retry_diagnostics(_call, action_prompt, max_retries=2)
        if action_result.value is None:
            return {
                "action": "PARSE_ERROR",
                "error": action_result.diagnostics.error_message or "action parse failed",
                "_parse_diagnostics": action_result.diagnostics.to_dict(),
            }

        action = action_result.value
        action_kind = action.get("action")
        if action_kind not in {"ASK", "FINAL"}:
            return {
                "action": "PARSE_ERROR",
                "error": "action must be ASK or FINAL",
                "_parse_diagnostics": {
                    "ok": False,
                    "error_code": "schema_error",
                    "retry_count": action_result.diagnostics.retry_count,
                    "raw_response_snippet": action_result.diagnostics.raw_response_snippet,
                    "error_message": "action must be ASK or FINAL",
                },
            }
        if action_kind == "ASK" and not action.get("slot_id"):
            return {
                "action": "PARSE_ERROR",
                "error": "ASK action requires slot_id",
                "_parse_diagnostics": {
                    "ok": False,
                    "error_code": "schema_error",
                    "retry_count": action_result.diagnostics.retry_count,
                    "raw_response_snippet": action_result.diagnostics.raw_response_snippet,
                    "error_message": "ASK action requires slot_id",
                },
            }
        if action_kind == "FINAL":
            final_prompt = self._build_final_prompt(state)
            final_result = parse_with_retry_diagnostics(_call, final_prompt, max_retries=2)
            return {
                "action": "FINAL",
                "final_output": final_result.value,
                "_parse_diagnostics": action_result.diagnostics.to_dict(),
                "_final_parse_diagnostics": final_result.diagnostics.to_dict(),
            }
        return action

    @staticmethod
    def _build_action_prompt(
        minimal_cc: str,
        state: DoctorState,
        allowed_slots: Sequence[str],
        must_ask_slots: Sequence[str],
    ) -> str:
        unasked_must = [s for s in must_ask_slots if s not in state.asked_slots]
        return (
            "你是精神科访谈医生，必须输出一个 JSON 动作，不得输出任何其他文字。\n"
            "可选动作：ASK 或 FINAL。\n"
            "ASK 结构: {\"action\":\"ASK\",\"slot_id\":\"<从可用slot列表中选>\",\"utterance\":\"<中文问诊话语>\"}\n"
            "FINAL 结构: {\"action\":\"FINAL\"}\n\n"
            f"【主诉】{minimal_cc}\n"
            f"【已收集观察】{json.dumps(state.observations, ensure_ascii=False)}\n"
            f"【已问过的slot（禁止重复）】{state.asked_slots}\n"
            f"【尚未问到的必问slot】{unasked_must}\n"
            f"【可用slot列表（slot_id只能从此列表选，不得使用任何其他值）】\n{list(allowed_slots)}\n\n"
            "规则：\n"
            "1. slot_id 必须严格从【可用slot列表】中选择，不得自造任何slot名称。\n"
            "2. 不得选择【已问过的slot】中的任何slot_id。\n"
            "3. 优先问【尚未问到的必问slot】。\n"
            "4. 若已收集足够信息可以诊断，输出 {\"action\":\"FINAL\"}。\n"
            "只输出 JSON，不要输出任何解释。"
        )

    @staticmethod
    def _build_final_prompt(state: DoctorState) -> str:
        return (
            "根据以下观察，输出诊断结果 JSON。只输出 JSON，不要任何其他文字。\n\n"
            f"asked_slots: {state.asked_slots}\n"
            f"observations: {json.dumps(state.observations, ensure_ascii=False)}\n\n"
            "严格按照以下格式输出（所有字段必须存在，类型必须完全匹配）：\n"
            "{\n"
            "  \"diagnosis_topk\": [\n"
            "    {\"label\": \"OCD\", \"confidence\": 0.7},\n"
            "    {\"label\": \"OTHER\", \"confidence\": 0.3}\n"
            "  ],\n"
            "  \"slot_predictions\": {\"onset_time\": \"3 months\"},\n"
            "  \"risk_flags\": {\"suicide\": false, \"violence\": false, \"psychosis\": false, \"substance\": false},\n"
            "  \"justification\": [\n"
            "    {\"claim\": \"患者存在强迫思维\", \"support_slots\": [\"intrusive_thoughts\"]}\n"
            "  ],\n"
            "  \"next_steps\": [\n"
            "    {\"type\": \"suggest_assessment\", \"text\": \"建议进一步结构化评估。\"}\n"
            "  ],\n"
            "  \"calibration\": {\"uncertainty_statement\": \"基于有限访谈，需进一步确认。\"}\n"
            "}\n\n"
            "规则：\n"
            "1. diagnosis_topk 必须是对象数组，每个对象含 label（字符串）和 confidence（0-1浮点数）。\n"
            "2. diagnosis_topk 中必须包含 OTHER 标签。\n"
            "3. label 只能从以下值选择：ADJ, PGD, OCD, BDD, OS_OCRD, SSD, PMDD, IED, BPD, OCPD, OTHER。\n"
            "4. risk_flags 必须是对象，包含 suicide/violence/psychosis/substance 四个布尔字段。\n"
            "5. justification 必须是对象数组，每个对象含 claim（字符串）和 support_slots（字符串数组，只能用 asked_slots 中的值）。\n"
            "6. next_steps 必须是对象数组，每个对象含 type 和 text，不得包含处方、用药、立即治疗等内容。\n"
            "7. slot_predictions 用 observations 字典填充即可。\n"
        )


# ---------------------------------------------------------------------------
# SSM-Psychiatrist: 显式 Slot State Machine doctor（P0 实验：同 22 例重跑 + 消融）
# 论文 §III: 四状态 {E,F,R,U} / T1-T3 / Φ(C1∧C2∧C3) / 权威分离（SSM 决定问什么与何时停，LLM 只做表面生成）
# ---------------------------------------------------------------------------

# Φ 的 C2 条件：三个安全关键槽（论文：suicidal ideation, self-harm, violence risk）
SSM_SAFETY_SLOTS = ["self_harm_ideation", "suicide_plan", "violence_ideation"]
# Φ 的 C3 条件：functional_impairment 域的 Dx-path 槽（DSM-5-TR Criterion B/C）
SSM_DX_PATH_SLOTS = [
    "impairment_school",
    "impairment_work",
    "impairment_social",
    "daily_routine_impairment",
]
# T1 风险分层触发时额外提升的客观史槽
SSM_T1_EXTRA_SLOTS = ["substance_misuse", "psychosis_like_symptom", "trauma_exposure"]
# T3 共病 / 鉴别诊断触发时额外加入的 ddx 槽
SSM_T3_EXTRA_SLOTS = [
    "comorbid_anxiety_history",
    "family_psych_history",
    "previous_treatment_response",
]


@dataclass
class SSMConfig:
    """控制 SSM 消融变体（A2/A3/A4）的开关。完整 SSM = 全部 True。"""
    use_t1: bool = True
    use_t2: bool = True
    use_t3: bool = True
    use_phi: bool = True            # Φ 终止准则 (C1∧C2∧C3)
    four_state: bool = True         # 四状态(E/F/R/U) vs 二状态(E/F)
    safety_slots: Sequence[str] = tuple(SSM_SAFETY_SLOTS)
    dx_path_slots: Sequence[str] = tuple(SSM_DX_PATH_SLOTS)


class SSMDoctorAgent(BaseDoctorAgent):
    """确定性槽位状态机 + LLM 表面生成器（authority separation）。

    SSM 层负责：四状态跟踪、T1-T3 议程重排、Φ 终止判定；LLM 执行层仅生成
    自然语言问句与最终诊断 JSON。消融变体通过 SSMConfig 单变量开关实现。
    """

    def __init__(self, adapter: ChatAdapter, temperature: float = 0.0, config: SSMConfig | None = None, max_turns: int = 15):
        self.adapter = adapter
        self.temperature = temperature
        self.config = config or SSMConfig()
        self.max_turns = max_turns

    # ---- 状态机核心 ----------------------------------------------------
    def _infer_state(self, slot_id: str, state: DoctorState) -> str:
        """根据 patient 已给出的观察推断该 slot 的四状态之一。"""
        if slot_id not in state.observations:
            return "E"
        val = state.observations[slot_id]
        if isinstance(val, str) and val.strip() in ("refused", "拒绝"):
            return "R" if self.config.four_state else "E"
        if val == "unknown" or val is None:
            return "U" if self.config.four_state else "E"
        return "F"

    def _signals(self, state: DoctorState):
        """从已观察值中提取 T1(风险) 与 T3(共病) 触发信号。"""
        risk_signal = any(
            state.observations.get(k) in (True, "true", "clear_link")
            for k in ("stressor_present", "loss_event_present", "trauma_exposure")
        )
        comorbidity = (
            sum(
                1
                for s, v in state.observations.items()
                if s not in self.config.safety_slots and v in (True, "moderate", "severe")
            )
            >= 2
        )
        return risk_signal, comorbidity

    def _agenda(self, state, allowed_slots, must_ask_slots):
        """构建待问议程（已排除已问 slot），按 SSM 优先级与 T1-T3 触发重排。"""
        cfg = self.config
        allowed = set(allowed_slots)
        must = list(must_ask_slots or [])
        risk_signal, comorbidity = self._signals(state)

        # 基础优先级: safety -> must_ask -> dx_path（A3 去掉 Φ 时不强制 safety/dx_path）
        if cfg.use_phi:
            base = list(cfg.safety_slots) + must + list(cfg.dx_path_slots)
        else:
            base = list(must)

        # T1: 风险分层触发，提升客观史槽到安全槽之后、必问之前
        if cfg.use_t1 and risk_signal:
            t1 = SSM_T1_EXTRA_SLOTS
            base = (list(cfg.safety_slots) + t1 + must + list(cfg.dx_path_slots)) if cfg.use_phi else (list(must) + t1)

        # T2: A-criteria gating —— use_phi 时确保 dx_path 严格置于 must_ask 之后（基础顺序已隐含；
        #      关闭时允许 ddx/extra 与 must 交错，模拟缺乏结构化 gate 的退化行为）
        if not cfg.use_t2:
            # 打乱 gate：把 dx_path 与 T1/T3 extra 直接拼在 must 之后即视为无强制排序约束
            core = (list(cfg.safety_slots) + must) if cfg.use_phi else list(must)
            tail = list(cfg.dx_path_slots)
            if cfg.use_t1 and risk_signal:
                tail = SSM_T1_EXTRA_SLOTS + tail
            base = core + tail

        # T3: 共病信号触发，追加鉴别诊断槽
        if cfg.use_t3 and comorbidity:
            base = base + SSM_T3_EXTRA_SLOTS

        # 去重保序 + 排除已问
        seen: set = set()
        ordered: List[str] = []
        for s in base:
            if s in allowed and s not in state.asked_slots and s not in seen:
                ordered.append(s)
                seen.add(s)
        # 兜底：二状态(A4)下 unknown 不计入覆盖，若核心议程已问完但 Φ 仍未满足，
        # 继续追问其余 allowed slot 直至 max_turns，使"四状态 vs 二状态"的 turns/覆盖差异可观测。
        if len(ordered) < self.max_turns:
            for s in allowed_slots:
                if s not in state.asked_slots and s not in seen:
                    ordered.append(s)
                    seen.add(s)
        return ordered

    def _phi_satisfied(self, state, allowed_slots, must_ask_slots) -> bool:
        """Φ = C1(coverage) ∧ C2(safety) ∧ C3(dx_path)。A3 去掉 Φ 时退化为仅 must_ask 覆盖。"""
        cfg = self.config
        allowed = set(allowed_slots)

        def done(slot: str) -> bool:
            return self._infer_state(slot, state) != "E"

        if not cfg.use_phi:
            # A3: 终止只看必问槽覆盖，不强制安全/诊断路径完成
            return all(done(s) for s in must_ask_slots if s in allowed)
        # 完整 Φ: 安全 + 必问 + 诊断路径 三者全部非 E
        core = list(cfg.safety_slots) + list(must_ask_slots) + list(cfg.dx_path_slots)
        return all(done(s) for s in core if s in allowed)

    # ---- LLM 表面生成 --------------------------------------------------
    def _generate_question(self, slot_id: str, state: DoctorState, minimal_cc: str) -> str:
        prompt = (
            "你是精神科访谈医生，请用一句自然、共情的中文问句向患者采集以下临床信息。"
            "只输出问句本身，不要输出任何解释或 JSON。\n\n"
            f"【主诉】{minimal_cc}\n"
            f"【本次要采集的槽】{slot_id}\n"
            f"【已收集观察】{json.dumps(state.observations, ensure_ascii=False)}\n"
        )
        try:
            text = self.adapter.complete(
                [
                    {"role": "system", "content": "你是精神科访谈医生，只输出一句中文问句。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
            )
            return text.strip().strip('"').strip("'")
        except Exception:
            return f"我想进一步了解您的情况，关于「{slot_id}」。"

    def _final_action(self, state: DoctorState) -> Dict[str, Any]:
        prompt = LLMDoctorAgent._build_final_prompt(state)

        def _call(p: str) -> str:
            return self.adapter.complete(
                [
                    {"role": "system", "content": "你是精神科诊断访谈助手，只能输出JSON。"},
                    {"role": "user", "content": p},
                ],
                temperature=self.temperature,
            )

        result = parse_with_retry_diagnostics(_call, prompt, max_retries=2)
        return {
            "action": "FINAL",
            "final_output": result.value,
            "_final_parse_diagnostics": result.diagnostics.to_dict(),
        }

    # ---- 主接口（兼容 run_dynamic 的 next_action 契约）------------------
    def next_action(
        self,
        minimal_cc: str,
        state: DoctorState,
        allowed_slots: Sequence[str],
        must_ask_slots: Sequence[str] | None = None,
        forbidden_slots: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        allowed = set(allowed_slots)
        must = list(must_ask_slots or [])

        # 硬上限：与 run_dynamic 的 max_turns 协同，最后一轮必须终止
        if state.turn >= self.max_turns:
            return self._final_action(state)
        # Φ 满足（或 A3 退化为 must_ask 覆盖满足）-> 终止
        if self._phi_satisfied(state, allowed, must):
            return self._final_action(state)

        agenda = self._agenda(state, allowed_slots, must)
        forbidden = set(forbidden_slots or [])
        agenda = [s for s in agenda if s not in forbidden]
        if not agenda:
            return self._final_action(state)

        slot_id = agenda[0]
        utterance = self._generate_question(slot_id, state, minimal_cc)
        return {"action": "ASK", "slot_id": slot_id, "utterance": utterance}
