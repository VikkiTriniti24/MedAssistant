"""Utility helpers for approximating symptom severity scores.

The scoring logic intentionally stays deterministic and explainable so unit tests
can assert against it. We combine heuristics from the incoming payload together
with hints from the AI response (risk level, urgency, triage levels) to derive a
0-100 score plus short textual factors.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

# Keyword groups that should immediately raise the severity score. Expressions
# are matched case-insensitively against the symptoms text.
_CRITICAL_PHRASES: Iterable[str] = {
    "chest pain",
    "crushing pain",
    "shortness of breath",
    "difficulty breathing",
    "can't breathe",
    "severe bleeding",
    "unconscious",
    "fainting",
    "stroke",
    "seizure",
    "numbness on one side",
    "speech slurred",
}

_HIGH_PHRASES: Iterable[str] = {
    "high fever",
    "persistent vomiting",
    "severe pain",
    "blood in stool",
    "blood in urine",
    "rapid heartbeat",
    "dizziness",
    "confusion",
    "blurry vision",
}


@dataclass(frozen=True)
class SeverityResult:
    score: int
    level: str
    factors: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {"score": self.score, "level": self.level, "factors": list(self.factors)}


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def _maybe_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_symptom_severity(
    payload: Dict[str, Any],
    ai_response: Dict[str, Any],
    *,
    symptoms_text: str = "",
) -> Dict[str, Any]:
    """Return a severity dict with score/level/factors based on heuristics."""
    score = 10.0  # start with a neutral baseline
    factors: List[str] = []

    risk_eval = ai_response.get("risk_evaluation") or {}
    risk_level = str(risk_eval.get("risk_level", "")).strip().lower()
    urgency = str(risk_eval.get("urgency", "")).strip().lower()

    risk_baseline = {
        "low": 25.0,
        "medium": 50.0,
        "high": 75.0,
        "critical": 90.0,
    }
    if risk_level in risk_baseline:
        score = max(score, risk_baseline[risk_level])
        factors.append(f"AI risk level: {risk_level}")

    urgency_bonus = {
        "self-care": 0.0,
        "see-doctor": 5.0,
        "urgent-care": 15.0,
        "emergency": 22.0,
    }
    if urgency in urgency_bonus:
        score += urgency_bonus[urgency]
        if urgency_bonus[urgency] > 0:
            factors.append(f"AI urgency recommendation: {urgency}")

    # Triage levels from diagnoses give additional hints.
    diagnoses = ai_response.get("diagnoses") or []
    for diag in diagnoses:
        triage = str(diag.get("triage", "")).lower()
        probability = _maybe_number(diag.get("probability")) or 0.0
        if triage == "high":
            score += 25.0 * max(0.3, probability)
            factors.append(f"High-triage diagnosis: {diag.get('condition', 'Unknown')}")
        elif triage == "medium":
            score += 10.0 * max(0.2, probability)

    # Patient basics -----------------------------------------------------------------
    age = payload.get("age")
    age_num = _maybe_number(age)
    if age_num is not None:
        if age_num <= 5 or age_num >= 75:
            score += 12.0
            factors.append(f"Age in higher risk bracket ({int(age_num)} years)")
        elif age_num <= 12 or age_num >= 65:
            score += 7.0
            factors.append(f"Age slightly elevated risk ({int(age_num)} years)")

    if payload.get("pregnant") is True:
        score += 6.0
        factors.append("Pregnancy reported")

    conditions = payload.get("conditions")
    if isinstance(conditions, list) and conditions:
        if len(conditions) >= 3:
            score += 8.0
            factors.append("Multiple chronic conditions")
        else:
            score += 4.0
            factors.append("Existing chronic condition")

    # Vitals -------------------------------------------------------------------------
    vitals = payload.get("vitals")
    if isinstance(vitals, dict):
        temp_c = _maybe_number(vitals.get("temp_c"))
        if temp_c is not None:
            if temp_c >= 39.5:
                score += 15.0
                factors.append(f"High fever ({temp_c:.1f} °C)")
            elif temp_c >= 38.0:
                score += 8.0
                factors.append(f"Fever ({temp_c:.1f} °C)")
            elif temp_c <= 35.0:
                score += 12.0
                factors.append(f"Hypothermia risk ({temp_c:.1f} °C)")

        heart_rate = _maybe_number(vitals.get("hr"))
        if heart_rate is not None:
            if heart_rate >= 120:
                score += 10.0
                factors.append(f"Tachycardia (HR {int(heart_rate)} bpm)")
            elif heart_rate >= 100:
                score += 6.0
                factors.append(f"Elevated heart rate (HR {int(heart_rate)} bpm)")
            elif heart_rate <= 45:
                score += 10.0
                factors.append(f"Bradycardia (HR {int(heart_rate)} bpm)")

        systolic = _maybe_number(vitals.get("bp_sys"))
        diastolic = _maybe_number(vitals.get("bp_dia"))
        if systolic is not None:
            if systolic >= 180:
                score += 12.0
                factors.append(f"Hypertensive crisis (BP sys {int(systolic)})")
            elif systolic <= 90:
                score += 8.0
                factors.append(f"Low systolic pressure (BP sys {int(systolic)})")
        if diastolic is not None:
            if diastolic >= 110:
                score += 12.0
                factors.append(f"Hypertensive crisis (BP dia {int(diastolic)})")
            elif diastolic <= 60:
                score += 4.0
                factors.append(f"Low diastolic pressure (BP dia {int(diastolic)})")

        spo2 = _maybe_number(vitals.get("spo2"))
        if spo2 is not None:
            if spo2 < 90:
                score += 20.0
                factors.append(f"Critical oxygen saturation ({spo2:.0f}%)")
            elif spo2 < 94:
                score += 10.0
                factors.append(f"Low oxygen saturation ({spo2:.0f}%)")

    # Symptoms text ---------------------------------------------------------------
    text = (symptoms_text or payload.get("symptoms") or "").lower()
    if text:
        for phrase in _CRITICAL_PHRASES:
            if phrase in text:
                score += 25.0
                factors.append(f"Critical symptom phrase detected: '{phrase}'")
        for phrase in _HIGH_PHRASES:
            if phrase in text:
                score += 12.0
                factors.append(f"Severe symptom phrase detected: '{phrase}'")
        if "mild" in text and score > 20:
            score -= 3.0  # slightly dampen when explicitly stated mild
        if "slight" in text and score > 20:
            score -= 2.0

    score = _clamp(score)

    if score >= 85:
        level = "critical"
    elif score >= 65:
        level = "high"
    elif score >= 40:
        level = "moderate"
    else:
        level = "low"

    if not factors:
        factors.append("Baseline assessment")

    result = SeverityResult(score=int(round(score)), level=level, factors=list(dict.fromkeys(factors)))
    return result.as_dict()
