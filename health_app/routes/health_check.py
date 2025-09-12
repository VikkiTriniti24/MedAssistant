# health_app/routes/health_check.py
from http import HTTPStatus
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

health_check_bp = Blueprint("health_check", __name__)

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
      "conditions": ["hypertension"]           # optional (list[str])
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

    for list_key in ("medications", "conditions"):
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

    error = _validate_payload(data)
    if error:
        return jsonify({"success": False, "errors": [error]}), HTTPStatus.BAD_REQUEST

    symptoms_text = data["symptoms"].strip()

    try:
        # TODO: call your AI layer here (e.g., ai_service.triage(symptoms_text, context=data))
        result = {
            "summary": {
                "risk_level": "medium",           # enum: low|medium|high|critical
                "urgency": "see-doctor",          # enum: self-care|see-doctor|urgent-care|emergency
                "notes": ["Placeholder result — no model inference yet."]
            },
            "diagnoses": [
                {
                    "condition": "Example condition",
                    "probability": 0.5,           # 0..1 (model-calibrated later)
                    "triage": "medium"
                }
            ],
            "red_flags": [],                       # e.g., ["chest pain", "shortness of breath"]
            "follow_up": {
                "self_care_advice": [],
                "when_to_seek_help": []
            },
            "input_echo": {
                "user_id": user_id,
                "symptoms": symptoms_text,
                "age": data.get("age"),
                "sex": (str(data.get("sex", "unknown")).lower()),
                "duration": data.get("duration"),
                "onset": str(data.get("onset", "unknown")).lower(),
                "vitals": data.get("vitals", {}),
                "pregnant": data.get("pregnant", False),
                "medications": data.get("medications", []),
                "conditions": data.get("conditions", [])
            }
        }

        return jsonify({"success": True, "data": result, "errors": []}), HTTPStatus.OK

    except Exception as exc:
        current_app.logger.exception("health_check failed for user %s: %s", user_id, exc)
        return jsonify({"success": False, "errors": ["internal error"]}), HTTPStatus.INTERNAL_SERVER_ERROR

