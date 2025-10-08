# health_app/routes/health_check.py
from http import HTTPStatus
from typing import Any, Dict, Optional, List

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from health_app.services.ai_service import chat_json, build_health_prompt, is_stub_mode
from health_app.models import Profile, SymptomEntry, Diagnosis, RiskEvaluation, SymptomSeverity, EmergencyContact
from health_app.utils.severity import evaluate_symptom_severity
from health_app import db
from health_app.utils.rate_limit import enforce_rate_limit

health_check_bp = Blueprint("health_check", __name__)

_BODY_SYSTEM_KEYWORDS = {
    "cardiovascular": {"chest", "heart", "palpitation", "pressure", "angina", "faint"},
    "respiratory": {"cough", "breath", "wheez", "lung", "dyspnea", "shortness of breath", "throat"},
    "neurological": {"headache", "dizziness", "vision", "numb", "weakness", "confusion", "seizure"},
    "gastrointestinal": {"stomach", "nausea", "vomit", "diarrhea", "abdomen", "abdominal", "cramp"},
    "musculoskeletal": {"joint", "muscle", "back", "sprain", "strain", "bone"},
    "dermatological": {"rash", "skin", "itch", "lesion"},
    "endocrine": {"thirst", "urination", "fatigue", "weight", "sweat"},
    "urinary": {"urine", "urinary", "dysuria", "frequency", "kidney"},
}

def _validate_payload(data: Dict[str, Any]) -> Optional[str]:
    """
    Expected JSON:
    {
      "symptoms": "free text",                 # required (string)
      "age": 34,                               # optional (int)
      "sex": "female|male|other|unknown",      # optional
      "duration": "3 days",                    # optional (string)
      "onset": "sudden|gradual|unknown",       # optional
      "vitals": { "temp_c": 38.2, "hr": 110 }, # optional (numbers)
      "pregnant": false,                       # optional (bool)
      "medications": ["ibuprofen"],            # optional (list[str])
      "conditions": ["hypertension"],          # optional (list[str])
      "allergies": ["penicillin"]              # optional (list[str])
    }
    """
    if not isinstance(data, dict):
        return "body must be a JSON object"

    s = data.get("symptoms", "")
    if not isinstance(s, str) or not s.strip():
        return "`symptoms` is required and must be a non-empty string"

    if "age" in data:
        try:
            age = int(data["age"])
            if age < 0 or age > 130:
                return "`age` out of range"
        except (TypeError, ValueError):
            return "`age` must be an integer"

    if "sex" in data and str(data["sex"]).lower() not in {"female", "male", "other", "unknown"}:
        return "`sex` must be one of: female, male, other, unknown"

    if "pregnant" in data and not isinstance(data["pregnant"], bool):
        return "`pregnant` must be a boolean"

    if "vitals" in data and not isinstance(data["vitals"], dict):
        return "`vitals` must be an object when provided"

    if "onset" in data and str(data["onset"]).lower() not in {"sudden", "gradual", "unknown"}:
        return "`onset` must be one of: sudden, gradual, unknown"

    for list_key in ("medications", "conditions", "allergies"):
        if list_key in data and not isinstance(data[list_key], list):
            return f"`{list_key}` must be a list when provided"

    return None


@health_check_bp.post("/")
@jwt_required()
def health_check():
    """
    Symptom checker (placeholder).
    Validates input and returns a structured stub you can replace with real AI.
    """
    # Identity must be a string in JWT; cast to int for internal use
    raw_identity = get_jwt_identity()
    try:
        user_id = int(raw_identity)
    except (TypeError, ValueError):
        return jsonify({"success": False, "errors": ["invalid token subject"]}), HTTPStatus.UNAUTHORIZED

    data = request.get_json(silent=True) or {}

    claims = get_jwt()
    role = str(claims.get("role", "user")).lower()
    rl_response = enforce_rate_limit(
        "health-check",
        identifier=str(user_id),
        role=role,
    )
    if rl_response is not None:
        return rl_response

    error = _validate_payload(data)
    if error:
        return jsonify({"success": False, "errors": [error]}), HTTPStatus.BAD_REQUEST

    symptoms_text = data["symptoms"].strip()

    try:
        # Build patient profile for AI analysis
        profile_stub = type('Profile', (), {
            'age': data.get("age", "unknown"),
            'sex': data.get("sex", "unknown")
        })()
        
        # Extract patient data
        allergies = data.get("allergies", [])
        conditions = data.get("conditions", [])
        medications = data.get("medications", [])
        
        # Build comprehensive symptoms text
        symptoms_parts = [symptoms_text]
        if data.get("duration"):
            symptoms_parts.append(f"Duration: {data['duration']}")
        if data.get("onset"):
            symptoms_parts.append(f"Onset: {data['onset']}")
        if data.get("vitals"):
            vitals_text = ", ".join([f"{k}: {v}" for k, v in data["vitals"].items()])
            symptoms_parts.append(f"Vitals: {vitals_text}")
        if data.get("pregnant"):
            symptoms_parts.append("Patient is pregnant")
        if medications:
            meds_list = ", ".join(map(str, medications))
            symptoms_parts.append(f"Current medications: {meds_list}")
        
        symptoms_text_full = "\n".join(symptoms_parts)
        
        # Call AI service for health analysis
        current_app.logger.info(f"Calling AI service for health check (stub_mode: {is_stub_mode()})")
        ai_prompt = build_health_prompt(profile_stub, allergies, conditions, symptoms_text_full)
        ai_response = chat_json(ai_prompt)
        
        # Transform AI response to our API format
        diagnoses = ai_response.get("diagnoses", [])
        risk_eval = ai_response.get("risk_evaluation", {})
        recommendations = ai_response.get("recommendations", [])
        differential = ai_response.get("differential_diagnosis", [])
        
        result = {
            "summary": {
                "risk_level": risk_eval.get("risk_level", "medium"),
                "urgency": risk_eval.get("urgency", "see-doctor"),
                "notes": recommendations if recommendations else ["AI analysis completed"]
            },
            "diagnoses": [
                {
                    "condition": diag.get("condition", "Unknown condition"),
                    "probability": float(diag.get("probability", 0.5)),
                    "triage": diag.get("triage", "medium")
                }
                for diag in diagnoses
            ],
            "red_flags": [],  # Could be enhanced to extract from AI response
            "follow_up": {
                "self_care_advice": recommendations[:3] if recommendations else [],
                "when_to_seek_help": recommendations[3:] if len(recommendations) > 3 else []
            },
            "differential_diagnosis": [
                {
                    "condition": item.get("condition", "Unknown"),
                    "likelihood": float(item.get("likelihood", 0.0)),
                    "rationale": item.get("rationale", "")
                }
                for item in differential
                if item
            ],
            "input_echo": {
                "user_id": user_id,
                "symptoms": symptoms_text,
                "age": data.get("age"),
                "sex": (str(data.get("sex", "unknown")).lower()),
                "duration": data.get("duration"),
                "onset": str(data.get("onset", "unknown")).lower(),
                "vitals": data.get("vitals", {}),
                "pregnant": data.get("pregnant", False),
                "medications": medications,
                "conditions": conditions,
                "allergies": allergies
            },
            "ai_mode": "stub" if is_stub_mode() else "live"
        }

        # Derive a severity score so clients can compare cases consistently.
        severity_data = evaluate_symptom_severity(
            data,
            ai_response,
            symptoms_text=symptoms_text_full,
        )
        result["summary"]["severity"] = severity_data

        body_systems = _detect_body_systems(symptoms_text_full, diagnoses)
        result["body_systems"] = body_systems
        severity_data["body_systems"] = [system["system"] for system in body_systems]
        for system in body_systems:
            tag = f"system:{system['system']}"
            if tag not in severity_data["factors"]:
                severity_data["factors"].append(tag)

        db_profile = Profile.query.filter_by(user_id=user_id).first()
        emergency_contact_payload = None
        if db_profile:
            contact = EmergencyContact.query.filter_by(profile_id=db_profile.id).order_by(
                EmergencyContact.is_primary.desc(), EmergencyContact.created_at.asc()
            ).first()
            if contact:
                emergency_contact_payload = {
                    "name": contact.name,
                    "relationship": contact.relationship,
                    "phone": contact.phone,
                    "email": contact.email,
                    "is_primary": bool(contact.is_primary),
                }

        result["emergency_contact"] = emergency_contact_payload

        # Persist health check history (best-effort; do not fail API on DB errors)
        try:
            if db_profile:
                entry = SymptomEntry(profile_id=db_profile.id, symptoms=symptoms_text_full)
                db.session.add(entry)
                db.session.flush()  # get entry.id

                # Store diagnoses
                for diag in result.get("diagnoses", [])[:10]:  # cap to 10
                    db.session.add(Diagnosis(
                        symptom_entry_id=entry.id,
                        condition_name=str(diag.get("condition", "Unknown"))[:255],
                        probability=float(diag.get("probability", 0.0)),
                        triage_level=str(diag.get("triage", "medium"))
                    ))

                # Store risk evaluation
                db.session.add(RiskEvaluation(
                    symptom_entry_id=entry.id,
                    risk_level=str(result["summary"].get("risk_level", "medium")),
                    urgency=str(result["summary"].get("urgency", "see-doctor"))
                ))

                # Store severity snapshot for trend tracking
                try:
                    db.session.add(SymptomSeverity(
                        symptom_entry_id=entry.id,
                        score=int(severity_data.get("score", 0)),
                        level=str(severity_data.get("level", "low")),
                        factors=list(severity_data.get("factors", [])),
                    ))
                except Exception as severity_exc:
                    current_app.logger.warning("Failed to persist severity snapshot: %s", severity_exc)

                db.session.commit()
        except Exception as _exc:
            current_app.logger.warning("Failed to persist health check history: %s", _exc)
            db.session.rollback()

        return jsonify({"success": True, "data": result, "errors": []}), HTTPStatus.OK

    except Exception as exc:
        current_app.logger.exception("health_check failed for user %s: %s", user_id, exc)
        return jsonify({"success": False, "errors": ["internal error"]}), HTTPStatus.INTERNAL_SERVER_ERROR
def _detect_body_systems(symptoms_text: str, diagnoses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    systems: List[Dict[str, Any]] = []
    text = symptoms_text.lower()
    diag_text = " ".join(str(d.get("condition", "")).lower() for d in diagnoses)

    for system, keywords in _BODY_SYSTEM_KEYWORDS.items():
        matches = []
        for kw in keywords:
            if kw in text or kw in diag_text:
                matches.append(kw)

        if matches:
            confidence = min(1.0, len(matches) / 3.0)
            systems.append(
                {
                    "system": system,
                    "confidence": round(confidence, 2),
                    "matches": sorted(set(matches)),
                }
            )

    return systems
