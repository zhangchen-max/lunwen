from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator
from eval.constants import (
    REQUIRED_DYNAMIC_MAX_TURNS,
    REQUIRED_OS_OCRD_SUBTYPES,
)


Certainty = Literal["low", "medium", "high"]
Ambiguity = Literal["ambiguous", "unambiguous"]
ActionType = Literal["ASK", "FINAL"]


class SlotValue(BaseModel):
    value: Any
    certainty: Certainty
    source: str = "interview"
    evidence: List[str] = Field(default_factory=list)


class InfoVariants(BaseModel):
    minimal_cc: str
    self_report: str
    chart_full: str


class RiskFlags(BaseModel):
    suicide: bool = False
    violence: bool = False
    psychosis: bool = False
    substance: bool = False


class CaseRecord(BaseModel):
    case_id: str
    dsm_module: str
    label: str
    label_subtype: Optional[str] = None
    ambiguity: Ambiguity = "ambiguous"

    patient_profile: Dict[str, Any] = Field(default_factory=dict)
    info_variants: InfoVariants

    slot_truth: Dict[str, SlotValue]
    gold_ddx_top5: List[str]

    risk_flags: RiskFlags = Field(default_factory=RiskFlags)
    required_svcl_domains: List[str] = Field(default_factory=list)

    patient_script: Dict[str, List[str]]

    @model_validator(mode="after")
    def check_required_fields(self) -> "CaseRecord":
        if not self.case_id.strip():
            raise ValueError("case_id must be non-empty")
        if not self.gold_ddx_top5:
            raise ValueError("gold_ddx_top5 cannot be empty")
        if "unknown_default" not in self.patient_script:
            raise ValueError("patient_script must contain unknown_default")
        if not self.patient_script["unknown_default"]:
            raise ValueError("patient_script.unknown_default cannot be empty")
        if self.label == "OS_OCRD" and not self.label_subtype:
            raise ValueError("label_subtype is required when label == OS_OCRD")
        if self.label == "OS_OCRD" and self.label_subtype not in REQUIRED_OS_OCRD_SUBTYPES:
            raise ValueError(
                f"label_subtype must be one of {REQUIRED_OS_OCRD_SUBTYPES} when label == OS_OCRD"
            )
        return self


class StopRules(BaseModel):
    max_turns: int = REQUIRED_DYNAMIC_MAX_TURNS

    @model_validator(mode="after")
    def check_turn_cap(self) -> "StopRules":
        if self.max_turns <= 0:
            raise ValueError("stop_rules.max_turns must be > 0")
        if self.max_turns > REQUIRED_DYNAMIC_MAX_TURNS:
            raise ValueError(f"stop_rules.max_turns must be <= {REQUIRED_DYNAMIC_MAX_TURNS}")
        return self


class RubricRecord(BaseModel):
    case_id: str
    must_ask_slots: List[str]
    must_ask_svcl_domains: List[str] = Field(default_factory=list)
    avoid_harm_rules: List[str] = Field(default_factory=list)
    stop_rules: StopRules = Field(default_factory=StopRules)

    @model_validator(mode="after")
    def check_must_ask(self) -> "RubricRecord":
        if not self.case_id.strip():
            raise ValueError("case_id must be non-empty")
        if not self.must_ask_slots:
            raise ValueError("must_ask_slots cannot be empty")
        return self


class DiagnosisItem(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)


class JustificationItem(BaseModel):
    claim: str
    support_slots: List[str] = Field(default_factory=list)


class NextStepItem(BaseModel):
    type: str
    text: str


class CalibrationBlock(BaseModel):
    uncertainty_statement: str


class FinalOutput(BaseModel):
    diagnosis_topk: List[DiagnosisItem]
    slot_predictions: Dict[str, Any] = Field(default_factory=dict)
    risk_flags: RiskFlags = Field(default_factory=RiskFlags)
    justification: List[JustificationItem] = Field(default_factory=list)
    next_steps: List[NextStepItem] = Field(default_factory=list)
    calibration: CalibrationBlock


class AskAction(BaseModel):
    action: Literal["ASK"]
    slot_id: str
    utterance: Optional[str] = None


class FinalAction(BaseModel):
    action: Literal["FINAL"]
    final_output: FinalOutput


class ParseErrorAction(BaseModel):
    action: Literal["PARSE_ERROR"]
    error: str


AnyAction = AskAction | FinalAction | ParseErrorAction
