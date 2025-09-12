# health_app/routes/chat.py
from http import HTTPStatus
from typing import List, Any, Dict, Optional

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..services.ai_service import chat_raw, chat_json, build_health_prompt
from ..models import Profile  # optionaler Kontext aus DB

chat_bp = Blueprint("chat", __name__)

def _norm_messages(v) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(v, list) or not v:
        return None
    cleaned: List[Dict[str, Any]] = []
    for m in v:
        if not isinstance(m, dict):
            return None
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "").strip()
        if role not in {"user", "assistant", "system"} or not content:
            return None
        cleaned.append({"role": role, "content": content})
    return cleaned

@chat_bp.post("/")
@jwt_required()
def chat():
    """
    Zwei Modi:
      A) Diagnosemodus (empfohlen):
         JSON: {"symptoms":"...", optional: age, sex, onset, duration, medications, conditions, allergies, pregnant, vitals}
         -> {"kind":"triage","data": {...}}  (strukturierte Differentialdiagnose)

      B) Freitext-Chat:
         JSON: {"messages":[{role,content}, ...]}
         -> {"kind":"message","message":"..."}
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    # ---- A) Diagnosemodus, wenn 'symptoms' vorhanden ist
    symptoms = (data.get("symptoms") or "").strip()
    if symptoms:
        # optionaler Patienten-Kontext
        profile: Optional[Profile] = Profile.query.filter_by(user_id=int(user_id)).first() if str(user_id).isdigit() else None
        allergies = [a.name for a in getattr(profile, "allergies", [])] or data.get("allergies", [])
        conditions = [c.name for c in getattr(profile, "conditions", [])] or data.get("conditions", [])

        prompt = build_health_prompt(
            profile=profile,
            allergies=allergies,
            conditions=conditions,
            symptoms_text=symptoms,
        )
        try:
            triage = chat_json(prompt, timeout=45)
            return jsonify({"kind": "triage", "data": triage}), HTTPStatus.OK
        except Exception as exc:
            current_app.logger.exception("chat triage failed: %s", exc)
            return jsonify({"error": "ai_service error"}), HTTPStatus.BAD_GATEWAY

    # ---- B) Freitext-Chat
    messages = _norm_messages(data.get("messages"))
    if not messages:
        return jsonify({"error": "`symptoms` (string) oder `messages` (list) erforderlich"}), HTTPStatus.BAD_REQUEST

    guard = {
        "role": "system",
        "content": (
            "You are a careful health assistant. Do not give definitive diagnoses. "
            "Provide differential considerations with uncertainty, triage suggestions, "
            "self-care tips, and when to seek care. For emergencies, advise to call local emergency services."
        ),
    }
    if messages[0]["role"] != "system":
        messages = [guard] + messages

    try:
        reply = chat_raw(messages=messages, timeout=45)
        return jsonify({"kind": "message", "message": reply}), HTTPStatus.OK
    except Exception as exc:
        current_app.logger.exception("chat raw failed: %s", exc)
        return jsonify({"error": "ai_service error"}), HTTPStatus.BAD_GATEWAY
