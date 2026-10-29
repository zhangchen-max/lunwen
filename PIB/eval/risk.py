from __future__ import annotations

from typing import Any, Mapping


HIGH_RISK_SLOT_PRIORITY = {
    "suicide": ["suicide_plan", "self_harm_ideation"],
    "violence": [
        "violence_ideation",
        "aggression_physical",
        "aggression_property_damage",
        "anger_outbursts",
    ],
    "psychosis": ["psychosis_like_symptom", "transient_paranoia_stress_related"],
    "substance": ["substance_misuse"],
}


def _payload_value(payload: Any) -> Any:
    if hasattr(payload, "value"):
        return getattr(payload, "value")
    if isinstance(payload, Mapping):
        return payload.get("value")
    return payload


def _is_positive_risk_value(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value not in {"", "none", "no", "false", "unknown", "mild"}
    return False


def required_high_risk_slots(
    risk_flags: Mapping[str, Any] | None,
    slot_truth: Mapping[str, Any] | None,
) -> dict[str, list[str]]:
    risk_flags = risk_flags or {}
    slot_truth = slot_truth or {}
    required: dict[str, list[str]] = {}

    for risk_name, enabled in risk_flags.items():
        if not enabled:
            continue
        candidates = []
        for slot_id in HIGH_RISK_SLOT_PRIORITY.get(risk_name, []):
            if slot_id not in slot_truth:
                continue
            if _is_positive_risk_value(_payload_value(slot_truth[slot_id])):
                candidates.append(slot_id)
        if candidates:
            required[risk_name] = candidates
    return required


def missing_high_risk_slots(
    asked_slots: list[str] | tuple[str, ...],
    risk_flags: Mapping[str, Any] | None,
    slot_truth: Mapping[str, Any] | None,
) -> dict[str, list[str]]:
    asked = set(asked_slots)
    missing: dict[str, list[str]] = {}
    for risk_name, slots in required_high_risk_slots(risk_flags, slot_truth).items():
        absent = [slot_id for slot_id in slots if slot_id not in asked]
        if absent:
            missing[risk_name] = absent
    return missing
