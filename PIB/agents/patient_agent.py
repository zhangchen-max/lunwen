from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any

from eval.schema import CaseRecord


@dataclass
class PatientReply:
    slot_id: str
    value: Any
    utterance: str
    certainty: str


def _stable_seed(seed: int, case_id: str, slot_id: str, turn: int) -> int:
    digest = hashlib.sha256(f"{case_id}:{slot_id}:{turn}".encode("utf-8")).hexdigest()
    return seed + int(digest[:12], 16)


class PatientAgent:
    """Deterministic patient simulator that only returns case-grounded facts."""

    def __init__(self, default_seed: int = 1234):
        self.default_seed = default_seed

    def answer(self, case: CaseRecord, slot_id: str, seed: int | None = None, turn: int = 0) -> PatientReply:
        seed_value = self.default_seed if seed is None else seed

        if slot_id in case.slot_truth:
            truth = case.slot_truth[slot_id]
            utterances = case.patient_script.get(slot_id) or case.patient_script["unknown_default"]
            rng = random.Random(_stable_seed(seed_value, case.case_id, slot_id, turn))
            utterance = utterances[rng.randrange(len(utterances))]
            return PatientReply(
                slot_id=slot_id,
                value=truth.value,
                utterance=utterance,
                certainty=truth.certainty,
            )

        fallback = case.patient_script["unknown_default"]
        rng = random.Random(_stable_seed(seed_value, case.case_id, "unknown_default", turn))
        utterance = fallback[rng.randrange(len(fallback))]
        return PatientReply(
            slot_id=slot_id,
            value="unknown",
            utterance=utterance,
            certainty="low",
        )
