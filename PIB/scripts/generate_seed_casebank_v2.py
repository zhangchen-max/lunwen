from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seed_casebank as G  # reuse _build_case / _impairment_tuple / _row_from_case / _write_csv

UNKNOWN_DEFAULT = ["我不太确定。", "我想不起来具体细节。"]


def _imp4(mode: str, sev: str, text: str) -> tuple[str, Any, str, str]:
    """Wrap _impairment_tuple into the 4-tuple form expected by slot_specs."""
    slot, value, _ = G._impairment_tuple(mode, sev, text)
    return (slot, value, text, "high")


# ---------------------------------------------------------------------------
# NEW seeds: 5 distinct scenarios per label (ids 0056..0110, same label order
# as the original 55 so case_id continuity is preserved).
# ---------------------------------------------------------------------------

def _ocd_cases_new(start_index: int):
    specs = [
        ("26-40", "F", "office", "办公室里我总觉得哪儿都脏。", "近九个月我反复担心污染，反复洗手，工作效率下降。", "污染担忧突出，伴工作受损。",
         [("onset_time", "9 months", "大概是 9 months 前开始的。", "high"),
          ("intrusive_thoughts", True, "那些念头会自己冒出来，我不想要。", "high"),
          ("ritual_behavior_present", True, "我会一直洗手，不洗就不安心。", "high"),
          ("contamination_fear", True, "我总觉得哪儿都脏。", "high"),
          ("compulsive_time_consumption", "over_3h", "每天差不多要花三个多小时。", "medium"),
          ("symptom_frequency", "daily", "几乎每天都停不下来。", "medium"),
          ("family_history_ocrd", True, "我妈也有点类似的较真习惯。", "medium"),
          _imp4("office", "moderate", "这已经明显拖慢了我的工作。")]),
        ("18-25", "M", "college", "出门前我总怕没锁好门。", "近两个月我反复检查门锁和电源，常常迟到。", "检查强迫持续两个月，学习受损。",
         [("onset_time", "2 months", "是 2 months 前开始的。", "high"),
          ("intrusive_thoughts", True, "会有不想要的念头冒出来。", "high"),
          ("ritual_behavior_present", True, "我会反复确认门锁。", "high"),
          ("checking_behavior", True, "我总担心门没锁好、电没关。", "high"),
          ("compulsive_time_consumption", "1_to_3h", "每天会耗掉一到三个小时。", "medium"),
          ("recent_exacerbation", True, "最近明显更频繁了。", "medium"),
          ("symptom_progression", "worsening", "感觉越来越重。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
        ("26-40", "M", "office", "脑子里会冒出很冒犯的念头。", "近一年我反复出现不想要的冒犯念头，还要做固定仪式缓解。", "侵入性念头与中和仪式并存，工作受损。",
         [("onset_time", "1 year", "差不多 1 year 前开始的。", "high"),
          ("intrusive_thoughts", True, "会突然冒出很冒犯的念头，我不想要。", "high"),
          ("ritual_behavior_present", True, "我得做固定动作才会稍微缓下来。", "high"),
          ("unwanted_taboo_thoughts", True, "那些念头让我很羞耻。", "high"),
          ("compulsive_time_consumption", "1_to_3h", "每天会耗掉一到三个小时。", "medium"),
          ("avoidance_behavior", True, "我会回避可能触发的人。", "medium"),
          ("family_history_ocrd", True, "家里人也有点较真。", "medium"),
          _imp4("office", "severe", "已经严重影响我的职责。")]),
        ("18-25", "F", "college", "东西摆得不对我就坐不住。", "近半年我总因秩序和对称反复整理，耽误学习。", "对称需求和重复整理突出，学习受损。",
         [("onset_time", "6 months", "是 6 months 前开始的。", "high"),
          ("intrusive_thoughts", True, "会有念头冒出来。", "high"),
          ("ritual_behavior_present", True, "我会一遍遍重新摆放。", "high"),
          ("ordering_symmetry_need", True, "东西不对称我就浑身不舒服。", "high"),
          ("compulsive_time_consumption", "1_to_3h", "每天会耗掉一到三个小时。", "medium"),
          ("symptom_frequency", "weekly", "一周总有好几次。", "medium"),
          ("emotion_regulation_difficulty", "moderate", "不顺心就很烦躁。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
        ("41-60", "F", "community", "我又怕脏又总怕没关好。", "近三年我反复洗手又反复检查，社交越来越少。", "混合污染与检查型强迫，社交受损。",
         [("onset_time", "3 years", "是 3 years 前开始的。", "high"),
          ("intrusive_thoughts", True, "念头会自己冒出来。", "high"),
          ("ritual_behavior_present", True, "我会又洗又查。", "high"),
          ("contamination_fear", True, "我总怕手和桌面特别脏。", "high"),
          ("checking_behavior", True, "我总担心门没锁好。", "high"),
          ("compulsive_time_consumption", "over_3h", "每天要花三个多小时。", "medium"),
          ("treatment_history", "psychotherapy", "我做过一段时间咨询。", "medium"),
          ("comorbid_anxiety_history", True, "我长期容易紧张。", "medium"),
          _imp4("community", "severe", "已经严重影响我的社交。")]),
    ]
    return _emit(start_index, "OCRD", "OCD", None, specs,
                 ["OCD", "OCPD", "BDD", "OS_OCRD", "OTHER"],
                 {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                 ["symptom_profile", "cog_emotion_process", "course_stability", "functional_impairment"],
                 ["onset_time", "intrusive_thoughts", "ritual_behavior_present"])


def _bdd_cases_new(start_index: int):
    specs = [
        ("26-40", "M", "office", "我好几处地方都看着不顺眼。", "近两年我总盯着好几处外貌不满意的地方，回避出门。", "多部位外貌先占观念突出。",
         [("onset_time", "2 years", "差不多 2 years 前开始的。", "high"),
          ("appearance_preoccupation", True, "我总盯着好几处不满意的地方。", "high"),
          ("mirror_checking", True, "我会反复照镜子确认。", "high"),
          ("camouflaging_behavior", True, "我会想办法遮住。", "medium"),
          ("perceived_defect_focus_area", "multiple", "好几处都让我难受。", "medium"),
          ("symptom_frequency", "daily", "几乎每天都会想。", "medium"),
          ("avoidance_behavior", True, "我尽量少出门见人。", "medium"),
          _imp4("office", "severe", "已经严重影响我的工作。")]),
        ("18-25", "F", "college", "我老看脸上的瑕疵。", "近四个月我总盯着脸上瑕疵，越看越闷，学习下降。", "外貌关注伴情绪低下。",
         [("onset_time", "4 months", "是 4 months 前开始的。", "high"),
          ("appearance_preoccupation", True, "我老看脸上的瑕疵。", "high"),
          ("mirror_checking", True, "我会反复照镜子。", "high"),
          ("camouflaging_behavior", True, "我会化妆遮掩。", "medium"),
          ("perceived_defect_focus_area", "skin", "主要就在皮肤上。", "medium"),
          ("depressed_mood", "moderate", "最近也总是闷闷的。", "medium"),
          ("anhedonia", "mild", "对事情提不起劲。", "medium"),
          ("recent_exacerbation", True, "最近更明显了。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
        ("41-60", "F", "family", "我总觉得身材比例不对。", "近五年我反复看镜子、拍照确认身材，很少社交。", "身体形体相关先占观念显著。",
         [("onset_time", "5 years", "是 5 years 前开始的。", "high"),
          ("appearance_preoccupation", True, "我总觉得身材比例不对。", "high"),
          ("mirror_checking", True, "我会反复照镜子。", "high"),
          ("camouflaging_behavior", True, "我会穿宽松衣服遮。", "medium"),
          ("perceived_defect_focus_area", "body_shape", "主要就在身材上。", "medium"),
          ("family_history_ocrd", True, "家里人也有点外貌焦虑。", "medium"),
          ("treatment_history", "medication", "我吃过一阵药。", "medium"),
          _imp4("family", "severe", "已经严重影响我的关系。")]),
        ("26-40", "F", "office", "脸上一小点我就崩掉。", "近七个月我总盯着脸，工作时也一直想外貌问题。", "外貌关注侵占时间并影响工作。",
         [("onset_time", "7 months", "是 7 months 前开始的。", "high"),
          ("appearance_preoccupation", True, "我上班时也一直想着脸。", "high"),
          ("mirror_checking", True, "我会反复照镜子。", "high"),
          ("camouflaging_behavior", True, "我会用遮瑕盖住。", "medium"),
          ("perceived_defect_focus_area", "face", "主要就在脸上。", "medium"),
          ("anxiety_tension", "moderate", "一想到就紧张。", "medium"),
          ("sleep_insomnia", "mild", "晚上总想着，睡不好。", "medium"),
          _imp4("office", "moderate", "这已经影响我的工作。")]),
        ("18-25", "M", "college", "我总拿头发和别人比。", "近十个月我总比较头发，越比较越不敢出门。", "外貌比较、镜检和社交损害明显。",
         [("onset_time", "10 months", "是 10 months 前开始的。", "high"),
          ("appearance_preoccupation", True, "我老拿自己和别人比头发。", "high"),
          ("mirror_checking", True, "我会反复照镜子看头发。", "high"),
          ("camouflaging_behavior", True, "我会戴帽子遮。", "medium"),
          ("perceived_defect_focus_area", "hair", "主要就在头发上。", "medium"),
          ("symptom_frequency", "weekly", "一周总会想好几次。", "medium"),
          ("emotion_regulation_difficulty", "moderate", "越想越烦躁。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
    ]
    return _emit(start_index, "OCRD", "BDD", None, specs,
                 ["BDD", "OCD", "SSD", "OCPD", "OTHER"],
                 {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                 ["symptom_profile", "course_stability", "functional_impairment"],
                 ["onset_time", "appearance_preoccupation", "mirror_checking"])


def _os_ocrd_cases_new(start_index: int):
    specs = [
        ("OS_OCRD_BFRB", "18-25", "F", "college", "我会不自觉抠皮又拔头发。", "近一年我紧张时就又抠又拔，之后又后悔。", "体为中心重复行为以抠皮与拔毛为主。",
         [("onset_time", "1 year", "大概是 1 year 前开始的。", "high"),
          ("intrusive_thoughts", False, "不是那种突然闯进来的侵入性念头。", "medium"),
          ("ritual_behavior_present", True, "会有一些停不下来的重复行为。", "medium"),
          ("body_focused_repetitive_behavior", True, "我会不自觉地一直抠和拔。", "high"),
          ("skin_picking_behavior", True, "脸和手都会抠。", "high"),
          ("hair_pulling_behavior", True, "也会拔头发。", "high"),
          ("body_focused_trigger_tension", True, "不抠之前会很绷。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
        ("OS_OCRD_JEAL", "26-40", "F", "family", "我总怀疑伴侣在骗我。", "近一年我反复怀疑伴侣不忠，会一直查手机，常吵架。", "以嫉妒/不忠怀疑为主的重复核查行为。",
         [("onset_time", "1 year", "大概是 1 year 前开始的。", "high"),
          ("intrusive_thoughts", False, "不是那种侵入性念头。", "medium"),
          ("ritual_behavior_present", True, "会反复确认。", "medium"),
          ("jealousy_preoccupation", True, "我总怀疑对方不忠。", "high"),
          ("partner_checking_behavior", True, "我会反复查手机。", "high"),
          ("repetitive_confession_seeking", True, "我会一遍遍逼问确认。", "medium"),
          ("family_conflict", True, "常为此吵架。", "medium"),
          _imp4("family", "severe", "已经严重影响我的关系。")]),
        ("OS_OCRD_OTHER", "41-60", "M", "community", "东西我很难扔掉。", "近四年我越来越难丢东西，家里堆满，社交也受影响。", "囤积/难以丢弃为主的其他特定 OCRD。",
         [("onset_time", "4 years", "是 4 years 前开始的。", "high"),
          ("intrusive_thoughts", False, "不是那种侵入性念头。", "medium"),
          ("ritual_behavior_present", True, "我会反复整理又舍不得丢。", "medium"),
          ("hoarding_difficulty_discarding", True, "我觉得很多东西都不能扔。", "high"),
          ("reassurance_seeking", True, "我会反复问家人是不是还能留着。", "medium"),
          _imp4("community", "moderate", "这已经影响到我的生活。")]),
        ("OS_OCRD_BFRB", "18-25", "M", "college", "考试紧张我就拔头发。", "近八个月我考试紧张时会反复拔头发，之后又后悔。", "体为中心重复行为以拔毛为主。",
         [("onset_time", "8 months", "是 8 months 前开始的。", "high"),
          ("intrusive_thoughts", False, "不是那种侵入性念头。", "medium"),
          ("ritual_behavior_present", True, "会有一些停不下来的重复行为。", "medium"),
          ("body_focused_repetitive_behavior", True, "我会一直拔头发。", "high"),
          ("hair_pulling_behavior", True, "经常拔到地上都是。", "high"),
          ("body_focused_trigger_tension", True, "不拔的时候会很烦躁。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
        ("OS_OCRD_JEAL", "26-40", "M", "community", "我总想确认另一半没隐瞒。", "近六个月我不停求证、翻记录，关系越来越差。", "反复求证和核查导致关系受损。",
         [("onset_time", "6 months", "是 6 months 前开始的。", "high"),
          ("intrusive_thoughts", False, "不是那种侵入性念头。", "medium"),
          ("ritual_behavior_present", True, "会反复确认。", "medium"),
          ("jealousy_preoccupation", True, "我很难停下这种怀疑。", "high"),
          ("partner_checking_behavior", True, "我会反复找证据。", "high"),
          ("repetitive_confession_seeking", False, "我不太逼问，但会查。", "medium"),
          ("recent_exacerbation", True, "最近更频繁了。", "medium"),
          _imp4("community", "moderate", "这已经影响到我的关系。")]),
    ]
    rows = []
    for offset, (subtype, age_band, gender, context, minimal_cc, self_report, chart_full, slot_specs) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        imp_slot = slot_specs[-1][0]
        rows.append(G._build_case(
            case_id, "OCRD", "OS_OCRD", subtype, ambiguity, age_band, gender, context,
            minimal_cc, self_report, chart_full, slot_specs,
            ["OS_OCRD", "OCD", "BDD", "ADJ", "OTHER"],
            {"suicide": False, "violence": False, "psychosis": False, "substance": False},
            ["symptom_profile", "cog_emotion_process", "course_stability", "functional_impairment"],
            ["onset_time", "ritual_behavior_present", imp_slot],
            ["course_stability", "symptom_profile", "cog_emotion_process", "functional_impairment"],
        ))
    return rows


def _adj_cases_new(start_index: int):
    specs = [
        ("26-40", "M", "office", "换工作后我一直紧绷。", "换工作后三个月我一直压力大、睡不好，工作受影响。", "工作变动后出现适应不良。",
         [("onset_time", "3 months", "是 3 months 前开始的。", "high"),
          ("duration", "3 months", "大概持续了 3 months。", "high"),
          ("stressor_present", True, "换工作后压力很大。", "high"),
          ("adjustment_related_stressor_timing", "clear_link", "就是在换工作之后出现的。", "high"),
          ("anxiety_tension", "moderate", "我一直很紧绷。", "medium"),
          ("financial_stress", True, "开销一下子变大了。", "medium"),
          ("depressed_mood", "moderate", "情绪也一直低落。", "medium"),
          ("sleep_insomnia", "mild", "晚上睡不太着。", "medium"),
          _imp4("office", "moderate", "这已经影响我的工作。")]),
        ("41-60", "F", "family", "照顾家人后我整个人都垮了。", "近五个月我因照护压力长期焦虑疲惫，社交减少。", "家庭照护压力后适应功能下降。",
         [("onset_time", "5 months", "是 5 months 前开始的。", "high"),
          ("duration", "5 months", "大概持续了 5 months。", "high"),
          ("stressor_present", True, "照顾家人这件事压得我喘不过气。", "high"),
          ("adjustment_related_stressor_timing", "clear_link", "就是照护之后出现的。", "high"),
          ("anxiety_tension", "moderate", "我一直很焦虑。", "medium"),
          ("family_conflict", True, "家里也常因为照护闹矛盾。", "medium"),
          ("anhedonia", "mild", "对事情有点提不起劲。", "medium"),
          _imp4("family", "moderate", "这已经影响我的关系。")]),
        ("18-25", "M", "college", "和同学闹翻后我一直缓不过来。", "近一个月我和同学闹翻，一直焦虑低落，学习效率下降。", "人际应激后出现适应不良。",
         [("onset_time", "1 month", "是 1 month 前开始的。", "high"),
          ("duration", "1 month", "大概持续了 1 month。", "high"),
          ("stressor_present", True, "和同学闹翻让我一直缓不过来。", "high"),
          ("adjustment_related_stressor_timing", "clear_link", "就在闹翻之后出现的。", "high"),
          ("anxiety_tension", "moderate", "我一直很紧绷。", "medium"),
          ("substance_misuse", True, "最近会喝点酒缓压。", "medium"),
          ("stressor_type", "interpersonal", "主要是人际冲突。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
        ("26-40", "F", "office", "体检出问题后我一直担心。", "近两个月体检异常后我一直焦虑，反复查资料，工作分心。", "健康应激后出现适应困难。",
         [("onset_time", "2 months", "是 2 months 前开始的。", "high"),
          ("duration", "2 months", "大概持续了 2 months。", "high"),
          ("stressor_present", True, "体检出了点问题让我很担心。", "high"),
          ("adjustment_related_stressor_timing", "clear_link", "就是体检之后出现的。", "high"),
          ("anxiety_tension", "moderate", "我一直很紧张。", "medium"),
          ("somatic_symptom_distress", "mild", "身体也总觉得不舒服。", "medium"),
          ("sleep_insomnia", "mild", "晚上睡不好。", "medium"),
          _imp4("office", "moderate", "这已经影响我的工作。")]),
        ("41-60", "M", "family", "家里宠物走了我一直缓不过来。", "近四个月宠物去世后我一直低落、回避相关东西，社交减少。", "丧失后亚阈值的持续低落反应。",
         [("onset_time", "4 months", "是 4 months 前开始的。", "high"),
          ("duration", "4 months", "大概持续了 4 months。", "high"),
          ("stressor_present", True, "家里宠物走了让我很难受。", "high"),
          ("adjustment_related_stressor_timing", "clear_link", "就是它走后出现的。", "high"),
          ("anxiety_tension", "moderate", "我一直有点不安。", "medium"),
          ("loss_event_present", True, "宠物去世了。", "high"),
          ("grief_yearning", "mild", "挺想它的。", "medium"),
          _imp4("family", "moderate", "这已经影响我的关系。")]),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, slot_specs) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        imp_slot = slot_specs[-1][0]
        risk = {"suicide": False, "violence": False, "psychosis": False, "substance": False}
        must_ask = ["onset_time", "stressor_present", "adjustment_related_stressor_timing", imp_slot]
        req_dom = ["environmental_risk", "course_stability", "functional_impairment"]
        has_substance = any(s[0] == "substance_misuse" and s[1] is True for s in slot_specs)
        if has_substance:
            risk["substance"] = True
            must_ask.append("substance_misuse")
            req_dom.append("comorbidity_pattern")
        rows.append(G._build_case(
            case_id, "TSR", "ADJ", None, ambiguity, age_band, gender, context,
            minimal_cc, self_report, chart_full, slot_specs,
            ["ADJ", "PGD", "PMDD", "SSD", "OTHER"], risk, req_dom, must_ask,
            ["environmental_risk", "course_stability", "functional_impairment"],
        ))
    return rows


def _pgd_cases_new(start_index: int):
    specs = [
        ("18-25", "M", "college", "好友走了一年多我还是走不出来。", "好友去世十七个月后，我仍每天强烈想念，对社交提不起劲。", "长期持续哀伤与思念突出。",
         [("loss_event_present", True, "好友在一年多前走了。", "high"),
          ("duration", "17 months", "这种状态持续了 17 months。", "high"),
          ("grief_yearning", True, "我会一直强烈地想念他。", "high"),
          ("grief_emotional_pain", "severe", "想到就会很痛。", "high"),
          ("rumination", True, "我每天都会反复回想。", "medium"),
          ("grief_avoidance_reminders", True, "我会避开提到他的东西。", "medium"),
          ("social_support_low", True, "身边没人能聊这些。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
        ("41-60", "F", "family", "老伴走后我觉得一半的自己也没了。", "老伴去世二十个月后，我仍强烈思念，身份感被挖空。", "丧失后持续思念和身份受损明显。",
         [("loss_event_present", True, "老伴两年前走了。", "high"),
          ("duration", "20 months", "这种状态持续了 20 months。", "high"),
          ("grief_yearning", True, "我会一直想念他。", "high"),
          ("grief_emotional_pain", "moderate", "想到还是会难过。", "high"),
          ("rumination", True, "我常反复回想过去。", "medium"),
          ("grief_identity_disruption", True, "我觉得一半的自己也没了。", "medium"),
          ("protective_supports", "limited", "身边支持很有限。", "medium"),
          _imp4("family", "severe", "这已经严重影响我的生活。")]),
        ("26-40", "F", "community", "哥哥走后我特别孤单。", "哥哥去世十九个月后，我仍痛苦、回避提醒物，家人关系也紧张。", "延长哀伤表现伴家庭冲突。",
         [("loss_event_present", True, "哥哥 19 months 前去世。", "high"),
          ("duration", "19 months", "这种状态持续了 19 months。", "high"),
          ("grief_yearning", True, "我会一直想念他。", "high"),
          ("grief_emotional_pain", "severe", "想到就很痛。", "high"),
          ("rumination", True, "我每天都会回想。", "medium"),
          ("grief_loneliness", True, "我特别孤单。", "medium"),
          ("family_conflict", True, "家里常因为这件事吵架。", "medium"),
          _imp4("community", "moderate", "这已经影响我的生活。")]),
        ("41-60", "M", "family", "母亲走后我一直没缓过来。", "母亲去世二十二个月后，我仍思念、回避相关场合，做过咨询。", "长期丧失反应持续。",
         [("loss_event_present", True, "母亲快两年前走的。", "high"),
          ("duration", "22 months", "这种状态持续了 22 months。", "high"),
          ("grief_yearning", True, "我会一直想念她。", "high"),
          ("grief_emotional_pain", "moderate", "想到还是会难过。", "high"),
          ("rumination", True, "我常反复回想。", "medium"),
          ("treatment_history", "psychotherapy", "我做过一段时间咨询。", "medium"),
          ("grief_avoidance_reminders", True, "我会避开提到她的东西。", "medium"),
          _imp4("family", "moderate", "这已经影响我的生活。")]),
        ("26-40", "M", "community", "带我的前辈走后我一直在恍惚。", "前辈去世二十八个月后，我仍强烈思念，身份感被撼动，少有支持。", "长期丧失反应持续。",
         [("loss_event_present", True, "带我的前辈两年多前走了。", "high"),
          ("duration", "28 months", "这种状态持续了 28 months。", "high"),
          ("grief_yearning", True, "我会一直想念他。", "high"),
          ("grief_emotional_pain", "severe", "想到就很痛。", "high"),
          ("rumination", True, "我每天都会回想。", "medium"),
          ("grief_identity_disruption", True, "我常怀疑自己还能不能做好。", "medium"),
          ("social_support_low", True, "身边没人能聊这些。", "medium"),
          _imp4("community", "moderate", "这已经影响我的生活。")]),
    ]
    return _emit(start_index, "TSR", "PGD", None, specs,
                 ["PGD", "ADJ", "BPD", "PMDD", "OTHER"],
                 {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                 ["environmental_risk", "course_stability", "cog_emotion_process", "functional_impairment"],
                 ["loss_event_present", "duration", "grief_yearning"])


def _ssd_cases_new(start_index: int):
    specs = [
        ("26-40", "F", "office", "我哪都不舒服，怕是绝症。", "近十四个月我多处不适，反复检查没事，但我还是非常担心。", "多部位躯体症状与过度健康担忧。",
         [("duration", "14 months", "大概已经持续 14 months。", "high"),
          ("somatic_symptom_distress", "severe", "身体不舒服这件事让我很痛苦。", "high"),
          ("catastrophizing", True, "我怕自己得的是绝症。", "high"),
          ("health_anxiety", True, "我会一直想是不是大病。", "high"),
          ("symptom_persistence_despite_negative_tests", True, "检查说没大问题，但我还是很难放心。", "medium"),
          ("multiple_somatic_sites", True, "头、胸、肚子都难受。", "high"),
          ("symptom_monitoring", True, "我天天量身体、记症状。", "medium"),
          _imp4("office", "moderate", "这已经影响我的工作。")]),
        ("18-25", "M", "college", "头痛让我整天都在想脑子出问题。", "近七个月我反复头痛，换了几家医院都没事，还是很担心。", "躯体症状困扰与灾难化明显。",
         [("duration", "7 months", "大概已经持续 7 months。", "high"),
          ("somatic_symptom_distress", "moderate", "头痛让我很困扰。", "high"),
          ("catastrophizing", True, "我总怕是脑子出问题。", "high"),
          ("health_anxiety", True, "我会一直想是不是大病。", "high"),
          ("symptom_persistence_despite_negative_tests", True, "检查正常后还是很担心。", "medium"),
          ("doctor_shopping", True, "我换了好几家医院。", "medium"),
          ("family_history_psy", True, "家里有人长期焦虑。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
        ("41-60", "F", "community", "胸闷气短让我做了很多检查。", "近两年我胸闷气短反复出现，几家医院都说没大事，但我还是不放心。", "症状持续且伴过度求证。",
         [("duration", "2 years", "大概已经持续 2 years。", "high"),
          ("somatic_symptom_distress", "severe", "胸闷让我很痛苦。", "high"),
          ("catastrophizing", True, "我怕是心脏出了大问题。", "high"),
          ("health_anxiety", True, "我会一直想是不是大病。", "high"),
          ("symptom_persistence_despite_negative_tests", True, "检查说没大问题，但我很难放心。", "medium"),
          ("disproportionate_health_behaviors", True, "我做了很多不必要的检查。", "medium"),
          ("treatment_history", "medication", "我吃过一阵药。", "medium"),
          _imp4("community", "moderate", "这已经影响我的生活。")]),
        ("26-40", "M", "office", " fatigue 和胃不舒服让我很焦虑。", "近九个月我经常疲劳、胃部不适，检查正常后依然担心。", "躯体关注占用大量时间。",
         [("duration", "9 months", "大概已经持续 9 months。", "high"),
          ("somatic_symptom_distress", "moderate", "不舒服让我挺困扰。", "high"),
          ("catastrophizing", True, "我总怕身体在恶化。", "high"),
          ("health_anxiety", True, "我会一直想是不是大病。", "high"),
          ("symptom_persistence_despite_negative_tests", True, "检查没事但我还是不放心。", "medium"),
          ("sleep_insomnia", "mild", "晚上总睡不好。", "medium"),
          ("anxiety_tension", "moderate", "我一直很紧张。", "medium"),
          _imp4("office", "moderate", "这已经影响我的工作。")]),
        ("41-60", "F", "family", "我全身都不对劲，查不出原因。", "近三十个月我多处不适，查不出异常，但每天都想。", "多部位躯体困扰和过度健康焦虑。",
         [("duration", "30 months", "大概已经持续 30 months。", "high"),
          ("somatic_symptom_distress", "severe", "身体不舒服让我很痛苦。", "high"),
          ("catastrophizing", True, "我总觉得检查不一定查得出来。", "high"),
          ("health_anxiety", True, "我会一直想是不是大病。", "high"),
          ("symptom_persistence_despite_negative_tests", True, "虽然查不出，但我还是很难放心。", "medium"),
          ("multiple_somatic_sites", True, "好几个地方都不舒服。", "high"),
          ("recent_exacerbation", True, "最近更频繁了。", "medium"),
          _imp4("family", "severe", "这已经严重影响我的生活。")]),
    ]
    return _emit(start_index, "SSRD", "SSD", None, specs,
                 ["SSD", "ADJ", "OCD", "PMDD", "OTHER"],
                 {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                 ["symptom_profile", "cog_emotion_process", "course_stability", "functional_impairment"],
                 ["duration", "somatic_symptom_distress", "health_anxiety"])


def _pmdd_cases_new(start_index: int):
    specs = [
        ("18-25", "F", "college", "每次经前我都特别低落。", "近九个月每到经前一周我都会低落、提不起劲，月经后缓解。", "症状和月经周期规律相关。",
         [("duration", "9 months", "差不多持续了 9 months。", "high"),
          ("menstrual_cycle_link", "clear_link", "和月经周期关系很明显。", "high"),
          ("luteal_phase_worsening", True, "主要就是月经前那一段更明显。", "high"),
          ("symptom_relief_post_menses", True, "月经来了之后会轻一些。", "high"),
          ("irritability_premenstrual", True, "经前我特别容易烦躁。", "medium"),
          ("depressed_mood", "moderate", "经前特别低落。", "medium"),
          ("anhedonia", "mild", "对什么都提不起劲。", "medium"),
          _imp4("college", "moderate", "那几天我的功能明显会掉下来。")]),
        ("26-40", "F", "office", "经前一点小事就让我炸。", "近一年经前我会明显情绪波动、易怒，来月经后好很多。", "经前加重、经后缓解明显。",
         [("duration", "1 year", "差不多持续了 1 year。", "high"),
          ("menstrual_cycle_link", "clear_link", "和月经周期关系很明显。", "high"),
          ("luteal_phase_worsening", True, "主要就是月经前那一段更明显。", "high"),
          ("symptom_relief_post_menses", True, "月经来了之后会轻一些。", "high"),
          ("irritability_premenstrual", True, "经前我特别容易烦躁。", "medium"),
          ("anger_trigger_triviality", True, "一点小事就让我炸。", "medium"),
          ("emotion_regulation_difficulty", "moderate", "那几天特别难控制情绪。", "medium"),
          _imp4("office", "moderate", "那几天我的工作会受影响。")]),
        ("18-25", "F", "college", "周期一到我就想吃又想睡。", "近十个月我每次经前都易饿、嗜睡、胸胀，还影响上课。", "周期性躯体与情绪问题突出。",
         [("duration", "10 months", "差不多持续了 10 months。", "high"),
          ("menstrual_cycle_link", "clear_link", "和月经周期关系很明显。", "high"),
          ("luteal_phase_worsening", True, "主要就是月经前那一段更明显。", "high"),
          ("symptom_relief_post_menses", True, "月经来了之后会轻一些。", "high"),
          ("irritability_premenstrual", True, "经前我特别容易烦躁。", "medium"),
          ("appetite_change", "increased", "经前总想吃东西。", "medium"),
          ("sleep_hypersomnia", "mild", "经前老想睡。", "medium"),
          ("breast_tenderness_premenstrual", True, "经前胸胀。", "medium"),
          _imp4("college", "moderate", "那几天我的学习会受影响。")]),
        ("26-40", "F", "community", "每个月都有固定几天特别不好受。", "近十一个月我经前明显易怒、腹胀，月经后又会缓下来。", "周期性模式清楚。",
         [("duration", "11 months", "差不多持续了 11 months。", "high"),
          ("menstrual_cycle_link", "clear_link", "和月经周期关系很明显。", "high"),
          ("luteal_phase_worsening", True, "主要就是月经前那一段更明显。", "high"),
          ("symptom_relief_post_menses", True, "月经来了之后会轻一些。", "high"),
          ("irritability_premenstrual", True, "经前我特别容易烦躁。", "medium"),
          ("physical_bloating_premenstrual", True, "经前肚子胀。", "medium"),
          ("depressed_mood", "moderate", "经前特别闷。", "medium"),
          ("treatment_history", "psychotherapy", "我做过一段时间咨询。", "medium"),
          _imp4("community", "moderate", "那几天我的生活会受影响。")]),
        ("41-60", "F", "family", "每到那几天我就没精神又紧张。", "近十三个月我经前明显焦虑、乏力，月经后缓解。", "周期性模式清楚。",
         [("duration", "13 months", "差不多持续了 13 months。", "high"),
          ("menstrual_cycle_link", "clear_link", "和月经周期关系很明显。", "high"),
          ("luteal_phase_worsening", True, "主要就是月经前那一段更明显。", "high"),
          ("symptom_relief_post_menses", True, "月经来了之后会轻一些。", "high"),
          ("irritability_premenstrual", True, "经前我特别容易烦躁。", "medium"),
          ("anxiety_tension", "moderate", "经前特别紧张。", "medium"),
          ("energy_low", "mild", "经前特别没精神。", "medium"),
          _imp4("family", "moderate", "那几天我的生活会受影响。")]),
    ]
    return _emit(start_index, "DEP", "PMDD", None, specs,
                 ["PMDD", "BPD", "ADJ", "IED", "OTHER"],
                 {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                 ["course_stability", "symptom_profile", "functional_impairment"],
                 ["duration", "menstrual_cycle_link", "symptom_relief_post_menses"])


def _ied_cases_new(start_index: int):
    specs = [
        ("18-25", "M", "community", "我会突然吼人、事后后悔。", "近半年我常因小事突然大吼，之后又自责。", "言语攻击突出。",
         [("duration", "6 months", "差不多持续了 6 months。", "high"),
          ("anger_outbursts", True, "我会突然爆发，控制不住。", "high"),
          ("outburst_disproportionate", True, "事后看会发现反应太大了。", "high"),
          ("outburst_remorse", True, "发作之后我一般都会后悔。", "medium"),
          ("substance_misuse", False, "不是酒精或药物造成的。", "high"),
          ("symptom_frequency", "weekly", "一周总有好几次。", "medium"),
          ("aggression_verbal", True, "我会大声吼人。", "medium"),
          ("impulsivity_non_substance", True, "我常冲动做事。", "medium"),
          _imp4("community", "moderate", "这已经影响到我和别人的关系。")]),
        ("26-40", "M", "office", "我一发火就摔东西。", "近八个月我在工作和回家路上都出现过突然发火、砸东西。", "非预谋怒爆发反复出现。",
         [("duration", "8 months", "差不多持续了 8 months。", "high"),
          ("anger_outbursts", True, "我会突然爆发，控制不住。", "high"),
          ("outburst_disproportionate", True, "事后看会发现反应太大了。", "high"),
          ("outburst_remorse", True, "发作之后我一般都会后悔。", "medium"),
          ("substance_misuse", False, "不是酒精或药物造成的。", "high"),
          ("symptom_frequency", "daily", "几乎每天都会有点。", "medium"),
          ("aggression_property_damage", True, "我会摔东西或者砸东西。", "medium"),
          _imp4("office", "moderate", "这已经影响我的工作。")]),
        ("18-25", "F", "college", "我会突然推人、不是预谋的。", "近七个月我常因小事大吼或推搡，之后又很自责。", "言语和肢体攻击突出。",
         [("duration", "7 months", "差不多持续了 7 months。", "high"),
          ("anger_outbursts", True, "我会突然爆发，控制不住。", "high"),
          ("outburst_disproportionate", True, "事后看会发现反应太大了。", "high"),
          ("outburst_remorse", True, "发作之后我一般都会后悔。", "medium"),
          ("substance_misuse", False, "不是酒精或药物造成的。", "high"),
          ("aggression_physical", True, "我会推搡别人。", "medium"),
          ("outburst_premeditation", False, "我不是预先计划好的。", "medium"),
          _imp4("college", "moderate", "这已经影响我的关系。")]),
        ("26-40", "F", "family", "气极了我会想伤人。", "近一年我多次因琐事爆发，会冒出伤人的念头，关系受损。", "反应不成比例且有侵害意念。",
         [("duration", "1 year", "差不多持续了 1 year。", "high"),
          ("anger_outbursts", True, "我会突然爆发，控制不住。", "high"),
          ("outburst_disproportionate", True, "事后看会发现反应太大了。", "high"),
          ("outburst_remorse", True, "发作之后我一般都会后悔。", "medium"),
          ("substance_misuse", False, "不是酒精或药物造成的。", "high"),
          ("violence_ideation", True, "气极了会想伤人。", "medium"),
          ("family_conflict", True, "家里常因此吵架。", "medium"),
          _imp4("family", "moderate", "这已经影响我的关系。")]),
        ("26-40", "M", "community", "发火后我常喝酒、还会动手。", "近九个月我会突然冲动发火，有时推搡别人，之后靠酒缓压。", "冲动型愤怒发作伴物质使用。",
         [("duration", "9 months", "差不多持续了 9 months。", "high"),
          ("anger_outbursts", True, "我会突然爆发，控制不住。", "high"),
          ("outburst_disproportionate", True, "事后看会发现反应太大了。", "high"),
          ("outburst_remorse", True, "发作之后我一般都会后悔。", "medium"),
          ("substance_misuse", True, "发火后我常喝酒缓压。", "medium"),
          ("aggression_physical", True, "我会推搡别人。", "medium"),
          _imp4("community", "moderate", "这已经影响我的关系。")]),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, slot_specs) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        imp_slot = slot_specs[-1][0]
        risk = {"suicide": False, "violence": False, "psychosis": False, "substance": False}
        must_ask = ["duration", "anger_outbursts", "substance_misuse", imp_slot]
        for s in slot_specs:
            if s[0] in {"aggression_physical", "aggression_property_damage", "violence_ideation"} and s[1] is True:
                if s[0] not in must_ask:
                    must_ask.append(s[0])
        has_violence_slot = any(s[0] in {"aggression_physical", "aggression_property_damage", "violence_ideation"} for s in slot_specs)
        if has_violence_slot:
            risk["violence"] = True
        if any(s[0] == "substance_misuse" and s[1] is True for s in slot_specs):
            risk["substance"] = True
        rows.append(G._build_case(
            case_id, "DICCD", "IED", None, ambiguity, age_band, gender, context,
            minimal_cc, self_report, chart_full, slot_specs,
            ["IED", "BPD", "ADJ", "PMDD", "OTHER"], risk,
            ["symptom_profile", "course_stability", "functional_impairment", "comorbidity_pattern"],
            must_ask,
            ["course_stability", "symptom_profile", "comorbidity_pattern", "functional_impairment"],
        ))
    return rows


def _bpd_cases_new(start_index: int):
    specs = [
        ("18-25", "F", "community", "关系一乱我就会想伤害自己。", "很多年里我关系和情绪都很不稳定，压力大时会有自伤想法。", "长期不稳定人格模式伴自伤风险。",
         [("longstanding_pattern", True, "这种状态已经很多年了。", "high"),
          ("relationship_instability", True, "我的关系经常忽好忽坏。", "high"),
          ("abandonment_sensitivity", True, "我特别怕别人不要我。", "medium"),
          ("chronic_emptiness", True, "我会长期觉得心里空空的。", "medium"),
          ("self_harm_ideation", True, "压力大时我会有自伤念头。", "high"),
          ("emotion_regulation_difficulty", "severe", "情绪一上来就控制不住。", "medium"),
          ("avoidance_behavior", True, "怕被丢下我就会躲开。", "medium"),
          _imp4("community", "severe", "这已经严重影响我的关系。")]),
        ("26-40", "M", "community", "我常不知道自己是谁。", "这些年我情绪起伏大，也很难稳定看待自己，常冲动。", "身份不稳、冲动和长期人际问题并存。",
         [("longstanding_pattern", True, "这种状态已经很多年了。", "high"),
          ("relationship_instability", True, "我的关系经常忽好忽坏。", "high"),
          ("abandonment_sensitivity", True, "我特别怕别人不要我。", "medium"),
          ("chronic_emptiness", True, "我会长期觉得心里空空的。", "medium"),
          ("identity_disturbance", True, "我常常不知道自己到底是谁。", "medium"),
          ("impulsivity_non_substance", True, "我常冲动行事。", "medium"),
          _imp4("community", "moderate", "这已经影响我的关系。")]),
        ("26-40", "F", "family", "压力大时我会觉得别人在害我。", "很多年里我关系不稳、情绪大起大落，压力大时会短暂非常怀疑别人。", "长期人格模式伴应激相关偏执样体验。",
         [("longstanding_pattern", True, "这种状态已经很多年了。", "high"),
          ("relationship_instability", True, "我的关系经常忽好忽坏。", "high"),
          ("abandonment_sensitivity", True, "我特别怕别人不要我。", "medium"),
          ("chronic_emptiness", True, "我会长期觉得心里空空的。", "medium"),
          ("transient_paranoia_stress_related", True, "压力大时我会突然非常怀疑别人害我。", "medium"),
          ("dissociation_like_symptom", True, "崩溃时像魂飘在外面。", "medium"),
          _imp4("family", "severe", "这已经严重影响我的关系。")]),
        ("18-25", "F", "college", "我有时想自伤，也会借酒消愁。", "这些年我常感空虚、关系混乱，压力大有自伤念头，也会喝酒。", "慢性空虚感、自伤与物质使用并存。",
         [("longstanding_pattern", True, "这种状态已经很多年了。", "high"),
          ("relationship_instability", True, "我的关系经常忽好忽坏。", "high"),
          ("abandonment_sensitivity", True, "我特别怕别人不要我。", "medium"),
          ("chronic_emptiness", True, "我会长期觉得心里空空的。", "medium"),
          ("substance_misuse", True, "我会借酒消愁。", "medium"),
          ("self_harm_ideation", True, "有时我会有自伤想法。", "high"),
          _imp4("college", "severe", "这已经严重影响我的学习。")]),
        ("41-60", "F", "family", "早年创伤后我一直很难稳定。", "这么多年我关系不稳、情绪起伏，早年有创伤，常回避。", "长期人格模式伴创伤史。",
         [("longstanding_pattern", True, "这种状态已经很多年了。", "high"),
          ("relationship_instability", True, "我的关系经常忽好忽坏。", "high"),
          ("abandonment_sensitivity", True, "我特别怕别人不要我。", "medium"),
          ("chronic_emptiness", "moderate", "常觉得心里空空的。", "medium"),
          ("trauma_exposure", True, "早年有过让我受创的经历。", "medium"),
          ("avoidance_behavior", True, "我会回避相关的场合。", "medium"),
          _imp4("family", "moderate", "这已经影响我的关系。")]),
    ]
    rows = []
    for offset, (age_band, gender, context, minimal_cc, self_report, chart_full, slot_specs) in enumerate(specs):
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        imp_slot = slot_specs[-1][0]
        risk = {"suicide": False, "violence": False, "psychosis": False, "substance": False}
        must_ask = ["longstanding_pattern", "relationship_instability", "abandonment_sensitivity", imp_slot]
        if any(s[0] == "self_harm_ideation" for s in slot_specs):
            risk["suicide"] = True
            must_ask.append("self_harm_ideation")
        if any(s[0] == "transient_paranoia_stress_related" for s in slot_specs):
            risk["psychosis"] = True
            must_ask.append("transient_paranoia_stress_related")
        if any(s[0] == "substance_misuse" for s in slot_specs):
            risk["substance"] = True
            must_ask.append("substance_misuse")
        rows.append(G._build_case(
            case_id, "PD", "BPD", None, ambiguity, age_band, gender, context,
            minimal_cc, self_report, chart_full, slot_specs,
            ["BPD", "IED", "PMDD", "ADJ", "OTHER"], risk,
            ["temperament_personality", "functional_impairment", "comorbidity_pattern", "cog_emotion_process"],
            must_ask,
            ["temperament_personality", "functional_impairment", "cog_emotion_process", "comorbidity_pattern"],
        ))
    return rows


def _ocpd_cases_new(start_index: int):
    specs = [
        ("26-40", "M", "office", "我总因控制欲和同事冲突。", "很多年里我很难把事情交给别人，不按我的方式就焦虑，常吵架。", "控制和委派困难突出。",
         [("longstanding_pattern", True, "很多年都是这样。", "high"),
          ("perfectionism_trait", True, "我很难容忍不完美。", "high"),
          ("rigidity_control_need", True, "我很难接受灵活变化。", "medium"),
          ("intrusive_thoughts", False, "不是那种闯进来的强迫念头。", "medium"),
          ("rigidity_morality", True, "对非黑即白我很执着。", "medium"),
          ("reluctance_delegate", True, "我很难把事情放心交给别人。", "medium"),
          ("interpersonal_control_conflict", True, "常因控制欲和同事冲突。", "medium"),
          _imp4("office", "moderate", "这已经拖慢了我的工作。")]),
        ("41-60", "M", "family", "我对规则特别僵硬，家人受不了。", "这些年我对规则和细节要求很僵硬，经常因此和家人冲突，也较真。", "僵硬标准和关系冲突并存。",
         [("longstanding_pattern", True, "很多年都是这样。", "high"),
          ("perfectionism_trait", True, "我很难容忍不完美。", "high"),
          ("rigidity_control_need", True, "我很难接受灵活变化。", "medium"),
          ("intrusive_thoughts", False, "不是那种闯进来的强迫念头。", "medium"),
          ("rigidity_morality", True, "我对规则和做法特别僵硬。", "medium"),
          ("family_history_ocrd", True, "家里人也有点较真。", "medium"),
          ("comorbid_depression_history", True, "我有过一段明显抑郁。", "medium"),
          _imp4("family", "moderate", "这已经影响我的关系。")]),
        ("18-25", "F", "college", "我会为了完美把作业拖很晚。", "上大学后我总因完美主义和秩序要求拖慢任务，做过咨询。", "完美主义影响学业效率。",
         [("longstanding_pattern", True, "很多年都是这样。", "high"),
          ("perfectionism_trait", True, "我很难容忍不完美。", "high"),
          ("rigidity_control_need", True, "我很难接受灵活变化。", "medium"),
          ("intrusive_thoughts", False, "不是那种闯进来的强迫念头。", "medium"),
          ("reluctance_delegate", True, "小组作业我也不放心交给别人。", "medium"),
          ("treatment_history", "psychotherapy", "我做过一段时间咨询。", "medium"),
          _imp4("college", "moderate", "这已经影响我的学习。")]),
        ("26-40", "F", "office", "不按我来的时候我非常烦躁。", "很多年里我坚持自己那一套，导致合作和效率都受影响，也较真。", "长期刚性控制模式明显。",
         [("longstanding_pattern", True, "很多年都是这样。", "high"),
          ("perfectionism_trait", True, "我很难容忍不完美。", "high"),
          ("rigidity_control_need", True, "我很难接受灵活变化。", "medium"),
          ("intrusive_thoughts", False, "不是那种闯进来的强迫念头。", "medium"),
          ("rigidity_morality", True, "我对规则和做法特别僵硬。", "medium"),
          ("reluctance_delegate", True, "我很难把事情交给别人。", "medium"),
          ("emotion_regulation_difficulty", "moderate", "不按我来的时候很烦。", "medium"),
          _imp4("office", "severe", "这已经严重影响我的工作。")]),
        ("41-60", "F", "family", "我会回避不严谨的场合。", "这些年我做事追求完美和秩序，会回避不严谨的环境，关系偏僵。", "完美主义与回避并存。",
         [("longstanding_pattern", True, "很多年都是这样。", "high"),
          ("perfectionism_trait", True, "我很难容忍不完美。", "high"),
          ("rigidity_control_need", True, "我很难接受灵活变化。", "medium"),
          ("intrusive_thoughts", False, "不是那种闯进来的强迫念头。", "medium"),
          ("rigidity_morality", True, "我对规则和做法特别僵硬。", "medium"),
          ("avoidance_behavior", True, "我会回避不严谨的场合。", "medium"),
          _imp4("family", "moderate", "这已经影响我的关系。")]),
    ]
    return _emit(start_index, "PD", "OCPD", None, specs,
                 ["OCPD", "OCD", "ADJ", "BDD", "OTHER"],
                 {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                 ["temperament_personality", "functional_impairment", "cog_emotion_process"],
                 ["longstanding_pattern", "perfectionism_trait", "intrusive_thoughts"])


def _other_cases_new(start_index: int):
    specs = [
        ("18-25", "X", "college", "最近状态不太对，但说不清。", "最近注意力差、睡得浅、偶尔没精神，时间和诱因都不太清楚。", "信息不足，暂不能归入已定义标签。",
         [("onset_time", "unknown", "我记不清具体是什么时候开始。", "low"),
          ("stressor_present", "unknown", "好像没有特别明确的一件事。", "low"),
          ("anxiety_tension", "mild", "有一点心烦和紧张。", "medium"),
          ("sleep_insomnia", "mild", "晚上睡得浅。", "medium"),
          ("energy_low", "mild", "偶尔没精神。", "medium"),
          _imp4("college", "mild", "有一点影响，但我也说不清。")]),
        ("26-40", "F", "community", "最近就是觉得整个人不太对劲。", "近来有些心烦、注意力不太集中，但描述很零散。", "信息不足且症状非特异。",
         [("onset_time", "unknown", "我记不清具体是什么时候开始。", "low"),
          ("stressor_present", "unknown", "好像没有特别明确的一件事。", "low"),
          ("anxiety_tension", "mild", "有一点心烦。", "medium"),
          ("concentration_problem", "mild", "有时集中不了。", "medium"),
          ("avoidance_behavior", False, "我倒没有特意回避什么。", "low"),
          _imp4("community", "mild", "有一点影响，但说不清。")]),
        ("41-60", "M", "family", "最近总觉得提不起劲，又说不上来。", "这段时间有些低落、胃口时好时坏，但没有清楚线索指向哪类问题。", "轻度非特异主诉，仍需补充评估。",
         [("onset_time", "unknown", "我记不清具体是什么时候开始。", "low"),
          ("stressor_present", "unknown", "好像没有特别明确的一件事。", "low"),
          ("anxiety_tension", "mild", "有一点心烦。", "medium"),
          ("depressed_mood", "mild", "偶尔会低落。", "medium"),
          ("appetite_change", "fluctuating", "胃口时好时坏。", "medium"),
          _imp4("family", "moderate", "有一点影响，但我也说不清。")]),
        ("18-25", "F", "college", "我最近就是很乱。", "最近注意力差、提不起劲，朋友也不多，描述零散。", "现有信息不足以判断。",
         [("onset_time", "unknown", "我记不清具体是什么时候开始。", "low"),
          ("stressor_present", "unknown", "好像没有特别明确的一件事。", "low"),
          ("anxiety_tension", "mild", "有一点心烦。", "medium"),
          ("anhedonia", "mild", "对事情提不起劲。", "medium"),
          ("social_support_low", True, "身边朋友不多。", "medium"),
          _imp4("college", "mild", "有一点影响，但我也说不清。")]),
        ("26-40", "M", "office", "我最近状态不好，但没有特别明确的点。", "最近偶尔这里酸那里痛、睡不好，持续时间和触发都不稳定。", "非特异症状，需进一步结构化访谈。",
         [("onset_time", "unknown", "我记不清具体是什么时候开始。", "low"),
          ("stressor_present", "unknown", "好像没有特别明确的一件事。", "low"),
          ("anxiety_tension", "mild", "有一点心烦。", "medium"),
          ("somatic_symptom_distress", "mild", "偶尔这里酸那里痛。", "medium"),
          ("sleep_insomnia", "mild", "晚上睡得浅。", "medium"),
          _imp4("office", "mild", "有一点影响，但我也说不清。")]),
    ]
    return _emit(start_index, "OTHER", "OTHER", None, specs,
                 ["OTHER", "ADJ", "SSD", "PMDD", "OCD"],
                 {"suicide": False, "violence": False, "psychosis": False, "substance": False},
                 ["course_stability", "environmental_risk", "functional_impairment"],
                 ["onset_time", "stressor_present"])


def _emit(start_index, dsm_module, label, subtype, specs, gold, risk_base, req_dom, must_ask_base):
    rows = []
    for offset, spec in enumerate(specs):
        age_band, gender, context, minimal_cc, self_report, chart_full, slot_specs = spec
        case_id = f"PIB_{start_index + offset:04d}"
        ambiguity = "ambiguous" if offset < 2 else "unambiguous"
        imp_slot = slot_specs[-1][0]
        must_ask = list(must_ask_base) + [imp_slot]
        rows.append(G._build_case(
            case_id, dsm_module, label, subtype, ambiguity, age_band, gender, context,
            minimal_cc, self_report, chart_full, slot_specs, gold, risk_base, req_dom, must_ask, req_dom,
        ))
    return rows


def generate_casebank_v2():
    rows = []
    # ---- original 55 seeds (exact, ids 0001..0055) ----
    rows += G._ocd_cases(1)
    rows += G._bdd_cases(6)
    rows += G._os_ocrd_cases(11)
    rows += G._adj_cases(16)
    rows += G._pgd_cases(21)
    rows += G._ssd_cases(26)
    rows += G._pmdd_cases(31)
    rows += G._ied_cases(36)
    rows += G._bpd_cases(41)
    rows += G._ocpd_cases(46)
    rows += G._other_cases(51)
    # ---- 55 NEW distinct seeds (ids 0056..0110) ----
    rows += _ocd_cases_new(56)
    rows += _bdd_cases_new(61)
    rows += _os_ocrd_cases_new(66)
    rows += _adj_cases_new(71)
    rows += _pgd_cases_new(76)
    rows += _ssd_cases_new(81)
    rows += _pmdd_cases_new(86)
    rows += _ied_cases_new(91)
    rows += _bpd_cases_new(96)
    rows += _ocpd_cases_new(101)
    rows += _other_cases_new(106)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate 110 distinct synthetic PIB cases (v2)")
    parser.add_argument("--output", type=Path, default=Path("authoring/pilot_casebank_v12.csv"))
    args = parser.parse_args()

    cases_and_rubrics = generate_casebank_v2()
    rows = [G._row_from_case(case, rubric) for case, rubric in cases_and_rubrics]
    G._write_csv(args.output, rows)
    print(f"Generated {len(rows)} authoring rows at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
