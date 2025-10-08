"""Drug compatibility evaluation utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from sqlalchemy import or_, tuple_

from .. import db
from ..models import Drug, DrugInteraction


@dataclass
class CompatibilityIssue:
    drug1: str
    drug2: str
    severity: Optional[str]
    description: Optional[str]


@dataclass
class CompatibilityResult:
    compatible: bool
    issues: List[CompatibilityIssue]


def evaluate_compatibility(drugs: Iterable[Drug]) -> CompatibilityResult:
    """Return compatibility outcome for the supplied Drug rows."""
    drug_list = [drug for drug in drugs if getattr(drug, "id", None)]
    if len(drug_list) < 2:
        return CompatibilityResult(compatible=True, issues=[])

    pairs = []
    for idx, drug_a in enumerate(drug_list):
        for drug_b in drug_list[idx + 1:]:
            if not drug_a or not drug_b:
                continue
            a_id, b_id = sorted([drug_a.id, drug_b.id])
            pairs.append((a_id, b_id, drug_a, drug_b))

    if not pairs:
        return CompatibilityResult(compatible=True, issues=[])

    pair_ids = [(a, b) for (a, b, _, _) in pairs]
    interactions = (
        db.session.query(DrugInteraction)
        .filter(
            or_(
                tuple_(DrugInteraction.drug1_id, DrugInteraction.drug2_id).in_(pair_ids),
                tuple_(DrugInteraction.drug2_id, DrugInteraction.drug1_id).in_(pair_ids),
            )
        )
        .all()
    )

    issues: List[CompatibilityIssue] = []
    for interaction in interactions:
        for (a_id, b_id, drug_a, drug_b) in pairs:
            if {interaction.drug1_id, interaction.drug2_id} == {a_id, b_id}:
                issues.append(
                    CompatibilityIssue(
                        drug1=drug_a.name,
                        drug2=drug_b.name,
                        severity=interaction.severity,
                        description=interaction.description,
                    )
                )

    compatible = not issues
    return CompatibilityResult(compatible=compatible, issues=issues)
