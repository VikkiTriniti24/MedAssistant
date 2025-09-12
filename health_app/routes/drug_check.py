# health_app/routes/drug_check.py
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple
import re

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from .. import db
from ..models import Drug, Substance, DrugInteraction

drug_check_bp = Blueprint("drug_check", __name__)

# -------- Helpers ------------------------------------------------------------

_NUM_MG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mg\b", re.IGNORECASE)

def _to_lc(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _parse_mg(dose_text: Optional[str]) -> Optional[float]:
    """
    Extract 'mg' from strings like '400 mg', '400mg', '400 MG'.
    Returns float mg or None if not parseable.
    """
    if not dose_text:
        return None
    m = _NUM_MG_RE.search(dose_text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None

def _validate_payload(data: Dict[str, Any]) -> Optional[str]:
    """
    Expect JSON:
    {
      "drugs": [ {"name": "ibuprofen", "dose": "400 mg", "freq_per_day": 3}, ... ],
      "conditions": ["hypertension"],    # optional
      "allergies":  ["ibuprofen"],       # optional (gegen Wirkstoffnamen)
      "pregnant": false                  # optional
    }
    """
    if not isinstance(data, dict):
        return "body must be a JSON object"

    drugs = data.get("drugs")
    if not isinstance(drugs, list) or not drugs:
        return "`drugs` must be a non-empty list"

    for i, d in enumerate(drugs):
        if not isinstance(d, dict):
            return f"drugs[{i}] must be an object"
        if not _to_lc(d.get("name")):
            return f"drugs[{i}].name is required"
        # Dose/Frequenz sind optional, aber wenn gesetzt, prüfen wir die Types
        if d.get("freq_per_day") is not None and not isinstance(d.get("freq_per_day"), int):
            return f"drugs[{i}].freq_per_day must be integer when provided"

    if "conditions" in data and not isinstance(data["conditions"], list):
        return "`conditions` must be a list when provided"
    if "allergies" in data and not isinstance(data["allergies"], list):
        return "`allergies` must be a list when provided"
    if "pregnant" in data and not isinstance(data["pregnant"], bool):
        return "`pregnant` must be a boolean when provided"

    return None

def _fetch_drugs_map(names: List[str]) -> Tuple[Dict[str, Drug], List[str]]:
    """
    Look up Drug rows by normalized (lowercase) name.
    Returns (mapping lc_name -> Drug, unrecognized list).
    """
    lc_names = [_to_lc(n) for n in names]
    rows = Drug.query.filter(Drug.name.in_(names) | Drug.name.in_(lc_names)).all()
    by_name = {}
    for r in rows:
        by_name[_to_lc(r.name)] = r
    unrec = [n for n in lc_names if n not in by_name]
    return by_name, unrec

def _all_substance_names(drug: Drug) -> List[str]:
    # Substance.name auf lowercase
    return [_to_lc(s.name) for s in (drug.substances or [])]

# -------- Core evaluation ----------------------------------------------------

def _check_overdose(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sehr einfache Logik:
    - wenn dose parsebar (mg) und freq_per_day bekannt:
        daily_mg = mg * freq_per_day
      Vergleiche mit drug.max_daily_dose (mg)
    """
    results: List[Dict[str, Any]] = []
    for it in items:
        drug: Drug = it["drug_row"]
        mg = _parse_mg(it.get("dose"))
        freq = it.get("freq_per_day") or 1
        if mg is None or drug.max_daily_dose is None:
            continue
        daily_mg = mg * max(freq, 1)
        if float(daily_mg) > float(drug.max_daily_dose):
            results.append({
                "drug": drug.name,
                "dosage": it.get("dose"),
                "freq_per_day": freq,
                "daily_mg": daily_mg,
                "max_daily_dose": float(drug.max_daily_dose),
                "alert": True,
                "reason": "daily_mg exceeds max_daily_dose"
            })
    return results

def _check_allergy_conflicts(items: List[Dict[str, Any]], allergies_lc: List[str]) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    if not allergies_lc:
        return conflicts
    for it in items:
        drug: Drug = it["drug_row"]
        subs = _all_substance_names(drug)
        hits = sorted(set(subs).intersection(allergies_lc))
        if hits:
            conflicts.append({
                "drug": drug.name,
                "allergens": hits,
                "notes": "Potential allergy conflict with active/helper substances."
            })
    return conflicts

def _check_pairwise_interactions(drug_rows: List[Drug]) -> List[Dict[str, Any]]:
    """
    Sucht in DrugInteraction sowohl (a,b) als auch (b,a).
    """
    results: List[Dict[str, Any]] = []
    n = len(drug_rows)
    if n < 2:
        return results

    # Build quick index by (min_id,max_id)
    id_map = {d.id: d for d in drug_rows}
    pairs = []
    seen = set()
    for i in range(n):
        for j in range(i + 1, n):
            a, b = drug_rows[i], drug_rows[j]
            key = (min(a.id, b.id), max(a.id, b.id))
            if key not in seen:
                seen.add(key)
                pairs.append((a.id, b.id))

    if not pairs:
        return results

    # Query interactions where (drug1_id, drug2_id) match in any order.
    q = db.session.query(DrugInteraction).filter(
        db.or_(
            db.tuple_(DrugInteraction.drug1_id, DrugInteraction.drug2_id).in_(pairs),
            db.tuple_(DrugInteraction.drug2_id, DrugInteraction.drug1_id).in_(pairs),
        )
    )
    for row in q.all():
        a = id_map.get(row.drug1_id)
        b = id_map.get(row.drug2_id)
        if not a or not b:
            # Fallback (shouldn't happen)
            continue
        results.append({
            "pair": [a.name, b.name],
            "severity": row.severity,
            "description": row.description or ""
        })
    return results

# -------- Route --------------------------------------------------------------

@drug_check_bp.post("/")
@jwt_required()
def run_drug_check():
    """
    Führt einen einfachen Wechselwirkungs-/Sicherheitscheck durch.
    Nutzt:
      - Drugs / Substances aus DB
      - DrugInteraction (paarweise)
      - sehr einfache Überdosierungslogik (mg * freq_per_day > max_daily_dose)
      - Allergie-Check gegen Substanznamen
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    err = _validate_payload(data)
    if err:
        return jsonify({"success": False, "errors": [err]}), HTTPStatus.BAD_REQUEST

    # Eingaben
    in_drugs: List[Dict[str, Any]] = data["drugs"]
    conditions: List[str] = [*{_to_lc(c) for c in data.get("conditions", [])}]
    allergies: List[str] = [*{_to_lc(a) for a in data.get("allergies", [])}]
    pregnant: bool = bool(data.get("pregnant", False))

    # DB-Lookups
    names = [d.get("name") for d in in_drugs]
    name_map, unrecognized = _fetch_drugs_map(names)

    # Items anreichern (Dose/Frequenz etc.)
    enriched: List[Dict[str, Any]] = []
    found_rows: List[Drug] = []
    for d in in_drugs:
        key = _to_lc(d.get("name"))
        row = name_map.get(key)
        if not row:
            continue
        item = {
            "name": row.name,
            "drug_id": row.id,
            "dose": d.get("dose"),                    # z.B. "400 mg"
            "freq_per_day": d.get("freq_per_day"),    # z.B. 3
            "drug_row": row,
        }
        enriched.append(item)
        found_rows.append(row)

    # Checks
    overdose = _check_overdose(enriched)
    allergy_conf = _check_allergy_conflicts(enriched, allergies)
    interactions = _check_pairwise_interactions(found_rows)

    major = sum(1 for x in interactions if _to_lc(x.get("severity")) in {"major", "severe"})
    moderate = sum(1 for x in interactions if _to_lc(x.get("severity")) in {"moderate"})

    safe = (major == 0 and not overdose and not allergy_conf)

    resp = {
        "input_echo": {
            "user_id": user_id,
            "drugs": in_drugs,
            "conditions": conditions,
            "allergies": allergies,
            "pregnant": pregnant,
        },
        "summary": {
            "safe_to_proceed": safe,
            "major_issue_count": major,
            "moderate_issue_count": moderate,
            "notes": ([] if safe else ["Issues found — review details below."]),
        },
        "overdose_alerts": overdose,
        "interactions": interactions,
        "contraindications": [],   # Für später (separater Master-Katalog nötig)
        "allergy_conflicts": allergy_conf,
        "normalization": {
            "mapping": {e["name"].lower(): e["drug_id"] for e in enriched},
            "unrecognized": unrecognized,
        },
    }

    return jsonify({"success": True, "data": resp, "errors": []}), HTTPStatus.OK
