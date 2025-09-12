# health_app/services/medication_service.py
from typing import Iterable, List, Tuple, TypedDict, Optional, Any

from ..models import ProfileMedication, Drug  # type: ignore[attr-defined]


class SubstanceOut(TypedDict):
    name: str
    type: str  # normalized string, e.g. "active" | "help" | "unknown"


class DrugContextItem(TypedDict):
    id: int
    name: str
    dosage: Optional[str]
    max_daily_dose: Optional[float]
    substances: List[SubstanceOut]


__all__ = ["build_drug_context", "DrugContextItem", "SubstanceOut"]


def _normalize_substance_type(t: Any) -> str:
    """
    Normalize Substance.type to a plain lowercase string.
    Supports Enum-like `.value`, strings, or None.
    """
    if hasattr(t, "value"):
        t = getattr(t, "value", None)
    if t is None:
        return "unknown"
    return str(t).strip().lower() or "unknown"


def build_drug_context(
    meds: Iterable[Tuple[ProfileMedication, Drug]]
) -> List[DrugContextItem]:
    """
    Transform joined (ProfileMedication, Drug) rows into a JSON-friendly list.

    Input:
        meds: iterable of (ProfileMedication pm, Drug drug)
              Ensure you eager-load substances to avoid N+1 queries:
              e.g., selectinload(Drug.substances) in your repository layer.

    Output (sorted by drug.name case-insensitively):
        [
          {
            "id": 1,
            "name": "Ibuprofen",
            "dosage": "400 mg",
            "max_daily_dose": 1200.0,
            "substances": [{"name": "Ibuprofen", "type": "active"}]
          },
          ...
        ]
    """
    ctx: List[DrugContextItem] = []
    seen_pairs = set()  # avoid duplicates if the same (pm, drug) tuple appears

    for pm, drug in meds:
        # Deduplicate by (pm.id, drug.id) if both exist; otherwise by id fallback
        key = (getattr(pm, "id", id(pm)), getattr(drug, "id", id(drug)))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)

        # Safe attribute access with fallbacks
        drug_id = getattr(drug, "id", None)
        drug_name = getattr(drug, "name", None)
        dosage = getattr(pm, "dosage", None)
        max_daily = getattr(drug, "max_daily_dose", None)

        # Build substances list defensively & deduplicate by (name,type)
        subs = getattr(drug, "substances", None) or []
        subs_out: List[SubstanceOut] = []
        seen_subs = set()
        for s in subs:
            s_name = str(getattr(s, "name", "") or "").strip()
            s_type = _normalize_substance_type(getattr(s, "type", None))
            sub_key = (s_name.casefold(), s_type)
            if sub_key in seen_subs:
                continue
            seen_subs.add(sub_key)
            if s_name:  # skip empty names
                subs_out.append({"name": s_name, "type": s_type})

        item: DrugContextItem = {
            "id": int(drug_id) if drug_id is not None else -1,
            "name": str(drug_name) if drug_name is not None else "",
            "dosage": str(dosage) if dosage is not None else None,
            "max_daily_dose": float(max_daily) if max_daily is not None else None,
            "substances": subs_out,
        }
        ctx.append(item)

    # Stable, case-insensitive sort by name
    ctx.sort(key=lambda x: (x["name"] or "").casefold())
    return ctx
