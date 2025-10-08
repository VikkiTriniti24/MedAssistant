# health_app/routes/drug_check.py
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Tuple, Set
import re

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from .. import db
from ..models import Drug, Substance, DrugInteraction, DrugCheck, DrugCheckItem, InteractionResult, Profile
from ..utils.rate_limit import enforce_rate_limit
from ..services.ai_service import chat_json, build_drug_prompt, is_stub_mode
from ..services.drug_allergy_service import assess_allergy_conflicts
from ..services.drug_contraindication_service import assess_contraindications
from ..services.side_effect_service import collect_side_effect_warnings
from ..services.dosage_guidance_service import build_dosage_guidance
from ..services.drug_compatibility_service import evaluate_compatibility
from ..services.drug_compatibility_service import evaluate_compatibility

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
        normalized = _to_lc(r.name)
        by_name[normalized] = r
        for syn in _brand_synonyms(r):
            by_name.setdefault(syn, r)

    unrec = [n for n in lc_names if n not in by_name]

    if unrec:
        remaining = set(unrec)
        for missing in list(remaining):
            candidate_rows = Drug.query.filter(
                Drug.brand_synonyms.isnot(None),
                Drug.brand_synonyms.ilike(f"%{missing}%")
            ).all()
            for r in candidate_rows:
                for syn in _brand_synonyms(r):
                    if syn == missing and syn not in by_name:
                        by_name[syn] = r
                        remaining.discard(missing)
                        break
                if missing not in remaining:
                    break
        unrec = [n for n in lc_names if n not in by_name]
    return by_name, unrec

def _all_substance_names(drug: Drug) -> List[str]:
    # Substance.name auf lowercase
    return [_to_lc(s.name) for s in (drug.substances or [])]


def _brand_synonyms(drug: Drug) -> List[str]:
    raw = getattr(drug, "brand_synonyms", None)
    if not raw:
        return []
    parts = re.split(r"[,;\n]", raw)
    return [p.strip().lower() for p in parts if p and p.strip()]

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

def _ai_enhanced_drug_check(
    enriched_items: List[Dict[str, Any]],
    conditions: List[str],
    allergies: List[str],
    pregnant: Optional[bool],
    profile: Optional[Profile],
) -> Dict[str, Any]:
    """
    Enhanced drug checking using AI analysis for comprehensive interaction detection.
    """
    try:
        # Build patient profile for AI analysis (fall back to minimal context)
        profile_context = profile or type(
            "ProfileContext",
            (),
            {"age": None, "sex": None},
        )()

        # Prepare drug context for AI
        drug_context_list = []
        for item in enriched_items:
            drug_row = item["drug_row"]
            drug_info = {
                "name": drug_row.name,
                "dosage": item.get("dose", "unknown"),
                "frequency_per_day": item.get("freq_per_day", 1),
                "max_daily_dose": drug_row.max_daily_dose,
                "substances": [s.name for s in drug_row.substances] if drug_row.substances else []
            }
            drug_context_list.append(drug_info)
        
        # Call AI service for enhanced drug analysis
        current_app.logger.info(
            "Calling AI service for drug check (stub_mode: %s) | allergies=%s | conditions=%s",
            is_stub_mode(),
            allergies,
            conditions,
        )
        ai_prompt = build_drug_prompt(
            profile_context,
            allergies,
            conditions,
            drug_context_list,
            pregnant=pregnant,
        )
        ai_response = chat_json(ai_prompt)
        
        return {
            "ai_overdose_alerts": ai_response.get("overdose_alerts", []),
            "ai_interactions": ai_response.get("interactions", []),
            "ai_contraindications": ai_response.get("contraindications", []),
            "ai_side_effects": ai_response.get("side_effects", []),
            "ai_dosage_guidance": ai_response.get("dosage_guidance", []),
            "ai_mode": "stub" if is_stub_mode() else "live"
        }
        
    except Exception as exc:
        current_app.logger.exception("AI-enhanced drug check failed: %s", exc)
        return {
            "ai_overdose_alerts": [],
            "ai_interactions": [],
            "ai_contraindications": [],
            "ai_side_effects": [],
            "ai_dosage_guidance": [],
            "ai_mode": "error",
            "ai_error": str(exc)
        }

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

    claims = get_jwt()
    role = str(claims.get("role", "user")).lower()
    rl_response = enforce_rate_limit(
        "drug-check",
        identifier=str(user_id),
        role=role,
    )
    if rl_response is not None:
        return rl_response

    profile: Optional[Profile] = None
    if str(user_id).isdigit():
        profile = Profile.query.filter_by(user_id=int(user_id)).first()

    err = _validate_payload(data)
    if err:
        return jsonify({"success": False, "errors": [err]}), HTTPStatus.BAD_REQUEST

    # Eingaben
    in_drugs: List[Dict[str, Any]] = data["drugs"]
    manual_conditions_raw: List[str] = []
    for value in data.get("conditions", []) or []:
        if isinstance(value, str) and value.strip():
            manual_conditions_raw.append(value.strip())

    manual_allergies_raw: List[str] = []
    for value in data.get("allergies", []) or []:
        if isinstance(value, str) and value.strip():
            manual_allergies_raw.append(value.strip())

    allergies: List[str] = [*{_to_lc(a) for a in manual_allergies_raw}]

    pregnant_value = data.get("pregnant")
    pregnant: Optional[bool]
    if isinstance(pregnant_value, bool):
        pregnant = pregnant_value
    else:
        pregnant = None

    profile_conditions = list(getattr(profile, "conditions", []) or [])

    condition_names_for_analysis = manual_conditions_raw + [
        cond.name for cond in profile_conditions if getattr(cond, "name", None)
    ]

    def _dedupe_preserve_case(items: Iterable[str]) -> List[str]:
        seen: Set[str] = set()
        result: List[str] = []
        for item in items:
            normalized = _to_lc(item)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(item)
        return result

    conditions_for_summary = _dedupe_preserve_case(condition_names_for_analysis)
    allergies_for_prompt = _dedupe_preserve_case(
        manual_allergies_raw
        + [
            a.name
            for a in getattr(profile, "allergies", []) or []
            if getattr(a, "name", None)
        ]
    )

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

    # Traditional database checks
    overdose = _check_overdose(enriched)
    allergy_assessment = assess_allergy_conflicts(found_rows, allergies)
    allergy_conf = [
        {
            "drug": entry["drug"],
            "allergens": entry.get("allergens", []),
            "notes": entry.get("notes", "Potential allergy conflict with drug name or its substances."),
            "matched_names": entry.get("matched_names", []),
            "matched_substances": entry.get("matched_substances", []),
        }
        for entry in allergy_assessment["conflicts"]
    ]
    interactions_raw = _check_pairwise_interactions(found_rows)

    contraindication_assessment = assess_contraindications(
        found_rows,
        profile_conditions,
        condition_names_for_analysis,
    )
    contraindication_matches = [
        {
            "drug": entry.get("drug"),
            "condition": entry.get("condition"),
            "notes": entry.get("notes"),
            "condition_id": entry.get("condition_id"),
            "drug_id": entry.get("drug_id"),
            "source": "database",
        }
        for entry in contraindication_assessment["matches"]
    ]

    def _format_interaction(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pair = entry.get("pair") or []
        drug1 = entry.get("drug1")
        drug2 = entry.get("drug2")
        if (not drug1 or not drug2) and isinstance(pair, list) and len(pair) == 2:
            drug1, drug2 = pair[0], pair[1]
        if not drug1 or not drug2:
            return None
        return {
            "drug1": drug1,
            "drug2": drug2,
            "severity": entry.get("severity"),
            "description": entry.get("description", ""),
        }

    db_interactions = [
        formatted for formatted in (
            _format_interaction(entry) for entry in interactions_raw
        ) if formatted
    ]

    # AI-enhanced checks
    ai_results = _ai_enhanced_drug_check(
        enriched,
        conditions_for_summary,
        allergies_for_prompt,
        pregnant,
        profile,
    )

    side_effects = collect_side_effect_warnings(found_rows)
    dosage_guidance = build_dosage_guidance(enriched)
    compatibility = evaluate_compatibility(found_rows)
    
    # Combine results
    ai_interactions = [
        formatted for formatted in (
            _format_interaction(entry)
            for entry in ai_results.get("ai_interactions", [])
        ) if formatted
    ]
    all_interactions = db_interactions + ai_interactions
    all_overdose_alerts = overdose + ai_results["ai_overdose_alerts"]
    all_contraindications = contraindication_matches + ai_results["ai_contraindications"]
    all_dosage_guidance = dosage_guidance + ai_results.get("ai_dosage_guidance", [])
    all_side_effects = side_effects["warnings"] + ai_results.get("ai_side_effects", [])

    # Calculate severity counts
    major = sum(1 for x in all_interactions if _to_lc(x.get("severity")) in {"major", "severe"})
    moderate = sum(1 for x in all_interactions if _to_lc(x.get("severity")) in {"moderate"})

    safe = (
        compatibility.compatible
        and major == 0
        and not all_overdose_alerts
        and not allergy_conf
        and not all_contraindications
        and not all_side_effects
    )

    resp = {
        "input_echo": {
            "user_id": user_id,
            "drugs": in_drugs,
            "conditions": conditions_for_summary,
            "allergies": allergies,
            "pregnant": pregnant,
        },
        "summary": {
            "safe_to_proceed": safe,
            "major_issue_count": major,
            "moderate_issue_count": moderate,
            "total_issues": len(all_interactions) + len(all_overdose_alerts) + len(allergy_conf) + len(all_contraindications) + len(all_side_effects) + (0 if compatibility.compatible else len(compatibility.issues)),
            "notes": ([] if safe else ["Issues found — review details below."]),
        },
        "overdose_alerts": all_overdose_alerts,
        "interactions": all_interactions,
        "contraindications": all_contraindications,
        "side_effect_warnings": all_side_effects,
        "side_effect_summary": side_effects["effects_by_drug"],
        "dosage_guidance": all_dosage_guidance,
        "compatibility": {
            "compatible": compatibility.compatible,
            "issues": [
                {
                    "drug1": issue.drug1,
                    "drug2": issue.drug2,
                    "severity": issue.severity,
                    "description": issue.description,
                }
                for issue in compatibility.issues
            ],
        },
        "allergy_conflicts": allergy_conf,
        "allergy_analysis": {
            "matched_allergies": allergy_assessment["matched_allergies"],
            "unmatched_allergies": allergy_assessment["unmatched_allergies"],
        },
        "contraindication_analysis": {
            "matched_conditions": contraindication_assessment["matched_conditions"],
            "unmatched_conditions": contraindication_assessment["unmatched_conditions"],
        },
        "ai_analysis": {
            "mode": ai_results["ai_mode"],
            "overdose_alerts": ai_results["ai_overdose_alerts"],
            "interactions": ai_interactions,
            "contraindications": ai_results["ai_contraindications"],
            "side_effects": ai_results.get("ai_side_effects", []),
            "dosage_guidance": ai_results.get("ai_dosage_guidance", []),
            "error": ai_results.get("ai_error")
        },
        "normalization": {
            "mapping": {e["name"].lower(): e["drug_id"] for e in enriched},
            "unrecognized": unrecognized,
        },
    }

    # Persist a DrugCheck history entry (best-effort)
    try:
        # Resolve profile id from user id
        if profile:
            check = DrugCheck(profile_id=profile.id)
            db.session.add(check)
            db.session.flush()  # get id

            # Store items for recognized drugs
            for it in enriched:
                db.session.add(DrugCheckItem(drug_check_id=check.id, drug_id=it["drug_id"]))

            # Store pairwise interaction results when both drugs recognized
            # Build name->id map from enriched for quick lookup
            nm_to_id = {it["name"].lower(): it["drug_id"] for it in enriched}
            for inter in all_interactions:
                drug1_name = inter.get("drug1")
                drug2_name = inter.get("drug2")
                if not drug1_name or not drug2_name:
                    continue
                d1 = nm_to_id.get(str(drug1_name).lower())
                d2 = nm_to_id.get(str(drug2_name).lower())
                if not d1 or not d2:
                    continue
                db.session.add(InteractionResult(
                    drug_check_id=check.id,
                    drug1_id=d1,
                    drug2_id=d2,
                    severity=(inter.get("severity") or None),
                    description=(inter.get("description") or None),
                ))

            db.session.commit()
    except Exception as _exc:
        current_app.logger.warning("Failed to persist drug check history: %s", _exc)
        db.session.rollback()

    return jsonify({"success": True, "data": resp, "errors": []}), HTTPStatus.OK


@drug_check_bp.post("/allergy-check/")
@jwt_required()
def run_drug_allergy_check():
    """Lightweight endpoint to assess potential drug allergy conflicts."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    claims = get_jwt()
    role = str(claims.get("role", "user")).lower()
    rl_response = enforce_rate_limit(
        "drug-allergy-check",
        identifier=str(user_id),
        role=role,
    )
    if rl_response is not None:
        return rl_response

    drugs_input = data.get("drugs")
    if not isinstance(drugs_input, list) or not drugs_input:
        return jsonify({"success": False, "errors": ["`drugs` must be a non-empty list"]}), HTTPStatus.BAD_REQUEST

    normalized_names: List[str] = []
    for idx, entry in enumerate(drugs_input):
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            name = entry.get("name")
        else:
            return jsonify({"success": False, "errors": [f"drugs[{idx}] must be a string or object with 'name'"]}), HTTPStatus.BAD_REQUEST
        if not _to_lc(name):
            return jsonify({"success": False, "errors": [f"drugs[{idx}] name is required"]}), HTTPStatus.BAD_REQUEST
        normalized_names.append(str(name))

    allergies_input = data.get("allergies", [])
    if allergies_input is None:
        allergies_input = []
    if not isinstance(allergies_input, list):
        return jsonify({"success": False, "errors": ["`allergies` must be a list when provided"]}), HTTPStatus.BAD_REQUEST

    for idx, entry in enumerate(allergies_input):
        if not isinstance(entry, str):
            return jsonify({"success": False, "errors": [f"allergies[{idx}] must be a string"]}), HTTPStatus.BAD_REQUEST

    include_profile = bool(data.get("include_profile_allergies", False))

    combined_allergies: List[str] = []
    seen_allergies: Set[str] = set()

    def _append_allergies(source: Iterable[str]) -> None:
        for value in source:
            normalized = _to_lc(value)
            if not normalized or normalized in seen_allergies:
                continue
            seen_allergies.add(normalized)
            combined_allergies.append(value.strip())

    _append_allergies(allergies_input)

    if include_profile and str(user_id).isdigit():
        profile = Profile.query.filter_by(user_id=int(user_id)).first()
        if profile:
            _append_allergies(a.name for a in profile.allergies)

    name_map, unrecognized = _fetch_drugs_map(normalized_names)

    recognized_rows: List[Drug] = []
    for name in normalized_names:
        row = name_map.get(_to_lc(name))
        if row:
            recognized_rows.append(row)

    assessment = assess_allergy_conflicts(recognized_rows, combined_allergies)

    conflicts_by_name = {conf["drug"]: conf for conf in assessment["conflicts"]}

    results: List[Dict[str, Any]] = []
    for row in recognized_rows:
        conflict_entry = conflicts_by_name.get(row.name)
        result = {
            "drug": row.name,
            "drug_id": row.id,
            "substances": [s.name for s in row.substances] if row.substances else [],
            "conflict": conflict_entry is not None,
        }
        if conflict_entry:
            result.update({
                "allergens": conflict_entry.get("allergens", []),
                "matched_names": conflict_entry.get("matched_names", []),
                "matched_substances": conflict_entry.get("matched_substances", []),
                "notes": conflict_entry.get("notes"),
            })
        results.append(result)

    response_payload = {
        "input": {
            "drugs": normalized_names,
            "allergies": combined_allergies,
            "include_profile_allergies": include_profile,
            "user_id": user_id,
        },
        "summary": {
            "total_drugs": len(normalized_names),
            "recognized_drugs": len(recognized_rows),
            "conflict_count": len(assessment["conflicts"]),
            "matched_allergy_count": len(assessment["matched_allergies"]),
        },
        "results": results,
        "unrecognized_drugs": unrecognized,
        "matched_allergies": assessment["matched_allergies"],
        "unmatched_allergies": assessment["unmatched_allergies"],
    }

    return jsonify({"success": True, "data": response_payload, "errors": []}), HTTPStatus.OK
