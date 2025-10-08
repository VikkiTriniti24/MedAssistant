"""Utilities for matching brand and generic drug names."""
from __future__ import annotations

from typing import Dict, Iterable, Optional

from ..models import Drug


def build_brand_index(drugs: Iterable[Drug]) -> Dict[str, Drug]:
    index: Dict[str, Drug] = {}
    for drug in drugs:
        names = [drug.name]
        if getattr(drug, "brand_synonyms", None):
            names.extend(s.strip() for s in drug.brand_synonyms if s)
        for name in names:
            key = name.strip().lower()
            if key:
                index.setdefault(key, drug)
    return index


def find_drug_by_name(name: str) -> Optional[Drug]:
    normalized = (name or "").strip().lower()
    if not normalized:
        return None
    drug = Drug.query.filter(Drug.name == normalized).first()
    if drug:
        return drug
    return Drug.query.filter(Drug.brand_synonyms.contains(normalized)).first()

