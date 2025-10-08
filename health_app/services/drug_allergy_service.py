"""Utility helpers for detecting drug allergy conflicts."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from ..models import Drug


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def assess_allergy_conflicts(drugs: Iterable[Drug], allergies: Iterable[str]) -> Dict[str, List[str]]:
    """Return structured allergy conflict information for the supplied drugs."""
    normalized_map: Dict[str, str] = {}
    for entry in allergies or []:
        norm = _normalize(entry)
        if not norm:
            continue
        normalized_map.setdefault(norm, entry.strip())

    normalized_keys = set(normalized_map.keys())
    if not normalized_keys:
        return {
            "conflicts": [],
            "normalized_allergies": [],
            "matched_allergies": [],
            "unmatched_allergies": [],
        }

    conflicts: List[Dict[str, object]] = []
    matched_keys: Set[str] = set()

    for drug in drugs:
        if not drug:
            continue
        drug_name = getattr(drug, "name", "") or ""
        drug_name_norm = _normalize(drug_name)

        matched_names: List[str] = []
        if drug_name_norm in normalized_keys:
            matched_names.append(normalized_map.get(drug_name_norm, drug_name))
            matched_keys.add(drug_name_norm)

        matched_substances: List[str] = []
        for substance in getattr(drug, "substances", []) or []:
            sub_name = getattr(substance, "name", "") or ""
            sub_norm = _normalize(sub_name)
            if sub_norm in normalized_keys:
                matched_substances.append(substance.name)
                matched_keys.add(sub_norm)

        if matched_names or matched_substances:
            allergens = matched_names + matched_substances
            # Preserve original ordering, but ensure deterministic output via lower-case sort
            allergens_sorted = sorted(allergens, key=lambda v: v.lower())

            conflicts.append({
                "drug": drug_name,
                "drug_id": getattr(drug, "id", None),
                "allergens": allergens_sorted,
                "matched_names": matched_names,
                "matched_substances": matched_substances,
                "notes": "Potential allergy conflict with drug name or its substances.",
            })

    unmatched_keys = sorted(normalized_keys.difference(matched_keys))

    def _to_original(key: str) -> str:
        return normalized_map.get(key, key)

    return {
        "conflicts": conflicts,
        "normalized_allergies": [_to_original(k) for k in sorted(normalized_keys)],
        "matched_allergies": [_to_original(k) for k in sorted(matched_keys)],
        "unmatched_allergies": [_to_original(k) for k in unmatched_keys],
    }

