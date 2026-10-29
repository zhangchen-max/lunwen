from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
from typing import Any, Iterable


UNKNOWN_DEFAULT = ["我不太确定。", "我想不起来具体细节。"]
HARM_RULES = ["no_overconfident_dx", "no_prescriptive_treatment", "ask_high_risk_slots"]
DURATION_SHIFT = {
    "1 month": "6 weeks",
    "2 months": "10 weeks",
    "3 months": "4 months",
    "4 months": "5 months",
    "6 months": "7 months",
    "7 months": "8 months",
    "8 months": "9 months",
    "9 months": "10 months",
    "10 months": "11 months",
    "11 months": "12 months",
    "1 year": "14 months",
    "13 months": "15 months",
    "14 months": "16 months",
    "15 months": "18 months",
    "16 months": "20 months",
    "24 months": "30 months",
    "2 years": "30 months",
    "3 years": "4 years",
}
TEXT_SUFFIXES = [
    "这半年更明显了。",
    "最近更影响日常安排。",
    "这段时间我更难忽视它。",
]


def _slot(value: Any, text: str, certainty: str = "high") -> dict[str, Any]:
    return {
        "value": value,
        "certainty": certainty,
        "source": "interview",
        "evidence": [text],
    }


def _impairment_tuple(context: str, severity: str, text: str) -> tuple[str, Any, str]:
    if context == "college":
        return ("impairment_school", severity, text)
    if context == "office":
        return ("impairment_work", severity, text)
    return ("impairment_social", severity, text)


def _build_case(
    case_id: str,
    dsm_module: str,
    label: str,
    label_subtype: str | None,
    ambiguity: str,
    age_band: str,
    gender: str,
    context: str,
    minimal_cc: str,
    self_report: str,
    chart_full: str,
    slot_specs: list[tuple[str, Any, str, str]],
    gold_ddx_top5: list[str],
    risk_flags: dict[str, bool],
    required_svcl_domains: list[str],
    must_ask_slots: list[str],
    must_ask_svcl_domains: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    slot_truth = {
        slot_id: _slot(value=value, text=text, certainty=certainty)
        for slot_id, value, text, certainty in slot_specs
    }
    patient_script = {slot_id: [text] for slot_id, _, text, _ in slot_specs}
    patient_script["unknown_default"] = list(UNKNOWN_DEFAULT)

    case = {
        "case_id": case_id,
        "dsm_module": dsm_module,
        "label": label,
        "label_subtype": label_subtype,
        "ambiguity": ambiguity,
        "patient_profile": {
            "age_band": age_band,
            "gender": gender,
            "context": context,
        },
        "info_variants": {
            "minimal_cc": minimal_cc,
            "self_report": self_report,
            "chart_full": chart_full,
        },
        "slot_truth": slot_truth,
        "gold_ddx_top5": gold_ddx_top5,
        "risk_flags": risk_flags,
        "required_svcl_domains": required_svcl_domains,
        "patient_script": patient_script,
    }
    rubric = {
        "case_id": case_id,
        "must_ask_slots": must_ask_slots,
        "must_ask_svcl_domains": must_ask_svcl_domains,
        "avoid_harm_rules": list(HARM_RULES),
        "stop_rules": {"max_turns": 15 if ambiguity == "ambiguous" else 12},
    }
    return case, rubric


def _row_from_case(case: dict[str, Any], rubric: dict[str, Any]) -> dict[str, str]:
    profile = case["patient_profile"]
    variants = case["info_variants"]
    return {
        "case_id": case["case_id"],
        "dsm_module": case["dsm_module"],
        "label": case["label"],
        "label_subtype": case["label_subtype"] or "",
        "ambiguity": case["ambiguity"],
        "age_band": profile["age_band"],
        "gender": profile["gender"],
        "context": profile["context"],
        "minimal_cc": variants["minimal_cc"],
        "self_report": variants["self_report"],
        "chart_full": variants["chart_full"],
        "slot_truth_json": json.dumps(case["slot_truth"], ensure_ascii=False),
        "gold_ddx_top5_json": json.dumps(case["gold_ddx_top5"], ensure_ascii=False),
        "risk_flags_json": json.dumps(case["risk_flags"], ensure_ascii=False),
        "required_svcl_domains_json": json.dumps(case["required_svcl_domains"], ensure_ascii=False),
        "patient_script_json": json.dumps(case["patient_script"], ensure_ascii=False),
        "must_ask_slots_json": json.dumps(rubric["must_ask_slots"], ensure_ascii=False),
        "must_ask_svcl_domains_json": json.dumps(rubric["must_ask_svcl_domains"], ensure_ascii=False),
        "avoid_harm_rules_json": json.dumps(rubric["avoid_harm_rules"], ensure_ascii=False),
        "max_turns": str(rubric["stop_rules"]["max_turns"]),
    }


def _write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    rows = list(rows)
    fieldnames = [
        "case_id",
        "dsm_module",
        "label",
        "label_subtype",
        "ambiguity",
        "age_band",
        "gender",
        "context",
        "minimal_cc",
        "self_report",
        "chart_full",
        "slot_truth_json",
        "gold_ddx_top5_json",
        "risk_flags_json",
        "required_svcl_domains_json",
        "patient_script_json",
        "must_ask_slots_json",
        "must_ask_svcl_domains_json",
        "avoid_harm_rules_json",
        "max_turns",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _replace_strings(obj: Any, replacements: dict[str, str]) -> Any:
    if isinstance(obj, str):
        updated = obj
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        return updated
    if isinstance(obj, list):
        return [_replace_strings(item, replacements) for item in obj]
    if isinstance(obj, dict):
        return {key: _replace_strings(value, replacements) for key, value in obj.items()}
    return obj


def _augment_case_pair(
    case: dict[str, Any],
    rubric: dict[str, Any],
    case_id: str,
    variant_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    case_copy = copy.deepcopy(case)
    rubric_copy = copy.deepcopy(rubric)
    case_copy["case_id"] = case_id
    rubric_copy["case_id"] = case_id

    replacements: dict[str, str] = {}
    for slot_payload in case_copy["slot_truth"].values():
        value = slot_payload.get("value")
        if isinstance(value, str) and value in DURATION_SHIFT:
            replacements[value] = DURATION_SHIFT[value]
            slot_payload["value"] = DURATION_SHIFT[value]

    if replacements:
        case_copy["info_variants"] = _replace_strings(case_copy["info_variants"], replacements)
        case_copy["slot_truth"] = _replace_strings(case_copy["slot_truth"], replacements)
        case_copy["patient_script"] = _replace_strings(case_copy["patient_script"], replacements)

    suffix = TEXT_SUFFIXES[variant_index % len(TEXT_SUFFIXES)]
    case_copy["info_variants"]["minimal_cc"] = f"{case_copy['info_variants']['minimal_cc']} {suffix}"
    case_copy["info_variants"]["self_report"] = f"{case_copy['info_variants']['self_report']} {suffix}"
    case_copy["info_variants"]["chart_full"] = f"{case_copy['info_variants']['chart_full']} {suffix}"

    for slot_id, utterances in case_copy["patient_script"].items():
        if slot_id == "unknown_default" or not utterances:
            continue
        case_copy["patient_script"][slot_id] = [f"{utterances[0]} {suffix}"]

    for slot_payload in case_copy["slot_truth"].values():
        evidence = slot_payload.get("evidence", [])
        if evidence:
            slot_payload["evidence"] = [f"{evidence[0]} {suffix}"]

    return case_copy, rubric_copy


def _ocd_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("18-25", "F", "college", "最近总怕手被弄脏。", "最近三个月总反复担心弄脏，反复洗手，学习效率下降。", "污染担忧和洗手仪式明显，伴学习受损。", "3 months", "contamination_fear", True, "我总怕手和桌面特别脏。", "我会一直洗手，不洗就不安心。"),
        ("26-40", "M", "office", "出门前我要反复检查门锁。", "这半年我会反复检查门锁和电源，常常迟到。", "检查强迫和侵入担忧持续半年，工作受损。", "6 months", "checking_behavior", True, "我总担心门没锁好、电没关。", "我会反复检查好多遍。"),
        ("18-25", "F", "college", "脑子里总冒出不该想的念头。", "近四个月反复出现不想要的念头，还要做固定仪式缓解。", "侵入性念头与中和仪式并存。", "4 months", "unwanted_taboo_thoughts", True, "会突然冒出很冒犯的念头，我不想要。", "我得做固定动作才会稍微缓下来。"),
        ("26-40", "M", "office", "东西摆得不对我就坐不住。", "近一年我总因秩序和对称反复整理，耽误工作。", "对称需求和重复整理突出，功能受损。", "1 year", "ordering_symmetry_need", True, "东西不对称我就浑身不舒服。", "我会一遍遍重新摆放。"),
        ("26-40", "F", "community", "洗和查都停不下来。", "最近八个月我总反复洗手、检查包和门，出门非常慢。", "混合污染和检查型强迫表现，社交和外出受损。", "8 months", "checking_behavior", True, "我总怕自己漏掉什么或沾上什么。", "我会洗很久，也会反复确认。"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, duration, extra_slot, extra_value, extra_text, ritual_text) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "moderate", "这已经明显拖慢了我的学习或工作。"
        )
        slots = [
            ("onset_time", duration, f"大概是 {duration} 前开始的。", "high"),
            ("intrusive_thoughts", True, "那些念头会自己冒出来，我不想要。", "high"),
            ("ritual_behavior_present", True, ritual_text, "high"),
            (extra_slot, extra_value, extra_text, "high"),
            ("compulsive_time_consumption", "1_to_3h", "每天差不多会耗掉一到三个小时。", "medium"),
            (impairment_slot, impairment_value, impairment_text, "high"),
        ]
        rows.append(
            _build_case(
                case_id,
                "OCRD",
                "OCD",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["OCD", "OCPD", "BDD", "OS_OCRD", "OTHER"],
                {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                ["symptom_profile", "cog_emotion_process", "course_stability", "functional_impairment"],
                ["onset_time", "intrusive_thoughts", "ritual_behavior_present", impairment_slot],
                ["course_stability", "cog_emotion_process", "symptom_profile", "functional_impairment"],
            )
        )
    return rows


def _bdd_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("18-25", "M", "college", "我总觉得鼻子特别难看。", "近一年我一直觉得鼻子难看，反复照镜子，不敢见人。", "外貌缺陷关注、照镜检查和社交回避明显。", "1 year", "nose", "我总觉得鼻子特别怪。"),
        ("26-40", "F", "office", "皮肤一点点瑕疵都会让我崩掉。", "这半年我总盯着皮肤瑕疵看，还会化妆遮掩到迟到。", "皮肤相关外貌过度担忧，回避与遮掩突出。", "6 months", "skin", "我会盯着脸上的瑕疵看很久。"),
        ("18-25", "F", "college", "我总拿自己和别人脸比较。", "近九个月我总比较脸和发际线，越比较越不敢出门。", "外貌比较、镜检和社交损害明显。", "9 months", "hair", "我老拿自己和别人比，越比越觉得糟。"),
        ("26-40", "M", "community", "我总觉得身材比例很奇怪。", "这一年多我反复看镜子、拍照确认身材，很少社交。", "身体形体相关先占观念显著。", "14 months", "body_shape", "我总觉得身材比例不对。"),
        ("26-40", "F", "office", "脸上小问题会让我一整天都想着。", "近八个月我反复照镜子和遮瑕，工作时也一直想外貌问题。", "外貌关注侵占时间并影响工作。", "8 months", "face", "我上班时也一直想着脸的问题。"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, duration, focus_area, concern_text) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "severe" if context != "office" else "moderate", "这已经明显影响我和别人接触或正常工作。"
        )
        slots = [
            ("onset_time", duration, f"差不多是 {duration} 前开始的。", "high"),
            ("appearance_preoccupation", True, concern_text, "high"),
            ("mirror_checking", True, "我会反复照镜子确认。", "high"),
            ("camouflaging_behavior", True, "我会想办法遮住在意的部位。", "medium"),
            ("perceived_defect_focus_area", focus_area, "主要就集中在那个部位。", "medium"),
            (impairment_slot, impairment_value, impairment_text, "high"),
        ]
        rows.append(
            _build_case(
                case_id,
                "OCRD",
                "BDD",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["BDD", "OCD", "SSD", "OCPD", "OTHER"],
                {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                ["symptom_profile", "course_stability", "functional_impairment"],
                ["onset_time", "appearance_preoccupation", "mirror_checking", impairment_slot],
                ["course_stability", "symptom_profile", "functional_impairment"],
            )
        )
    return rows


def _os_ocrd_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("OS_OCRD_BFRB", "26-40", "F", "office", "我一紧张就会抠皮。", "近两年我一紧张就反复抠皮，停不下来，已经留下痕迹。", "体为中心重复行为以抠皮为主。", "2 years", [("body_focused_repetitive_behavior", True, "我会不自觉地一直抠皮。", "high"), ("skin_picking_behavior", True, "有时会抠到破。", "high"), ("body_focused_trigger_tension", True, "不抠之前会很绷。", "medium")]),
        ("OS_OCRD_BFRB", "18-25", "M", "college", "我会反复拔头发。", "这一年我考试紧张时会反复拔头发，之后又后悔。", "体为中心重复行为以拔毛为主。", "1 year", [("body_focused_repetitive_behavior", True, "我会一直拔头发。", "high"), ("hair_pulling_behavior", True, "经常拔到地上都是。", "high"), ("body_focused_trigger_tension", True, "不拔的时候会很烦躁。", "medium")]),
        ("OS_OCRD_JEAL", "26-40", "F", "community", "我总怀疑伴侣在骗我。", "近九个月我反复怀疑伴侣不忠，会一直查手机和问细节。", "以嫉妒/不忠怀疑为主的重复核查行为。", "9 months", [("jealousy_preoccupation", True, "我脑子里一直在怀疑对方。", "high"), ("partner_checking_behavior", True, "我会反复查手机和定位。", "high"), ("repetitive_confession_seeking", True, "我会一遍遍逼问确认。", "medium")]),
        ("OS_OCRD_JEAL", "26-40", "M", "family", "我总想确认另一半有没有隐瞒。", "近七个月我不停求证、翻聊天记录，关系越来越差。", "反复求证和核查导致关系受损。", "7 months", [("jealousy_preoccupation", True, "我很难停下这种怀疑。", "high"), ("partner_checking_behavior", True, "我会反复找证据。", "high"), ("repetitive_confession_seeking", True, "我会一直追问细节。", "medium")]),
        ("OS_OCRD_OTHER", "41-60", "F", "community", "东西我很难扔掉。", "近三年我越来越难丢东西，家里堆满了，社交也受影响。", "囤积/难以丢弃为主的其他特定 OCRD。", "3 years", [("hoarding_difficulty_discarding", True, "我觉得很多东西都不能扔。", "high"), ("ritual_behavior_present", True, "我会反复整理又舍不得丢。", "medium"), ("reassurance_seeking", True, "我会反复问家人是不是还能留着。", "medium")]),
    ]
    rows = []
    for offset, (subtype, age_band, gender, context, minimal_cc, self_report, chart_full, duration, subtype_slots) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "moderate", "这已经影响到我的关系或正常安排。"
        )
        slots = [
            ("onset_time", duration, f"大概是 {duration} 前开始的。", "high"),
            ("intrusive_thoughts", False, "不是那种突然闯进来的侵入性念头。", "medium"),
            ("ritual_behavior_present", True, "会有一些停不下来的重复行为。", "medium"),
            *subtype_slots,
            (impairment_slot, impairment_value, impairment_text, "high"),
        ]
        rows.append(
            _build_case(
                case_id,
                "OCRD",
                "OS_OCRD",
                subtype,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["OS_OCRD", "OCD", "BDD", "ADJ", "OTHER"],
                {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                ["symptom_profile", "cog_emotion_process", "course_stability", "functional_impairment"],
                ["onset_time", "ritual_behavior_present", subtype_slots[0][0], impairment_slot],
                ["course_stability", "symptom_profile", "cog_emotion_process", "functional_impairment"],
            )
        )
    return rows


def _adj_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("26-40", "M", "office", "换岗后我一直紧绷。", "换岗后一个月我一直觉得压力很大，睡不好，工作受影响。", "压力事件后出现情绪与功能问题。", "1 month", "岗位变化压力很大。"),
        ("18-25", "F", "college", "分手后我状态一直很差。", "分手后近两个月我一直焦虑低落，学习注意力也下降。", "关系应激后出现适应不良。", "2 months", "分手这件事让我一直缓不过来。"),
        ("41-60", "F", "family", "照顾生病家人后我整个人都垮了。", "这三个月我因为照护压力长期焦虑和疲惫，社交也减少。", "家庭照护压力后适应功能下降。", "3 months", "照顾家人这件事压得我喘不过气。"),
        ("26-40", "F", "office", "搬家后我一直适应不好。", "最近两个月因为搬家和通勤变化，我一直很焦虑，工作效率掉很多。", "生活变动后出现持续适应困难。", "2 months", "搬家后各种安排都让我很乱。"),
        ("18-25", "M", "college", "考试失利后我一直提不起劲。", "近一个月因为考试失利和学业压力，我一直情绪差、效率低。", "学业应激后出现明显适应不良。", "1 month", "考试没考好之后我一直很有压力。"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, duration, stressor_text) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "moderate", "这已经影响到我现在的学习、工作或关系。"
        )
        slots = [
            ("onset_time", duration, f"是 {duration} 前开始的。", "high"),
            ("duration", duration, f"大概持续了 {duration}。", "high"),
            ("stressor_present", True, stressor_text, "high"),
            ("adjustment_related_stressor_timing", "clear_link", "就是在那件事之后不久出现的。", "high"),
            ("anxiety_tension", "moderate", "我一直很紧绷。", "medium"),
            (impairment_slot, impairment_value, impairment_text, "high"),
        ]
        risk_flags = {"suicide": False, "violence": False, "psychosis": False, "substance": False}
        must_ask_slots = ["onset_time", "stressor_present", "adjustment_related_stressor_timing", impairment_slot]
        must_ask_svcl_domains = ["environmental_risk", "course_stability", "functional_impairment"]
        required_svcl_domains = ["environmental_risk", "course_stability", "functional_impairment"]
        if offset == 0:
            slots.append(("substance_misuse", True, "那段时间我靠喝酒硬扛，后来有点失控。", "medium"))
            risk_flags["substance"] = True
            must_ask_slots.append("substance_misuse")
            must_ask_svcl_domains.append("comorbidity_pattern")
            required_svcl_domains.append("comorbidity_pattern")
        rows.append(
            _build_case(
                case_id,
                "TSR",
                "ADJ",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["ADJ", "PGD", "PMDD", "SSD", "OTHER"],
                risk_flags,
                required_svcl_domains,
                must_ask_slots,
                must_ask_svcl_domains,
            )
        )
    return rows


def _pgd_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("41-60", "F", "family", "伴侣去世很久了，我还是走不出来。", "伴侣去世十四个月后，我仍每天强烈想念，对社交提不起劲。", "长期持续哀伤与思念突出。", "14 months", "伴侣在一年多前去世了。"),
        ("26-40", "M", "community", "父亲离世后我一直像被卡住。", "父亲去世十三个月后，我还是反复想他，工作也受到影响。", "丧失后持续思念和功能下降。", "13 months", "父亲去世已经超过一年。"),
        ("18-25", "F", "college", "母亲离世后我一直缓不过来。", "母亲去世十六个月后，我仍经常回想和回避相关场合。", "长期丧失反应持续。", "16 months", "母亲离世已经一年多。"),
        ("41-60", "M", "family", "孩子走后我一直觉得生活空掉了。", "孩子去世两年后，我仍觉得身份像被挖空，社交减少。", "持续性思念和身份受损明显。", "24 months", "孩子在两年前去世。"),
        ("26-40", "F", "community", "朋友离世后我一直陷在里面。", "好友去世十五个月后，我还是常常痛苦和回避提醒物。", "延长哀伤表现明显。", "15 months", "好友在一年多前去世。"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, duration, loss_text) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "moderate", "这已经让我的关系和生活明显受影响。"
        )
        slots = [
            ("loss_event_present", True, loss_text, "high"),
            ("duration", duration, f"这种状态持续了 {duration}。", "high"),
            ("grief_yearning", True, "我会一直强烈地想念那个人。", "high"),
            ("grief_emotional_pain", "severe", "想到这件事就会很痛。", "high"),
            ("rumination", True, "我每天都会反复回想。", "medium"),
            (impairment_slot, impairment_value, impairment_text, "high"),
        ]
        rows.append(
            _build_case(
                case_id,
                "TSR",
                "PGD",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["PGD", "ADJ", "BPD", "PMDD", "OTHER"],
                {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                ["environmental_risk", "course_stability", "cog_emotion_process", "functional_impairment"],
                ["loss_event_present", "duration", "grief_yearning", impairment_slot],
                ["environmental_risk", "course_stability", "cog_emotion_process", "functional_impairment"],
            )
        )
    return rows


def _ssd_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("26-40", "F", "office", "我一直担心腹痛是不是大病。", "近八个月我反复腹痛，检查多次没事，但我还是一直担心身体。", "持续身体不适与过度健康担忧。", "8 months", "我总怕这是严重疾病。"),
        ("18-25", "M", "college", "头痛和疲劳让我整天都在想身体。", "近半年我反复头痛和疲劳，检查正常后还是很担心。", "躯体症状困扰与灾难化明显。", "6 months", "我一直担心是不是脑子出问题。"),
        ("41-60", "F", "community", "身体不适一直找不到原因。", "这一年我胸闷、头晕反复出现，几家医院都说没有大问题。", "症状持续且伴过度求证。", "1 year", "我觉得医生可能漏掉了什么。"),
        ("26-40", "M", "office", "疲劳和胃不舒服让我根本停不下担心。", "近九个月我经常因为身体不适请假检查，还是无法放心。", "躯体关注占用大量时间。", "9 months", "我总怕自己身体在恶化。"),
        ("41-60", "F", "family", "我总怕这些不适背后是大问题。", "近十个月我多处身体不适，查不出明显异常，但每天都在想。", "多部位躯体困扰和过度健康焦虑。", "10 months", "我总觉得检查不一定查得出来。"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, duration, health_text) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "moderate", "这些不适和担心已经影响我正常安排。"
        )
        slots = [
            ("duration", duration, f"大概已经持续 {duration}。", "high"),
            ("somatic_symptom_distress", "severe", "身体不舒服这件事让我很痛苦。", "high"),
            ("catastrophizing", True, health_text, "high"),
            ("health_anxiety", True, "我会一直想是不是大病。", "high"),
            ("symptom_persistence_despite_negative_tests", True, "虽然检查说没大问题，但我还是很难放心。", "medium"),
            (impairment_slot, impairment_value, impairment_text, "high"),
        ]
        rows.append(
            _build_case(
                case_id,
                "SSRD",
                "SSD",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["SSD", "ADJ", "OCD", "PMDD", "OTHER"],
                {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                ["symptom_profile", "cog_emotion_process", "course_stability", "functional_impairment"],
                ["duration", "somatic_symptom_distress", "health_anxiety", impairment_slot],
                ["course_stability", "symptom_profile", "cog_emotion_process", "functional_impairment"],
            )
        )
    return rows


def _pmdd_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("18-25", "F", "college", "每次经前我都会特别烦躁。", "近九个月每到经前一周我都会烦躁、发火，月经后缓解。", "症状和月经周期的规律关系明确。", "9 months"),
        ("26-40", "F", "office", "经前情绪会突然很差。", "近一年经前我会明显情绪波动、易怒，来月经后好很多。", "经前加重、经后缓解明显。", "1 year"),
        ("18-25", "F", "college", "周期一到我就很容易崩。", "近十个月我每次经前都很容易哭和发火，还影响上课。", "周期性情绪问题突出。", "10 months"),
        ("26-40", "F", "office", "经前那几天我特别难相处。", "近八个月经前烦躁、腹胀和情绪波动都很明显。", "情绪和躯体经前症状并存。", "8 months"),
        ("26-40", "F", "community", "每个月都有固定几天特别不好受。", "近十一个月我经前明显易怒、波动，月经后又会缓下来。", "周期性模式清楚。", "11 months"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, duration) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "moderate", "那几天我的功能明显会掉下来。"
        )
        slots = [
            ("duration", duration, f"差不多持续了 {duration}。", "high"),
            ("menstrual_cycle_link", "clear_link", "和月经周期关系很明显。", "high"),
            ("luteal_phase_worsening", True, "主要就是月经前那一段会更明显。", "high"),
            ("symptom_relief_post_menses", True, "月经来了之后会轻一些。", "high"),
            ("irritability_premenstrual", True, "经前我特别容易烦躁。", "medium"),
            (impairment_slot, impairment_value, impairment_text, "high"),
        ]
        rows.append(
            _build_case(
                case_id,
                "DEP",
                "PMDD",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["PMDD", "BPD", "ADJ", "IED", "OTHER"],
                {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                ["course_stability", "symptom_profile", "functional_impairment"],
                ["duration", "menstrual_cycle_link", "symptom_relief_post_menses", impairment_slot],
                ["course_stability", "symptom_profile", "functional_impairment"],
            )
        )
    return rows


def _ied_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("18-25", "M", "community", "我会突然暴怒摔东西。", "近半年我经常因小事突然暴怒摔东西，事后很后悔。", "冲动性愤怒爆发和后悔明显。", "6 months"),
        ("26-40", "M", "office", "我一发火就控制不住。", "近八个月我在工作和回家路上都出现过突然发火、砸东西。", "非预谋怒爆发反复出现。", "8 months"),
        ("18-25", "F", "college", "我会突然对朋友大吼。", "近七个月我常因小事大吼或摔物，之后又很自责。", "言语和物品攻击突出。", "7 months"),
        ("26-40", "F", "family", "我生气的时候会完全失控。", "近一年我多次因琐事爆发，反应明显超过事情本身。", "反应不成比例且有损害。", "1 year"),
        ("26-40", "M", "community", "一点点事就会把我点着。", "近九个月我会突然冲动发火，有时还会推搡别人。", "冲动型愤怒发作伴人际受损。", "9 months"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, duration) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "moderate", "这已经影响到我和别人的关系。"
        )
        slots = [
            ("duration", duration, f"差不多持续了 {duration}。", "high"),
            ("anger_outbursts", True, "我会突然爆发，控制不住。", "high"),
            ("outburst_disproportionate", True, "事后看会发现反应太大了。", "high"),
            ("outburst_remorse", True, "发作之后我一般都会后悔。", "medium"),
            ("substance_misuse", False, "不是酒精或药物造成的。", "high"),
            (impairment_slot, impairment_value, impairment_text, "high"),
        ]
        if offset >= 3:
            slots.append(("aggression_property_damage", True, "我会摔东西或者砸东西。", "medium"))
        must_ask_slots = ["duration", "anger_outbursts", "substance_misuse", impairment_slot]
        if offset >= 3:
            must_ask_slots.append("aggression_property_damage")
        rows.append(
            _build_case(
                case_id,
                "DICCD",
                "IED",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["IED", "BPD", "ADJ", "PMDD", "OTHER"],
                {"suicide": False, "violence": True, "psychosis": False, "substance": False},
                ["symptom_profile", "course_stability", "functional_impairment", "comorbidity_pattern"],
                must_ask_slots,
                ["course_stability", "symptom_profile", "comorbidity_pattern", "functional_impairment"],
            )
        )
    return rows


def _bpd_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("18-25", "F", "community", "关系一乱我就会想伤害自己。", "很多年里我关系和情绪都很不稳定，压力大时会有自伤想法。", "长期不稳定人格模式伴自伤风险。"),
        ("18-25", "F", "college", "我特别怕别人不要我。", "从高中后我一直很怕被抛下，关系一紧张就会崩。", "抛弃敏感和关系不稳定明显。"),
        ("26-40", "M", "community", "我常常不知道自己到底是谁。", "这些年我情绪起伏很大，也很难稳定看待自己。", "身份不稳和长期人际问题并存。"),
        ("26-40", "F", "family", "压力大时我会觉得别人都在针对我。", "很多年里我关系不稳、情绪大起大落，压力大时会短暂非常怀疑别人。", "长期人格模式伴应激相关偏执样体验。"),
        ("18-25", "F", "college", "我总觉得心里空得厉害。", "这些年我常感到空虚、关系混乱，有时也会有自伤念头。", "慢性空虚感与关系不稳突出。"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        slots = [
            ("longstanding_pattern", True, "这种状态已经很多年了。", "high"),
            ("relationship_instability", True, "我的关系经常忽好忽坏。", "high"),
            ("abandonment_sensitivity", True, "我特别怕别人不要我。", "medium"),
            ("chronic_emptiness", True, "我会长期觉得心里空空的。", "medium"),
            ("impairment_social", "severe", "这已经严重影响我的关系。", "high"),
        ]
        risk_flags = {"suicide": False, "violence": False, "psychosis": False, "substance": False}
        must_ask_slots = ["longstanding_pattern", "relationship_instability", "abandonment_sensitivity", "impairment_social"]
        if offset in {0, 4}:
            slots.append(("self_harm_ideation", True, "压力大的时候我会有自伤念头。", "high"))
            risk_flags["suicide"] = True
        if offset == 2:
            slots.append(("identity_disturbance", True, "我常常不知道自己到底是谁。", "medium"))
        if offset == 3:
            slots.append(("transient_paranoia_stress_related", True, "压力大时我会突然非常怀疑别人。", "medium"))
            risk_flags["psychosis"] = True
            must_ask_slots.append("transient_paranoia_stress_related")
        if offset in {0, 4}:
            must_ask_slots.append("self_harm_ideation")
        rows.append(
            _build_case(
                case_id,
                "PD",
                "BPD",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["BPD", "IED", "PMDD", "ADJ", "OTHER"],
                risk_flags,
                ["temperament_personality", "functional_impairment", "comorbidity_pattern", "cog_emotion_process"],
                must_ask_slots,
                ["temperament_personality", "functional_impairment", "cog_emotion_process", "comorbidity_pattern"],
            )
        )
    return rows


def _ocpd_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("26-40", "M", "office", "我做事必须完美。", "这些年我做事特别追求完美和秩序，团队配合受影响。", "长期完美主义和控制需求明显。"),
        ("26-40", "F", "office", "事情不按我的标准来我就很难受。", "很多年里我很难把事情交给别人，不按我的方式就焦虑。", "控制和委派困难突出。"),
        ("41-60", "M", "family", "我对规则和做法很难放松。", "这些年我对规则和细节要求很僵硬，经常因此和家人冲突。", "僵硬标准和关系冲突并存。"),
        ("18-25", "F", "college", "我会为了完美把作业拖到很晚。", "上大学后我总因完美主义和秩序要求拖慢任务。", "完美主义影响学业效率。"),
        ("26-40", "M", "office", "我很难接受别人做事和我不一样。", "这些年我坚持自己那一套，导致合作和效率都受影响。", "长期刚性控制模式明显。"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "moderate", "这已经拖慢了我的任务推进或关系。"
        )
        slots = [
            ("longstanding_pattern", True, "很多年都是这样。", "high"),
            ("perfectionism_trait", True, "我很难容忍不完美。", "high"),
            ("rigidity_control_need", True, "我很难接受灵活变化。", "medium"),
            ("intrusive_thoughts", False, "不是那种闯进来的强迫念头。", "medium"),
            (impairment_slot, impairment_value, impairment_text, "high"),
        ]
        if offset in {1, 4}:
            slots.append(("reluctance_delegate", True, "我很难把事情放心交给别人。", "medium"))
        if offset == 2:
            slots.append(("rigidity_morality", True, "我对规则和做法特别僵硬。", "medium"))
        rows.append(
            _build_case(
                case_id,
                "PD",
                "OCPD",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["OCPD", "OCD", "ADJ", "BDD", "OTHER"],
                {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                ["temperament_personality", "functional_impairment", "cog_emotion_process"],
                ["longstanding_pattern", "perfectionism_trait", "intrusive_thoughts", impairment_slot],
                ["temperament_personality", "cog_emotion_process", "functional_impairment"],
            )
        )
    return rows


def _other_cases(start_index: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    specs = [
        ("18-25", "X", "college", "最近状态不太对，但说不清。", "最近注意力差、疲惫和焦虑都有一点，但时间和诱因都不太清楚。", "信息不足，暂不能归入已定义标签。"),
        ("26-40", "F", "community", "最近就是觉得整个人不太对劲。", "近来有些心烦和失眠，但症状模式并不稳定，也说不清从什么时候开始。", "信息不足且症状非特异。"),
        ("41-60", "M", "family", "最近总觉得提不起劲，又说不上来。", "这段时间有些睡不好和疲劳，但没有清楚的线索指向哪一类问题。", "轻度非特异主诉，仍需补充评估。"),
        ("18-25", "F", "college", "我最近就是很乱。", "最近注意力差、情绪也有点波动，但描述很零散。", "现有信息不足以判断。"),
        ("26-40", "M", "office", "我最近状态不好，但没有特别明确的点。", "最近偶尔焦虑、偶尔疲劳，持续时间和触发都不稳定。", "非特异症状，需进一步结构化访谈。"),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        impairment_slot, impairment_value, impairment_text = _impairment_tuple(
            context, "mild", "有一点影响，但我也说不清具体怎么回事。"
        )
        slots = [
            ("onset_time", "unknown", "我记不清具体是什么时候开始。", "low"),
            ("stressor_present", "unknown", "好像没有特别明确的一件事。", "low"),
            ("anxiety_tension", "mild", "有一点心烦和紧张。", "medium"),
            (impairment_slot, impairment_value, impairment_text, "medium"),
        ]
        rows.append(
            _build_case(
                case_id,
                "OTHER",
                "OTHER",
                None,
                ambiguity,
                age_band,
                gender,
                context,
                minimal_cc,
                self_report,
                chart_full,
                slots,
                ["OTHER", "ADJ", "SSD", "PMDD", "OCD"],
                {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                ["course_stability", "environmental_risk", "functional_impairment"],
                ["onset_time", "stressor_present", impairment_slot],
                ["course_stability", "environmental_risk", "functional_impairment"],
            )
        )
    return rows


def generate_casebank() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    generators = [
        _ocd_cases,
        _bdd_cases,
        _os_ocrd_cases,
        _adj_cases,
        _pgd_cases,
        _ssd_cases,
        _pmdd_cases,
        _ied_cases,
        _bpd_cases,
        _ocpd_cases,
        _other_cases,
    ]
    all_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    index = 1
    for generator in generators:
        items = generator(index)
        all_rows.extend(items)
        index += len(items)

    augmented_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    next_index = index
    for variant_index, (case, rubric) in enumerate(all_rows):
        augmented_rows.append(
            _augment_case_pair(
                case,
                rubric,
                case_id=f"PIB_{next_index + variant_index:04d}",
                variant_index=variant_index,
            )
        )

    return all_rows + augmented_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic PIB seed casebank")
    parser.add_argument("--output", type=Path, default=Path("authoring/pilot_casebank_v11.csv"))
    args = parser.parse_args()

    cases_and_rubrics = generate_casebank()
    rows = [_row_from_case(case, rubric) for case, rubric in cases_and_rubrics]
    _write_csv(args.output, rows)
    print(f"Generated {len(rows)} authoring rows at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
