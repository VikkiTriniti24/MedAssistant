"""Generate dosage guidance based on stored drug metadata."""
from __future__ import annotations

from typing import Dict, List, Optional

from ..models import Drug


def build_dosage_guidance(enriched_items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Produce dosage advice using standard dose and max daily dose data."""
    guidance: List[Dict[str, object]] = []
    for item in enriched_items:
        drug: Optional[Drug] = item.get("drug_row")  # type: ignore[assignment]
        if not isinstance(drug, Drug):
            continue

        standard = getattr(drug, "standard_dosage", None)
        max_daily = getattr(drug, "max_daily_dose", None)
        reported_dose = item.get("dose")
        freq = item.get("freq_per_day")

        note_parts: List[str] = []
        if standard:
            note_parts.append(f"Typical dose {standard}")
        if max_daily is not None:
            note_parts.append(f"Max daily {max_daily:g} mg")

        if reported_dose and standard and str(reported_dose).strip().lower() != str(standard).strip().lower():
            note_parts.append(f"Reported dose {reported_dose}")
        if freq and isinstance(freq, int):
            note_parts.append(f"Frequency {freq}× per day")

        if not note_parts:
            note_parts.append("No reference dosing information available")

        guidance.append({
            "drug": drug.name,
            "standard_dosage": standard,
            "max_daily_dose": max_daily,
            "reported_dose": reported_dose,
            "freq_per_day": freq,
            "note": "; ".join(note_parts),
        })

    return guidance

