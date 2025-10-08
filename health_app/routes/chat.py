# health_app/routes/chat.py
from http import HTTPStatus
from typing import List, Any, Dict, Optional
from datetime import datetime, timedelta
import json

from flask import Blueprint, request, jsonify, current_app, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..services.ai_service import chat_raw, chat_json, build_health_prompt, is_stub_mode
from ..models import Profile, ChatSession, ChatMessage, User
from .. import db
from ..utils.rate_limit import enforce_rate_limit
from ..utils.i18n import resolve_user_language

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

def _resolve_user(identity: Any) -> Optional[User]:
    if identity is None:
        return None
    try:
        return User.query.filter_by(id=int(identity)).first()
    except (ValueError, TypeError):
        pass

    if isinstance(identity, dict):
        if "id" in identity:
            try:
                user = User.query.filter_by(id=int(identity["id"])).first()
                if user:
                    return user
            except (ValueError, TypeError):
                pass
        if "email" in identity:
            normalized_email = str(identity["email"]).strip().lower()
            if normalized_email:
                return User.query.filter_by(email=normalized_email).first()

    normalized = str(identity).strip().lower()
    if not normalized:
        return None
    return User.query.filter_by(email=normalized).first()


def _get_profile_for_user(identity: Any) -> Optional[Profile]:
    """Return the existing profile for the resolved user without creating one."""
    user = _resolve_user(identity)
    if not user:
        return None
    return Profile.query.filter_by(user_id=user.id).first()


def _get_or_create_chat_session(user_id: Any) -> ChatSession:
    """Get existing active chat session or create a new one."""
    try:
        user_row = _resolve_user(user_id)
        if not user_row:
            raise ValueError("User not found")

        profile = Profile.query.filter_by(user_id=user_row.id).first()
        if not profile:
            profile = Profile(user_id=user_row.id)
            db.session.add(profile)
            db.session.commit()
        
        # Look for existing active session (rolling 24 hours)
        window_start = datetime.utcnow() - timedelta(hours=24)
        recent_session = ChatSession.query.filter(
            ChatSession.profile_id == profile.id,
            ChatSession.created_at >= window_start
        ).order_by(ChatSession.created_at.desc()).first()
        
        if recent_session:
            return recent_session
        
        # Create new session
        new_session = ChatSession(profile_id=profile.id)
        db.session.add(new_session)
        db.session.commit()
        return new_session
        
    except Exception as exc:
        current_app.logger.exception("Failed to get/create chat session: %s", exc)
        raise

def _save_chat_message(session_id: int, sender: str, message_text: str):
    """Save a chat message to the database."""
    try:
        message = ChatMessage(
            session_id=session_id,
            sender=sender,
            message_text=message_text
        )
        db.session.add(message)
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("Failed to save chat message: %s", exc)
        # Don't raise - chat should continue even if saving fails

def _get_chat_history(session_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent chat history for context."""
    try:
        messages = ChatMessage.query.filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.sent_at.desc()).limit(limit).all()
        
        # Convert to API format (most recent first)
        history = []
        for msg in reversed(messages):
            history.append({
                "role": msg.sender,
                "content": msg.message_text,
                "timestamp": msg.sent_at.isoformat()
            })
        return history
        
    except Exception as exc:
        current_app.logger.exception("Failed to get chat history: %s", exc)
        return []


def _conversation_to_text(messages: List[ChatMessage]) -> str:
    """Render messages into a simple transcript for summarization/export prompts."""
    lines: List[str] = []
    for msg in messages:
        role = "User" if msg.sender == "user" else "Assistant"
        timestamp = msg.sent_at.isoformat()
        lines.append(f"[{timestamp}] {role}: {msg.message_text}")
    return "\n".join(lines)


def _build_profile_context(profile: Optional[Profile]) -> Optional[str]:
    """Summarize key profile attributes for the system prompt."""
    if not profile:
        return None

    details: List[str] = []

    if profile.age is not None:
        details.append(f"Age: {profile.age}")

    if profile.sex:
        details.append(f"Sex: {profile.sex}")

    allergies = [a.name for a in getattr(profile, "allergies", []) if a.name]
    if allergies:
        details.append("Allergies: " + ", ".join(sorted(allergies)[:5]))

    conditions = [c.name for c in getattr(profile, "conditions", []) if c.name]
    if conditions:
        details.append("Conditions: " + ", ".join(sorted(conditions)[:5]))

    medications = []
    for med in getattr(profile, "medications", []):
        if med.ended_at is None:
            drug_name = med.drug.name if getattr(med, "drug", None) and med.drug.name else med.dosage or "Medication"
            medications.append(drug_name)
    if medications:
        details.append("Active medications: " + ", ".join(sorted(medications)[:5]))

    if not details:
        return None

    return "Patient context: " + "; ".join(details)


def _profile_language(profile: Optional[Profile]) -> str:
    user = getattr(profile, "user", None)
    return resolve_user_language(user)


def _is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_follow_up_suggestions(raw: str) -> List[str]:
    """Best-effort extraction of follow-up suggestions from AI output."""
    if not raw:
        return []

    text = raw.strip()

    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and "suggestions" in payload:
            items = payload["suggestions"]
        else:
            items = payload
        if isinstance(items, list):
            cleaned: List[str] = []
            for item in items:
                if isinstance(item, str):
                    suggestion = item.strip()
                elif isinstance(item, dict):
                    suggestion = str(item.get("text") or item.get("suggestion") or "").strip()
                else:
                    continue
                if suggestion:
                    cleaned.append(suggestion)
            if cleaned:
                return cleaned
    except Exception:
        pass

    suggestions: List[str] = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("-*0123456789. ").strip()
        if stripped:
            suggestions.append(stripped)

    seen: set[str] = set()
    unique: List[str] = []
    for item in suggestions:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


_STUB_FOLLOW_UP_TEXTS = {
    "en": [
        "Would you like tips on when to see a doctor about this concern?",
        "Do you want advice on monitoring these symptoms at home?",
        "Should we review how your medications might relate to this issue?",
    ],
    "de": [
        "Möchtest du Hinweise, wann ein Arztbesuch sinnvoll ist?",
        "Brauchst du Tipps, wie du die Symptome zu Hause beobachten kannst?",
        "Sollen wir prüfen, ob deine Medikamente mit dem Anliegen zusammenhängen?",
    ],
}


def _stub_follow_up(language: str, limit: int) -> List[str]:
    options = _STUB_FOLLOW_UP_TEXTS.get(language) or _STUB_FOLLOW_UP_TEXTS["en"]
    return options[:limit]

@chat_bp.post("/")
@jwt_required()
def chat():
    """
    Enhanced AI Health Assistant Chat with multiple modes:
    
    A) Symptom Analysis Mode:
       JSON: {"symptoms":"...", optional: age, sex, onset, duration, medications, conditions, allergies, pregnant, vitals}
       -> {"kind":"triage","data": {...}}  (structured differential diagnosis)

    B) Conversational Chat Mode:
       JSON: {"messages":[{role,content}, ...], "session_id": optional}
       -> {"kind":"message","message":"...", "session_id": int, "ai_mode": "live|stub"}

    C) Health Question Mode:
       JSON: {"question":"...", "context": optional}
       -> {"kind":"answer","answer":"...", "sources": [...]}
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    role = str(claims.get("role", "user")).lower()

    rl_response = enforce_rate_limit(
        "chat",
        identifier=str(user_id),
        role=role,
    )
    if rl_response is not None:
        return rl_response
    data = request.get_json(silent=True) or {}

    # ---- A) Symptom Analysis Mode
    symptoms = (data.get("symptoms") or "").strip()
    if symptoms:
        try:
            # Get user profile for context
            profile: Optional[Profile] = Profile.query.filter_by(user_id=int(user_id)).first() if str(user_id).isdigit() else None
            allergies = [a.name for a in getattr(profile, "allergies", [])] or data.get("allergies", [])
            conditions = [c.name for c in getattr(profile, "conditions", [])] or data.get("conditions", [])

            prompt = build_health_prompt(
                profile=profile,
                allergies=allergies,
                conditions=conditions,
                symptoms_text=symptoms,
            )
            
            triage = chat_json(prompt, timeout=45)
            return jsonify({
                "kind": "triage", 
                "data": triage,
                "ai_mode": "stub" if is_stub_mode() else "live"
            }), HTTPStatus.OK
            
        except Exception as exc:
            current_app.logger.exception("chat triage failed: %s", exc)
            return jsonify({"error": "ai_service error"}), HTTPStatus.BAD_GATEWAY

    # ---- B) Conversational Chat Mode
    messages = _norm_messages(data.get("messages"))
    if messages:
        try:
            # Get or create chat session
            session = _get_or_create_chat_session(user_id)
            profile_for_context: Optional[Profile] = Profile.query.filter_by(id=session.profile_id).first()
            
            # Get chat history for context
            history = _get_chat_history(session.id, limit=10)
            
            # Build enhanced system prompt
            enhanced_system_prompt = {
                "role": "system",
                "content": (
                    "You are MedAssistant, a helpful and careful health assistant. "
                    "You provide general health information, wellness tips, and guidance on when to seek medical care. "
                    "You do NOT provide definitive diagnoses or replace professional medical advice. "
                    "Always recommend consulting healthcare professionals for serious concerns. "
                    "For emergencies, advise calling local emergency services immediately. "
                    "Be empathetic, clear, and helpful while maintaining appropriate medical boundaries."
                )
            }

            patient_context = _build_profile_context(profile_for_context)
            context_message = (
                {"role": "system", "content": patient_context}
                if patient_context
                else None
            )

            # Combine history with new messages (remove non-chat fields like timestamp)
            sanitized_history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in history
                if msg.get("role") and msg.get("content")
            ]

            all_messages: List[Dict[str, Any]] = [enhanced_system_prompt]
            if context_message:
                all_messages.append(context_message)
            all_messages += sanitized_history + messages
            
            # Generate AI response
            language = _profile_language(profile_for_context)
            reply = chat_raw(messages=all_messages, timeout=45, language=language)
            
            # Save both user message and AI response
            if messages:
                last_user_message = next((msg for msg in reversed(messages) if msg["role"] == "user"), None)
                if last_user_message:
                    _save_chat_message(session.id, "user", last_user_message["content"])
            
            _save_chat_message(session.id, "assistant", reply)
            
            return jsonify({
                "kind": "message", 
                "message": reply,
                "session_id": session.id,
                "ai_mode": "stub" if is_stub_mode() else "live"
            }), HTTPStatus.OK
            
        except Exception as exc:
            current_app.logger.exception("chat conversation failed: %s", exc)
            return jsonify({"error": "ai_service error"}), HTTPStatus.BAD_GATEWAY

    # ---- C) Health Question Mode
    question = (data.get("question") or "").strip()
    if question:
        try:
            context = data.get("context", "")
            
            question_prompt = f"""
            You are MedAssistant, a helpful health assistant. Answer this health question clearly and safely:
            
            Question: {question}
            
            Context: {context if context else "No additional context provided"}
            
            Guidelines:
            - Provide helpful, evidence-based information
            - Be clear about limitations and when to seek professional help
            - Do not provide definitive diagnoses
            - Recommend consulting healthcare professionals for serious concerns
            - For emergencies, advise calling emergency services
            """
            
            profile_for_context = _get_profile_for_user(user_id)
            language = _profile_language(profile_for_context)

            messages = [
                {"role": "system", "content": question_prompt},
                {"role": "user", "content": question}
            ]
            
            answer = chat_raw(messages=messages, timeout=45, language=language)
            
            return jsonify({
                "kind": "answer",
                "answer": answer,
                "sources": ["MedAssistant AI Health Database"],
                "ai_mode": "stub" if is_stub_mode() else "live"
            }), HTTPStatus.OK
            
        except Exception as exc:
            current_app.logger.exception("chat question failed: %s", exc)
            return jsonify({"error": "ai_service error"}), HTTPStatus.BAD_GATEWAY

    # No valid mode specified
    return jsonify({
        "error": "Please provide either 'symptoms' (string), 'messages' (list), or 'question' (string)"
    }), HTTPStatus.BAD_REQUEST

@chat_bp.get("/history")
@jwt_required()
def get_chat_history():
    """Get chat history for the current user."""
    user_id = get_jwt_identity()
    
    try:
        user_id_int = int(user_id)
        profile = Profile.query.filter_by(user_id=user_id_int).first()
        if not profile:
            return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND
        
        # Get recent sessions
        sessions = ChatSession.query.filter(
            ChatSession.profile_id == profile.id
        ).order_by(ChatSession.created_at.desc()).limit(10).all()
        
        history = []
        for session in sessions:
            messages = ChatMessage.query.filter(
                ChatMessage.session_id == session.id
            ).order_by(ChatMessage.sent_at.asc()).all()
            
            session_data = {
                "session_id": session.id,
                "created_at": session.created_at.isoformat(),
                "message_count": len(messages),
                "messages": [
                    {
                        "role": msg.sender,
                        "content": msg.message_text,
                        "timestamp": msg.sent_at.isoformat()
                    }
                    for msg in messages
                ]
            }
            history.append(session_data)
        
        return jsonify({
            "success": True,
            "data": {
                "sessions": history,
                "total_sessions": len(history)
            }
        }), HTTPStatus.OK
        
    except Exception as exc:
        current_app.logger.exception("Failed to get chat history: %s", exc)
        return jsonify({"error": "Failed to retrieve chat history"}), HTTPStatus.INTERNAL_SERVER_ERROR


@chat_bp.get("/export")
@jwt_required()
def export_chat_session():
    """Export a chat session in JSON or plain text format for the current user."""
    user_id = get_jwt_identity()

    profile = _get_profile_for_user(user_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    _language = _profile_language(profile)  # aktuell ungenutzt

    session_id = request.args.get("session_id", type=int)
    export_format = (request.args.get("format") or "json").strip().lower()
    anonymize = _is_truthy(request.args.get("anonymize"))

    if export_format not in {"json", "txt", "text"}:
        return jsonify({"error": "format must be 'json' or 'txt'"}), HTTPStatus.BAD_REQUEST

    session_query = ChatSession.query.filter(ChatSession.profile_id == profile.id)
    if session_id is not None:
        session_query = session_query.filter(ChatSession.id == session_id)

    session = session_query.order_by(ChatSession.created_at.desc()).first()
    if not session:
        return jsonify({"error": "Chat session not found"}), HTTPStatus.NOT_FOUND

    messages = ChatMessage.query.filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.sent_at.asc()).all()

    session_payload = {
        "session_id": session.id,
        "created_at": session.created_at.isoformat(),
        "message_count": len(messages),
        "messages": [
            {
                "role": msg.sender,
                "content": msg.message_text,
                "timestamp": msg.sent_at.isoformat()
            }
            for msg in messages
        ]
    }

    if anonymize:
        session_payload["anonymized"] = True
        session_payload["session_id"] = f"session-{session.id}"
        session_payload["created_at"] = session.created_at.date().isoformat()
        for entry in session_payload["messages"]:
            entry.pop("timestamp", None)
    else:
        session_payload["anonymized"] = False

    if export_format == "json":
        return jsonify({
            "success": True,
            "data": session_payload,
            "ai_mode": "stub" if is_stub_mode() else "live"
        }), HTTPStatus.OK

    # Plain text export
    lines = []
    for msg in messages:
        role = "User" if msg.sender == "user" else "Assistant"
        if anonymize:
            lines.append(f"{role}: {msg.message_text}")
        else:
            timestamp = msg.sent_at.isoformat()
            lines.append(f"[{timestamp}] {role}: {msg.message_text}")

    if not lines:
        lines.append("(no messages in this session)")

    payload = "\n".join(lines)
    response = make_response(payload)
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=chat-session-{session.id}.txt"
    return response


@chat_bp.post("/summarize")
@jwt_required()
def summarize_chat_session():
    """Generate a concise summary of a chat session using the AI service."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    profile = _get_profile_for_user(user_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    session_id = data.get("session_id")
    max_messages = data.get("max_messages")

    try:
        session_query = ChatSession.query.filter(ChatSession.profile_id == profile.id)

        if session_id is not None:
            session_query = session_query.filter(ChatSession.id == int(session_id))

        session = session_query.order_by(ChatSession.created_at.desc()).first()
        if not session:
            return jsonify({"error": "Chat session not found"}), HTTPStatus.NOT_FOUND

        message_query = ChatMessage.query.filter(ChatMessage.session_id == session.id)

        limit: Optional[int] = None
        if max_messages is not None:
            limit = int(max_messages)
            if limit <= 0:
                raise ValueError
            recent_messages = message_query.order_by(ChatMessage.sent_at.desc()).limit(limit).all()
            messages = list(reversed(recent_messages))
        else:
            messages = message_query.order_by(ChatMessage.sent_at.asc()).all()

        if not messages:
            return jsonify({"error": "Chat session has no messages"}), HTTPStatus.BAD_REQUEST

    except ValueError:
        return jsonify({"error": "max_messages must be a positive integer"}), HTTPStatus.BAD_REQUEST

    transcript = _conversation_to_text(messages)

    system_prompt = (
        "You are MedAssistant, summarizing a conversation between a patient and the assistant. "
        "Provide a concise summary with three sections: Overview, Key Points, and Suggested Follow-ups. "
        "Highlight safety guidance when relevant and avoid definitive diagnoses."
    )

    user_prompt = (
        "Summarize the following conversation transcript. Focus on the user's concerns, the assistant's guidance, "
        "and next steps."
        f"\n\nConversation:\n{transcript}"
    )

    language = _profile_language(profile)

    try:
        summary = chat_raw(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            timeout=45,
            language=language,
        )
    except Exception as exc:
        current_app.logger.exception("Failed to summarize chat session: %s", exc)
        return jsonify({"error": "ai_service error"}), HTTPStatus.BAD_GATEWAY

    return jsonify({
        "success": True,
        "data": {
            "session_id": session.id,
            "summary": summary,
            "message_count": len(messages),
        },
        "ai_mode": "stub" if is_stub_mode() else "live"
    }), HTTPStatus.OK


@chat_bp.post("/follow-ups")
@jwt_required()
def get_follow_up_suggestions():
    """Return follow-up question suggestions for the user's most recent chat context."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    profile = _get_profile_for_user(user_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    session_id = data.get("session_id")
    last_message = (data.get("last_message") or "").strip()
    max_suggestions = data.get("max_suggestions")

    if session_id is None and not last_message:
        return jsonify({"error": "Provide either session_id or last_message"}), HTTPStatus.BAD_REQUEST

    try:
        limit = None
        if max_suggestions is not None:
            limit = int(max_suggestions)
            if limit <= 0 or limit > 10:
                raise ValueError
        else:
            limit = 3
    except ValueError:
        return jsonify({"error": "max_suggestions must be between 1 and 10"}), HTTPStatus.BAD_REQUEST

    conversation_snippet = ""
    if session_id is not None:
        try:
            session_id_int = int(session_id)
        except (TypeError, ValueError):
            return jsonify({"error": "session_id must be an integer"}), HTTPStatus.BAD_REQUEST

        session = ChatSession.query.filter(
            ChatSession.profile_id == profile.id,
            ChatSession.id == session_id_int
        ).first()
        if not session:
            return jsonify({"error": "Chat session not found"}), HTTPStatus.NOT_FOUND

        recent_messages = ChatMessage.query.filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.sent_at.desc()).limit(6).all()
        if recent_messages:
            conversation_snippet = _conversation_to_text(list(reversed(recent_messages)))

    if not conversation_snippet and not last_message:
        return jsonify({"error": "No conversation context available"}), HTTPStatus.BAD_REQUEST

    language = _profile_language(profile)

    if is_stub_mode():
        suggestions = _stub_follow_up(language, limit)
        return jsonify({
            "success": True,
            "data": {
                "suggestions": suggestions,
                "source": "stub",
            },
            "ai_mode": "stub"
        }), HTTPStatus.OK

    system_prompt = (
        "You are MedAssistant generating follow-up questions that help patients explore their concerns safely. "
        "Responses must be a short unordered list (max 5) of concise suggestions encouraging next steps, "
        "with no diagnoses and at least one safety reminder."
    )

    user_prompt = """
Provide follow-up questions the assistant could ask next based on this conversation.

Conversation:
{conversation}

Latest user message:
{last}

Return JSON: {{"suggestions": ["..."]}}
""".format(conversation=conversation_snippet or "(none provided)", last=last_message or "(none provided)")

    try:
        response = chat_raw(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            timeout=30,
            language=language,
        )
    except Exception as exc:
        current_app.logger.exception("Failed to generate follow-up suggestions: %s", exc)
        return jsonify({"error": "ai_service error"}), HTTPStatus.BAD_GATEWAY

    suggestions = _parse_follow_up_suggestions(response)[:limit]
    if not suggestions:
        return jsonify({"error": "Failed to parse suggestions"}), HTTPStatus.BAD_GATEWAY

    return jsonify({
        "success": True,
        "data": {
            "suggestions": suggestions,
            "source": "ai",
        },
        "ai_mode": "stub" if is_stub_mode() else "live"
    }), HTTPStatus.OK


@chat_bp.post("/new-session")
@jwt_required()
def create_new_session():
    """Create a new chat session."""
    user_id = get_jwt_identity()
    
    try:
        user_id_int = int(user_id)
        profile = Profile.query.filter_by(user_id=user_id_int).first()
        if not profile:
            return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND
        
        # Create new session
        new_session = ChatSession(profile_id=profile.id)
        db.session.add(new_session)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "data": {
                "session_id": new_session.id,
                "created_at": new_session.created_at.isoformat()
            }
        }), HTTPStatus.CREATED
        
    except Exception as exc:
        current_app.logger.exception("Failed to create new session: %s", exc)
        return jsonify({"error": "Failed to create new session"}), HTTPStatus.INTERNAL_SERVER_ERROR

@chat_bp.get("/suggestions")
@jwt_required()
def get_chat_suggestions():
    """Get suggested questions/topics for the health assistant."""
    suggestions = [
        {
            "category": "General Health",
            "questions": [
                "What are the benefits of regular exercise?",
                "How can I improve my sleep quality?",
                "What should I include in a healthy diet?",
                "How often should I get health checkups?"
            ]
        },
        {
            "category": "Symptoms & Concerns",
            "questions": [
                "When should I be concerned about a headache?",
                "What causes fatigue and how can I manage it?",
                "How do I know if I have a cold or the flu?",
                "What are the warning signs of dehydration?"
            ]
        },
        {
            "category": "Medications",
            "questions": [
                "How should I store my medications?",
                "What should I do if I miss a dose?",
                "How can I avoid drug interactions?",
                "When should I take medications with food?"
            ]
        },
        {
            "category": "Emergency Situations",
            "questions": [
                "When should I call emergency services?",
                "What are the signs of a heart attack?",
                "How do I recognize a stroke?",
                "What should I do in case of severe allergic reaction?"
            ]
        }
    ]
    
    return jsonify({
        "success": True,
        "data": {
            "suggestions": suggestions,
            "ai_mode": "stub" if is_stub_mode() else "live"
        }
    }), HTTPStatus.OK
