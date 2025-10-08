"""Side effect warning utilities."""
from __future__ import annotations

from typing import Dict, Iterable, List


from .. import db
from ..models import Drug, SideEffect


def collect_side_effect_warnings(drugs: Iterable[Drug]) -> Dict[str, List[Dict[str, str]]]:
    """Aggregate side-effect warnings for the supplied drugs."""
    drug_ids = [drug.id for drug in drugs if getattr(drug, "id", None) is not None]
    if not drug_ids:
        return {
            "warnings": [],
            "effects_by_drug": {},
        }

    query = (
        db.session.query(SideEffect)
        .filter(SideEffect.drug_id.in_(drug_ids))
        .order_by(SideEffect.severity.desc(), SideEffect.category.asc())
    )

    warnings: List[Dict[str, str]] = []
    effects_by_drug: Dict[str, List[Dict[str, str]]] = {}

    for effect in query.all():
        drug_name = getattr(effect.drug, "name", "") if effect.drug else ""
        entry = {
            "drug": drug_name,
            "drug_id": effect.drug_id,
            "category": effect.category,
            "severity": effect.severity,
            "description": effect.description,
        }
        warnings.append(entry)
        effects_by_drug.setdefault(drug_name, []).append(entry)

    return {
        "warnings": warnings,
        "effects_by_drug": effects_by_drug,
    }

