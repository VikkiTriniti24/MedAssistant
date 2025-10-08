"""Utilities for detecting contraindications between drugs and conditions."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from sqlalchemy import or_, func

from .. import db
from ..models import Drug, Condition, Contraindication


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def assess_contraindications(
    drugs: Iterable[Drug],
    profile_conditions: Iterable[Condition],
    extra_condition_names: Iterable[str],
) -> Dict[str, List[Dict[str, object]]]:
    """Return structured contraindication info for supplied drugs and conditions."""

    drug_rows = [drug for drug in drugs if getattr(drug, "id", None)]
    if not drug_rows:
        return {
            "matches": [],
            "matched_conditions": [],
            "unmatched_conditions": list({
                name.strip() for name in extra_condition_names if name and name.strip()
            }),
        }

    drug_ids = {drug.id for drug in drug_rows}

    # Collect condition identifiers and names
    condition_id_set: Set[int] = set()
    condition_name_map: Dict[int, str] = {}

    for condition in profile_conditions or []:
        if not condition:
            continue
        if getattr(condition, "id", None) is not None:
            condition_id_set.add(condition.id)
            condition_name_map[condition.id] = condition.name

    normalized_names: Set[str] = {
        _normalize(name) for name in extra_condition_names if _normalize(name)
    }
    for condition_id, label in condition_name_map.items():
        normalized = _normalize(label)
        if normalized:
            normalized_names.add(normalized)

    if not normalized_names and not condition_id_set:
        return {
            "matches": [],
            "matched_conditions": [],
            "unmatched_conditions": [],
        }

    # Build query joining Condition to get names
    query = (
        db.session.query(Contraindication, Condition)
        .join(Condition, Contraindication.condition_id == Condition.id)
        .filter(Contraindication.drug_id.in_(drug_ids))
    )

    conditions_filter = []
    if condition_id_set:
        conditions_filter.append(Contraindication.condition_id.in_(condition_id_set))
    if normalized_names:
        conditions_filter.append(func.lower(Condition.name).in_(normalized_names))

    if conditions_filter:
        query = query.filter(or_(*conditions_filter))

    matches: List[Dict[str, object]] = []
    matched_condition_names: Set[str] = set()

    for contra_row, condition_row in query.all():
        if not contra_row or not condition_row:
            continue
        matched_condition_names.add(condition_row.name)
        drug = next((d for d in drug_rows if d.id == contra_row.drug_id), None)
        matches.append({
            "drug": getattr(drug, "name", ""),
            "drug_id": contra_row.drug_id,
            "condition": condition_row.name,
            "condition_id": condition_row.id,
            "notes": contra_row.notes,
        })

    unmatched_names = sorted(
        {
            name
            for name in normalized_names
            if name not in {_normalize(m) for m in matched_condition_names}
        }
    )

    # Convert normalized unmatched names back to best-effort original casing from inputs
    original_name_lookup: Dict[str, str] = {}
    for cond in profile_conditions or []:
        normalized = _normalize(cond.name)
        if normalized and normalized not in original_name_lookup:
            original_name_lookup[normalized] = cond.name
    for name in extra_condition_names:
        normalized = _normalize(name)
        if normalized and normalized not in original_name_lookup:
            original_name_lookup[normalized] = name.strip()

    unmatched_conditions = [original_name_lookup.get(name, name) for name in unmatched_names]

    return {
        "matches": matches,
        "matched_conditions": sorted(matched_condition_names, key=lambda v: v.lower()),
        "unmatched_conditions": unmatched_conditions,
    }

