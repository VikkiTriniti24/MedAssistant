# health_app/routes/profile.py
from http import HTTPStatus
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from .. import db
from ..models import (
    User, Profile, Allergy, Condition, ProfileMedication,
    Drug, SymptomEntry, Diagnosis, RiskEvaluation, SymptomSeverity, UserPreferences,
    MedicationSchedule, EmergencyContact, FamilyMember,
)
from ..services.reminder_service import build_reminder_payload

profile_bp = Blueprint("profile", __name__)

_ALLOWED_LANGUAGES = {"en", "de", "es", "fr", "it"}

_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_DAY_ALIASES = {
    "monday": "mon", "mon": "mon",
    "tuesday": "tue", "tue": "tue",
    "wednesday": "wed", "wed": "wed",
    "thursday": "thu", "thu": "thu",
    "friday": "fri", "fri": "fri",
    "saturday": "sat", "sat": "sat",
    "sunday": "sun", "sun": "sun",
}


def _parse_iso_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_schedule_payload(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(data, dict):
        return None, "body must be a JSON object"

    timezone = (data.get("timezone") or "UTC").strip() or "UTC"
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return None, "timezone is invalid"

    times_raw = data.get("times")
    if not isinstance(times_raw, list) or not times_raw:
        return None, "times must be a non-empty list"

    normalized_times: List[str] = []
    for item in times_raw:
        t = str(item).strip()
        if not _TIME_PATTERN.match(t):
            return None, "times must be in HH:MM 24h format"
        normalized_times.append(t)

    normalized_times = sorted(dict.fromkeys(normalized_times))

    days_raw = data.get("days_of_week")
    normalized_days: Optional[List[str]] = None
    if days_raw is not None:
        if not isinstance(days_raw, list) or not days_raw:
            return None, "days_of_week must be a list of weekday names"
        seen_days = []
        for item in days_raw:
            key = _DAY_ALIASES.get(str(item).strip().lower())
            if not key:
                return None, "days_of_week contains an invalid value"
            if key not in seen_days:
                seen_days.append(key)
        normalized_days = seen_days

    start_date = _parse_iso_date(data.get("start_date"))
    if data.get("start_date") and start_date is None:
        return None, "start_date must be ISO date"

    end_date = _parse_iso_date(data.get("end_date"))
    if data.get("end_date") and end_date is None:
        return None, "end_date must be ISO date"

    if start_date and end_date and start_date > end_date:
        return None, "start_date must be before end_date"

    reminders = data.get("reminders") or {}
    if not isinstance(reminders, dict):
        return None, "reminders must be an object"

    remind_email = bool(reminders.get("email", False))
    remind_push = bool(reminders.get("push", False))
    remind_sms = bool(reminders.get("sms", False))

    instructions = (data.get("instructions") or "").strip()
    notes = (data.get("notes") or "").strip()

    schedule_payload: Dict[str, Any] = {
        "times": normalized_times,
    }
    if normalized_days:
        schedule_payload["days_of_week"] = normalized_days
    if instructions:
        schedule_payload["instructions"] = instructions

    parsed = {
        "timezone": timezone,
        "start_date": start_date,
        "end_date": end_date,
        "remind_via_email": remind_email,
        "remind_via_push": remind_push,
        "remind_via_sms": remind_sms,
        "notes": notes or None,
        "schedule_payload": schedule_payload,
    }
    return parsed, None


def _body_systems_from_factors(factors: Optional[List[Any]]) -> List[str]:
    systems: List[str] = []
    if not factors:
        return systems
    for value in factors:
        if isinstance(value, str) and value.startswith("system:"):
            systems.append(value.split(":", 1)[1])
    return systems


def _serialize_schedule(schedule: Optional[MedicationSchedule]) -> Optional[Dict[str, Any]]:
    if not schedule:
        return None
    try:
        schedule_data = json.loads(schedule.schedule_data or "{}")
    except json.JSONDecodeError:
        schedule_data = {}
    return {
        "timezone": schedule.timezone,
        "times": schedule_data.get("times", []),
        "days_of_week": schedule_data.get("days_of_week", []),
        "instructions": schedule_data.get("instructions"),
        "start_date": schedule.start_date.isoformat() if schedule.start_date else None,
        "end_date": schedule.end_date.isoformat() if schedule.end_date else None,
        "reminders": {
            "email": bool(schedule.remind_via_email),
            "push": bool(schedule.remind_via_push),
            "sms": bool(schedule.remind_via_sms),
        },
        "notes": schedule.notes,
        "updated_at": schedule.updated_at.isoformat() if schedule.updated_at else None,
    }


def _serialize_contact(contact: EmergencyContact) -> Dict[str, Any]:
    return {
        "id": contact.id,
        "name": contact.name,
        "relationship": contact.relationship,
        "phone": contact.phone,
        "email": contact.email,
        "is_primary": bool(contact.is_primary),
        "notes": contact.notes,
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
    }


def _validate_contact_payload(data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(data, dict):
        return "body must be a JSON object"

    name = (data.get("name") or "").strip()
    if not name:
        return "name is required"

    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()

    if not phone and not email:
        return "phone or email is required"

    if email and "@" not in email:
        return "email must be valid"

    return None


def _serialize_family_member(member: FamilyMember) -> Dict[str, Any]:
    return {
        "id": member.id,
        "name": member.name,
        "relationship": member.relationship,
        "birthdate": member.birthdate.isoformat() if member.birthdate else None,
        "notes": member.notes,
        "share_preferences": bool(member.share_preferences),
        "created_at": member.created_at.isoformat() if member.created_at else None,
        "updated_at": member.updated_at.isoformat() if member.updated_at else None,
    }


def _validate_family_payload(data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(data, dict):
        return "body must be a JSON object"

    name = (data.get("name") or "").strip()
    relationship = (data.get("relationship") or "").strip()

    if not name:
        return "name is required"
    if not relationship:
        return "relationship is required"

    birthdate = data.get("birthdate")
    if birthdate:
        try:
            datetime.fromisoformat(str(birthdate))
        except ValueError:
            return "birthdate must be ISO format YYYY-MM-DD"

    return None


def _get_user_by_identity(identity: Any) -> Optional[User]:
    """Resolve a JWT identity to a User by id or email."""
    if identity is None:
        return None

    # Direct numeric id
    try:
        return User.query.filter_by(id=int(identity)).first()
    except (ValueError, TypeError):
        pass

    # Mapping-style identity (e.g. {"id": 1, "email": "..."})
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

    # String identity (email)
    normalized = str(identity).strip().lower()
    if not normalized:
        return None
    return User.query.filter_by(email=normalized).first()


def _get_user_profile(user_id: str) -> Optional[Profile]:
    """Get user profile by user ID."""
    try:
        user_id_int = int(user_id)
        return Profile.query.filter_by(user_id=user_id_int).first()
    except (ValueError, TypeError):
        return None


def _ensure_profile(user_id: str) -> Optional[Profile]:
    """Return an existing profile or create one if the user exists."""
    profile = _get_user_profile(user_id)
    if profile:
        return profile
    current_app.logger.debug("Profile missing for user_id=%r; attempting to create", user_id)
    user = _get_user_by_identity(user_id)
    if not user:
        current_app.logger.warning("Profile lookup failed: user not found for identity=%r", user_id)
        return None

    profile = Profile(user_id=user.id)
    db.session.add(profile)
    db.session.commit()
    return profile


def _ensure_preferences(user_id: int) -> UserPreferences:
    prefs = UserPreferences.query.filter_by(user_id=user_id).first()
    if prefs:
        return prefs

    prefs = UserPreferences(user_id=user_id)
    db.session.add(prefs)
    db.session.commit()
    return prefs


def _serialize_preferences(prefs: Optional[UserPreferences]) -> Dict[str, Any]:
    if not prefs:
        return {
            "language": "en",
            "notify_email": True,
            "notify_push": False,
            "notify_sms": False,
        }
    return {
        "language": prefs.language,
        "notify_email": prefs.notify_email,
        "notify_push": prefs.notify_push,
        "notify_sms": prefs.notify_sms,
        "updated_at": prefs.updated_at.isoformat() if prefs.updated_at else None,
    }


def _validate_profile_data(data: Dict[str, Any]) -> Optional[str]:
    """Validate profile update data."""
    if not isinstance(data, dict):
        return "body must be a JSON object"
    
    # Validate age
    if "age" in data:
        try:
            age = int(data["age"])
            if age < 0 or age > 130:
                return "age must be between 0 and 130"
        except (TypeError, ValueError):
            return "age must be an integer"
    
    # Validate sex
    if "sex" in data:
        sex = str(data["sex"]).lower()
        if sex not in {"female", "male", "other", "unknown"}:
            return "sex must be one of: female, male, other, unknown"
    
    return None

@profile_bp.get("/")
@jwt_required()
def get_profile():
    """Get current user's profile information."""
    user_id = get_jwt_identity()
    profile = _ensure_profile(user_id)

    if not profile:
        return jsonify({"error": "User not found"}), HTTPStatus.UNAUTHORIZED
    
    try:
        # Get user info
        user = profile.user
        
        # Get allergies
        allergies = [{"id": a.id, "name": a.name} for a in profile.allergies]
        
        # Get conditions
        conditions = [{"id": c.id, "name": c.name} for c in profile.conditions]
        
        # Get medications
        medications = []
        for med in profile.medications:
            medication_data = {
                "id": med.id,
                "drug_name": med.drug.name if med.drug else "Unknown",
                "dosage": med.dosage,
                "started_at": med.started_at.isoformat() if med.started_at else None,
                "ended_at": med.ended_at.isoformat() if med.ended_at else None,
                "is_active": med.ended_at is None,
                "schedule": _serialize_schedule(med.schedule),
            }
            medications.append(medication_data)

        contacts = EmergencyContact.query.filter_by(profile_id=profile.id).order_by(
            EmergencyContact.is_primary.desc(), EmergencyContact.created_at.asc()
        ).all()

        # Get recent health entries
        recent_symptoms = SymptomEntry.query.filter(
            SymptomEntry.profile_id == profile.id
        ).order_by(SymptomEntry.entered_at.desc()).limit(5).all()
        
        health_history = []
        for entry in recent_symptoms:
            diagnoses = Diagnosis.query.filter(
                Diagnosis.symptom_entry_id == entry.id
            ).all()
            
            risk_eval = RiskEvaluation.query.filter(
                RiskEvaluation.symptom_entry_id == entry.id
            ).first()

            severity = SymptomSeverity.query.filter(
                SymptomSeverity.symptom_entry_id == entry.id
            ).first()

            severity_payload = None
            body_systems: List[str] = []
            if severity:
                factors = list(severity.factors or [])
                body_systems = _body_systems_from_factors(factors)
                severity_payload = {
                    "score": severity.score,
                    "level": severity.level,
                    "factors": factors,
                    "body_systems": body_systems,
                    "recorded_at": severity.created_at.isoformat(),
                }

            entry_data = {
                "id": entry.id,
                "symptoms": entry.symptoms,
                "entered_at": entry.entered_at.isoformat(),
                "diagnoses": [
                    {
                        "condition": d.condition_name,
                        "probability": d.probability,
                        "triage_level": d.triage_level
                    }
                    for d in diagnoses
                ],
                "risk_evaluation": {
                    "risk_level": risk_eval.risk_level,
                    "urgency": risk_eval.urgency
                } if risk_eval else None,
                "severity": severity_payload,
                "body_systems": body_systems,
            }
            health_history.append(entry_data)
        
        profile_data = {
            "user": {
                "id": user.id,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
                "email_verified": getattr(user, "email_verified", False),
                "is_active": getattr(user, "is_active", True),
            },
            "profile": {
                "id": profile.id,
                "age": profile.age,
                "sex": profile.sex,
                "created_at": profile.created_at.isoformat(),
                "updated_at": profile.updated_at.isoformat()
            },
            "allergies": allergies,
            "conditions": conditions,
            "medications": medications,
            "emergency_contacts": [_serialize_contact(contact) for contact in contacts],
            "family_members": [
                _serialize_family_member(member)
                for member in FamilyMember.query.filter_by(profile_id=profile.id).order_by(
                    FamilyMember.created_at.asc()
                ).all()
            ],
            "health_history": health_history,
            "preferences": _serialize_preferences(_ensure_preferences(user.id)),
            "summary": {
                "total_allergies": len(allergies),
                "total_conditions": len(conditions),
                "active_medications": len([m for m in medications if m["is_active"]]),
                "total_health_entries": len(health_history),
                "emergency_contacts": len(contacts),
                "family_members": FamilyMember.query.filter_by(profile_id=profile.id).count(),
            }
        }
        
        return jsonify({
            "success": True,
            "data": profile_data
        }), HTTPStatus.OK
        
    except Exception as exc:
        current_app.logger.exception("Failed to get profile: %s", exc)
        return jsonify({"error": "Failed to retrieve profile"}), HTTPStatus.INTERNAL_SERVER_ERROR

@profile_bp.put("/")
@jwt_required()
def update_profile():
    """Update current user's profile information."""
    user_id = get_jwt_identity()
    profile = _ensure_profile(user_id)

    if not profile:
        return jsonify({"error": "User not found"}), HTTPStatus.UNAUTHORIZED
    
    data = request.get_json(silent=True) or {}
    
    # Validate input
    error = _validate_profile_data(data)
    if error:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST
    
    try:
        # Update profile fields
        if "age" in data:
            profile.age = int(data["age"])
        
        if "sex" in data:
            profile.sex = str(data["sex"]).lower()
        
        profile.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Profile updated successfully",
            "data": {
                "age": profile.age,
                "sex": profile.sex,
                "updated_at": profile.updated_at.isoformat()
            }
        }), HTTPStatus.OK
        
    except Exception as exc:
        current_app.logger.exception("Failed to update profile: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to update profile"}), HTTPStatus.INTERNAL_SERVER_ERROR

@profile_bp.post("/allergies/")
@jwt_required()
def add_allergy():
    """Add an allergy to the user's profile."""
    user_id = get_jwt_identity()
    profile = _ensure_profile(user_id)

    if not profile:
        return jsonify({"error": "User not found"}), HTTPStatus.UNAUTHORIZED
    
    data = request.get_json(silent=True) or {}
    allergy_name = (data.get("name") or "").strip()
    
    if not allergy_name:
        return jsonify({"error": "Allergy name is required"}), HTTPStatus.BAD_REQUEST
    
    try:
        # Check if allergy already exists
        existing = Allergy.query.filter_by(
            profile_id=profile.id,
            name=allergy_name
        ).first()
        
        if existing:
            return jsonify({"error": "Allergy already exists"}), HTTPStatus.CONFLICT
        
        # Add new allergy
        allergy = Allergy(profile_id=profile.id, name=allergy_name)
        db.session.add(allergy)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Allergy added successfully",
            "data": {
                "id": allergy.id,
                "name": allergy.name
            }
        }), HTTPStatus.CREATED
        
    except Exception as exc:
        current_app.logger.exception("Failed to add allergy: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to add allergy"}), HTTPStatus.INTERNAL_SERVER_ERROR

@profile_bp.delete("/allergies/<int:allergy_id>/")
@jwt_required()
def remove_allergy(allergy_id: int):
    """Remove an allergy from the user's profile."""
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)
    
    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND
    
    try:
        allergy = Allergy.query.filter_by(
            id=allergy_id,
            profile_id=profile.id
        ).first()
        
        if not allergy:
            return jsonify({"error": "Allergy not found"}), HTTPStatus.NOT_FOUND
        
        db.session.delete(allergy)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Allergy removed successfully"
        }), HTTPStatus.OK
        
    except Exception as exc:
        current_app.logger.exception("Failed to remove allergy: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to remove allergy"}), HTTPStatus.INTERNAL_SERVER_ERROR

@profile_bp.post("/conditions/")
@jwt_required()
def add_condition():
    """Add a medical condition to the user's profile."""
    user_id = get_jwt_identity()
    profile = _ensure_profile(user_id)

    if not profile:
        return jsonify({"error": "User not found"}), HTTPStatus.UNAUTHORIZED
    
    data = request.get_json(silent=True) or {}
    condition_name = (data.get("name") or "").strip()
    
    if not condition_name:
        return jsonify({"error": "Condition name is required"}), HTTPStatus.BAD_REQUEST
    
    try:
        # Check if condition already exists
        existing = Condition.query.filter_by(
            profile_id=profile.id,
            name=condition_name
        ).first()
        
        if existing:
            return jsonify({"error": "Condition already exists"}), HTTPStatus.CONFLICT
        
        # Add new condition
        condition = Condition(profile_id=profile.id, name=condition_name)
        db.session.add(condition)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Condition added successfully",
            "data": {
                "id": condition.id,
                "name": condition.name
            }
        }), HTTPStatus.CREATED
        
    except Exception as exc:
        current_app.logger.exception("Failed to add condition: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to add condition"}), HTTPStatus.INTERNAL_SERVER_ERROR

@profile_bp.delete("/conditions/<int:condition_id>/")
@jwt_required()
def remove_condition(condition_id: int):
    """Remove a medical condition from the user's profile."""
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)
    
    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND
    
    try:
        condition = Condition.query.filter_by(
            id=condition_id,
            profile_id=profile.id
        ).first()
        
        if not condition:
            return jsonify({"error": "Condition not found"}), HTTPStatus.NOT_FOUND
        
        db.session.delete(condition)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Condition removed successfully"
        }), HTTPStatus.OK
        
    except Exception as exc:
        current_app.logger.exception("Failed to remove condition: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to remove condition"}), HTTPStatus.INTERNAL_SERVER_ERROR

@profile_bp.post("/medications/")
@jwt_required()
def add_medication():
    """Add a medication to the user's profile."""
    user_id = get_jwt_identity()
    profile = _ensure_profile(user_id)

    if not profile:
        return jsonify({"error": "User not found"}), HTTPStatus.UNAUTHORIZED
    
    data = request.get_json(silent=True) or {}
    
    # Validate required fields
    drug_name = (data.get("drug_name") or "").strip()
    dosage = (data.get("dosage") or "").strip()
    
    if not drug_name:
        return jsonify({"error": "Drug name is required"}), HTTPStatus.BAD_REQUEST
    
    try:
        # Find or create drug
        drug = Drug.query.filter_by(name=drug_name.lower()).first()
        if not drug:
            # Create new drug entry
            drug = Drug(
                name=drug_name.lower(),
                standard_dosage=dosage
            )
            db.session.add(drug)
            db.session.flush()
        
        # Parse dates
        started_at = None
        ended_at = None
        
        if data.get("started_at"):
            try:
                started_at = datetime.fromisoformat(data["started_at"].replace('Z', '+00:00')).date()
            except ValueError:
                return jsonify({"error": "Invalid started_at date format"}), HTTPStatus.BAD_REQUEST
        
        if data.get("ended_at"):
            try:
                ended_at = datetime.fromisoformat(data["ended_at"].replace('Z', '+00:00')).date()
            except ValueError:
                return jsonify({"error": "Invalid ended_at date format"}), HTTPStatus.BAD_REQUEST
        
        # Add medication
        medication = ProfileMedication(
            profile_id=profile.id,
            drug_id=drug.id,
            dosage=dosage,
            started_at=started_at,
            ended_at=ended_at
        )
        db.session.add(medication)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Medication added successfully",
            "data": {
                "id": medication.id,
                "drug_name": drug.name,
            "dosage": medication.dosage,
            "started_at": medication.started_at.isoformat() if medication.started_at else None,
            "ended_at": medication.ended_at.isoformat() if medication.ended_at else None,
            "is_active": medication.ended_at is None,
            "schedule": _serialize_schedule(medication.schedule),
            "reminder": build_reminder_payload(medication),
        }
        }), HTTPStatus.CREATED
        
    except Exception as exc:
        current_app.logger.exception("Failed to add medication: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to add medication"}), HTTPStatus.INTERNAL_SERVER_ERROR

@profile_bp.put("/medications/<int:medication_id>/")
@jwt_required()
def update_medication(medication_id: int):
    """Update a medication in the user's profile."""
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)
    
    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND
    
    data = request.get_json(silent=True) or {}
    
    try:
        medication = ProfileMedication.query.filter_by(
            id=medication_id,
            profile_id=profile.id
        ).first()
        
        if not medication:
            return jsonify({"error": "Medication not found"}), HTTPStatus.NOT_FOUND
        
        # Update fields
        if "dosage" in data:
            medication.dosage = data["dosage"]
        
        if "started_at" in data:
            if data["started_at"]:
                medication.started_at = datetime.fromisoformat(data["started_at"].replace('Z', '+00:00')).date()
            else:
                medication.started_at = None
        
        if "ended_at" in data:
            if data["ended_at"]:
                medication.ended_at = datetime.fromisoformat(data["ended_at"].replace('Z', '+00:00')).date()
            else:
                medication.ended_at = None
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Medication updated successfully",
            "data": {
                "id": medication.id,
                "drug_name": medication.drug.name,
            "dosage": medication.dosage,
            "started_at": medication.started_at.isoformat() if medication.started_at else None,
            "ended_at": medication.ended_at.isoformat() if medication.ended_at else None,
            "is_active": medication.ended_at is None,
            "schedule": _serialize_schedule(medication.schedule),
            "reminder": build_reminder_payload(medication),
        }
        }), HTTPStatus.OK
        
    except Exception as exc:
        current_app.logger.exception("Failed to update medication: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to update medication"}), HTTPStatus.INTERNAL_SERVER_ERROR


@profile_bp.post("/medications/<int:medication_id>/schedule/")
@jwt_required()
def upsert_medication_schedule(medication_id: int):
    """Create or update a medication schedule for the current user."""
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    medication = ProfileMedication.query.filter_by(
        id=medication_id,
        profile_id=profile.id
    ).first()

    if not medication:
        return jsonify({"error": "Medication not found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    parsed, error = _parse_schedule_payload(data)
    if error:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    try:
        schedule = medication.schedule
        created = False
        if not schedule:
            schedule = MedicationSchedule(profile_medication_id=medication.id)
            created = True
            db.session.add(schedule)

        schedule.timezone = parsed["timezone"]
        schedule.schedule_data = json.dumps(parsed["schedule_payload"])
        schedule.start_date = parsed["start_date"]
        schedule.end_date = parsed["end_date"]
        schedule.remind_via_email = parsed["remind_via_email"]
        schedule.remind_via_push = parsed["remind_via_push"]
        schedule.remind_via_sms = parsed["remind_via_sms"]
        schedule.notes = parsed["notes"]
        schedule.updated_at = datetime.utcnow()
        if created:
            schedule.created_at = datetime.utcnow()

        db.session.commit()

        status = HTTPStatus.CREATED if created else HTTPStatus.OK
        return jsonify({
            "success": True,
            "data": _serialize_schedule(schedule),
        }), status

    except Exception as exc:
        current_app.logger.exception("Failed to upsert medication schedule: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to update schedule"}), HTTPStatus.INTERNAL_SERVER_ERROR


@profile_bp.get("/medications/<int:medication_id>/schedule/")
@jwt_required()
def get_medication_schedule(medication_id: int):
    """Get the medication schedule for the current user."""
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    medication = ProfileMedication.query.filter_by(
        id=medication_id,
        profile_id=profile.id
    ).first()

    if not medication or not medication.schedule:
        return jsonify({"error": "Medication schedule not found"}), HTTPStatus.NOT_FOUND

    return jsonify({
        "success": True,
        "data": _serialize_schedule(medication.schedule),
    }), HTTPStatus.OK


@profile_bp.delete("/medications/<int:medication_id>/schedule/")
@jwt_required()
def delete_medication_schedule(medication_id: int):
    """Delete the medication schedule for the current user."""
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    medication = ProfileMedication.query.filter_by(
        id=medication_id,
        profile_id=profile.id
    ).first()

    if not medication or not medication.schedule:
        return jsonify({"error": "Medication schedule not found"}), HTTPStatus.NOT_FOUND

    try:
        db.session.delete(medication.schedule)
        db.session.commit()
        return jsonify({"success": True, "message": "Medication schedule deleted"}), HTTPStatus.OK
    except Exception as exc:
        current_app.logger.exception("Failed to delete medication schedule: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to delete schedule"}), HTTPStatus.INTERNAL_SERVER_ERROR


@profile_bp.delete("/medications/<int:medication_id>/")
@jwt_required()
def remove_medication(medication_id: int):
    """Remove a medication from the user's profile."""
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)
    
    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND
    
    try:
        medication = ProfileMedication.query.filter_by(
            id=medication_id,
            profile_id=profile.id
        ).first()
        
        if not medication:
            return jsonify({"error": "Medication not found"}), HTTPStatus.NOT_FOUND
        
        db.session.delete(medication)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Medication removed successfully"
        }), HTTPStatus.OK
        
    except Exception as exc:
        current_app.logger.exception("Failed to remove medication: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to remove medication"}), HTTPStatus.INTERNAL_SERVER_ERROR


def _set_primary_contact(profile_id: int, contact: EmergencyContact) -> None:
    if contact.is_primary:
        EmergencyContact.query.filter(
            EmergencyContact.profile_id == profile_id,
            EmergencyContact.id != contact.id,
            EmergencyContact.is_primary.is_(True),
        ).update({"is_primary": False})
        db.session.flush()


@profile_bp.get("/emergency-contacts/")
@jwt_required()
def list_emergency_contacts():
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    contacts = EmergencyContact.query.filter_by(profile_id=profile.id).order_by(
        EmergencyContact.is_primary.desc(), EmergencyContact.created_at.asc()
    ).all()

    return jsonify({
        "success": True,
        "data": [_serialize_contact(contact) for contact in contacts],
    }), HTTPStatus.OK


@profile_bp.post("/emergency-contacts/")
@jwt_required()
def create_emergency_contact():
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    error = _validate_contact_payload(data)
    if error:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    contact = EmergencyContact(
        profile_id=profile.id,
        name=data["name"].strip(),
        relationship=(data.get("relationship") or "").strip() or None,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        is_primary=bool(data.get("is_primary", False)),
        notes=(data.get("notes") or "").strip() or None,
    )

    try:
        db.session.add(contact)
        db.session.flush()
        _set_primary_contact(profile.id, contact)
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("Failed to create emergency contact: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to create contact"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"success": True, "data": _serialize_contact(contact)}), HTTPStatus.CREATED


@profile_bp.put("/emergency-contacts/<int:contact_id>/")
@jwt_required()
def update_emergency_contact(contact_id: int):
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    contact = EmergencyContact.query.filter_by(id=contact_id, profile_id=profile.id).first()
    if not contact:
        return jsonify({"error": "Emergency contact not found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    merged_payload = {
        "name": data.get("name", contact.name),
        "phone": data.get("phone", contact.phone),
        "email": data.get("email", contact.email),
    }
    error = _validate_contact_payload(merged_payload)
    if error:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    if "name" in data:
        contact.name = str(data["name"]).strip() or contact.name
    if "relationship" in data:
        contact.relationship = (data.get("relationship") or "").strip() or None
    if "phone" in data:
        contact.phone = (data.get("phone") or "").strip() or None
    if "email" in data:
        contact.email = (data.get("email") or "").strip() or None
    if "notes" in data:
        contact.notes = (data.get("notes") or "").strip() or None
    if "is_primary" in data:
        contact.is_primary = bool(data.get("is_primary"))

    try:
        db.session.add(contact)
        db.session.flush()
        _set_primary_contact(profile.id, contact)
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("Failed to update emergency contact: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to update contact"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"success": True, "data": _serialize_contact(contact)}), HTTPStatus.OK


@profile_bp.delete("/emergency-contacts/<int:contact_id>/")
@jwt_required()
def delete_emergency_contact(contact_id: int):
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    contact = EmergencyContact.query.filter_by(id=contact_id, profile_id=profile.id).first()
    if not contact:
        return jsonify({"error": "Emergency contact not found"}), HTTPStatus.NOT_FOUND

    try:
        db.session.delete(contact)
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("Failed to delete emergency contact: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to delete contact"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"success": True, "message": "Emergency contact deleted"}), HTTPStatus.OK


@profile_bp.get("/family-members/")
@jwt_required()
def list_family_members():
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    members = FamilyMember.query.filter_by(profile_id=profile.id).order_by(
        FamilyMember.created_at.asc()
    ).all()

    return jsonify({
        "success": True,
        "data": [_serialize_family_member(member) for member in members],
    }), HTTPStatus.OK


@profile_bp.post("/family-members/")
@jwt_required()
def create_family_member():
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    error = _validate_family_payload(data)
    if error:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    birthdate = data.get("birthdate")
    if birthdate:
        birthdate = datetime.fromisoformat(str(birthdate)).date()

    member = FamilyMember(
        profile_id=profile.id,
        name=data["name"].strip(),
        relationship=data["relationship"].strip(),
        birthdate=birthdate,
        notes=(data.get("notes") or "").strip() or None,
        share_preferences=bool(data.get("share_preferences", False)),
    )

    try:
        db.session.add(member)
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("Failed to create family member: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to create family member"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"success": True, "data": _serialize_family_member(member)}), HTTPStatus.CREATED


@profile_bp.put("/family-members/<int:member_id>/")
@jwt_required()
def update_family_member(member_id: int):
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    member = FamilyMember.query.filter_by(id=member_id, profile_id=profile.id).first()
    if not member:
        return jsonify({"error": "Family member not found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    merged_payload = {
        "name": data.get("name", member.name),
        "relationship": data.get("relationship", member.relationship),
        "birthdate": data.get("birthdate", member.birthdate.isoformat() if member.birthdate else None),
    }
    error = _validate_family_payload(merged_payload)
    if error:
        return jsonify({"error": error}), HTTPStatus.BAD_REQUEST

    if "name" in data:
        member.name = str(data["name"]).strip() or member.name
    if "relationship" in data:
        member.relationship = (data.get("relationship") or "").strip() or member.relationship
    if "birthdate" in data:
        birthdate_raw = data.get("birthdate")
        member.birthdate = datetime.fromisoformat(str(birthdate_raw)).date() if birthdate_raw else None
    if "notes" in data:
        member.notes = (data.get("notes") or "").strip() or None
    if "share_preferences" in data:
        member.share_preferences = bool(data.get("share_preferences"))

    try:
        db.session.add(member)
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("Failed to update family member: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to update family member"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"success": True, "data": _serialize_family_member(member)}), HTTPStatus.OK


@profile_bp.delete("/family-members/<int:member_id>/")
@jwt_required()
def delete_family_member(member_id: int):
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    member = FamilyMember.query.filter_by(id=member_id, profile_id=profile.id).first()
    if not member:
        return jsonify({"error": "Family member not found"}), HTTPStatus.NOT_FOUND

    try:
        db.session.delete(member)
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("Failed to delete family member: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to delete family member"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"success": True, "message": "Family member deleted"}), HTTPStatus.OK


def _is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _anonymize_profile_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = json.loads(json.dumps(payload))

    user_info = sanitized.get("user", {}) or {}
    raw_id = user_info.get("id")
    hashed = hashlib.sha256(str(raw_id).encode("utf-8")).hexdigest()[:12] if raw_id is not None else "anonymous"
    user_info["id"] = f"user-{hashed}"
    user_info["email"] = None
    created = user_info.get("created_at")
    if isinstance(created, str):
        user_info["created_at"] = created[:10]
    sanitized["user"] = user_info

    for index, contact in enumerate(sanitized.get("emergency_contacts", []) or [], start=1):
        contact["name"] = f"Contact {index}"
        contact["phone"] = None
        contact["email"] = None
        if "notes" in contact:
            contact["notes"] = None

    for index, member in enumerate(sanitized.get("family_members", []) or [], start=1):
        member["name"] = f"Family Member {index}"
        if "notes" in member:
            member["notes"] = None

    sanitized["anonymized"] = True
    return sanitized


@profile_bp.get("/export/")
@jwt_required()
def export_profile():
    """Export user's profile and health history as JSON."""
    user_id = get_jwt_identity()
    profile = _ensure_profile(user_id)
    if not profile:
        return jsonify({"error": "User not found"}), HTTPStatus.UNAUTHORIZED
    try:
        user = profile.user
        anonymize = _is_truthy(request.args.get("anonymize"))
        # Build export payload
        allergies = [a.name for a in profile.allergies]
        conditions = [c.name for c in profile.conditions]
        medications = [
            {
                "drug_name": m.drug.name if m.drug else "Unknown",
                "dosage": m.dosage,
                "started_at": m.started_at.isoformat() if m.started_at else None,
                "ended_at": m.ended_at.isoformat() if m.ended_at else None,
                "schedule": _serialize_schedule(m.schedule),
                "reminder": build_reminder_payload(m),
            }
            for m in profile.medications
        ]
        # Health history (recent 50)
        entries = SymptomEntry.query.filter(
            SymptomEntry.profile_id == profile.id
        ).order_by(SymptomEntry.entered_at.desc()).limit(50).all()
        history = []
        for e in entries:
            diags = Diagnosis.query.filter(Diagnosis.symptom_entry_id == e.id).all()
            risk = RiskEvaluation.query.filter(RiskEvaluation.symptom_entry_id == e.id).first()
            severity = SymptomSeverity.query.filter(SymptomSeverity.symptom_entry_id == e.id).first()
            severity_payload = None
            body_systems = []
            if severity:
                factors = list(severity.factors or [])
                body_systems = _body_systems_from_factors(factors)
                severity_payload = {
                    "score": severity.score,
                    "level": severity.level,
                    "factors": factors,
                    "body_systems": body_systems,
                    "recorded_at": severity.created_at.isoformat(),
                }
            history.append({
                "entered_at": e.entered_at.isoformat(),
                "symptoms": e.symptoms,
                "diagnoses": [
                    {"condition": d.condition_name, "probability": d.probability, "triage_level": d.triage_level}
                    for d in diags
                ],
                "risk_evaluation": ({
                    "risk_level": risk.risk_level,
                    "urgency": risk.urgency,
                    "evaluated_at": risk.evaluated_at.isoformat()
                } if risk else None),
                "severity": severity_payload,
                "body_systems": body_systems,
            })
        payload = {
            "user": {"id": user.id, "email": user.email, "created_at": user.created_at.isoformat()},
            "profile": {"age": profile.age, "sex": profile.sex},
            "allergies": allergies,
            "conditions": conditions,
            "medications": medications,
            "health_history": history,
            "emergency_contacts": [
                _serialize_contact(contact)
                for contact in EmergencyContact.query.filter_by(profile_id=profile.id).order_by(
                    EmergencyContact.is_primary.desc(), EmergencyContact.created_at.asc()
                ).all()
            ],
            "family_members": [
                _serialize_family_member(member)
                for member in FamilyMember.query.filter_by(profile_id=profile.id).order_by(
                    FamilyMember.created_at.asc()
                ).all()
            ],
            "exported_at": datetime.utcnow().isoformat() + "Z"
        }
        if anonymize:
            payload = _anonymize_profile_payload(payload)
        else:
            payload["anonymized"] = False
        return jsonify({"success": True, "data": payload}), HTTPStatus.OK
    except Exception as exc:
        current_app.logger.exception("Failed to export profile: %s", exc)
        return jsonify({"error": "Failed to export profile"}), HTTPStatus.INTERNAL_SERVER_ERROR


@profile_bp.get("/reminders/")
@jwt_required()
def get_reminders():
    """List upcoming medication reminders for the current user."""
    user_id = get_jwt_identity()
    profile = _get_user_profile(user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), HTTPStatus.NOT_FOUND

    reminders: List[Dict[str, Any]] = []
    today = datetime.utcnow().date()

    for medication in profile.medications:
        if medication.ended_at and medication.ended_at < today:
            continue
        payload = build_reminder_payload(medication)
        if payload:
            reminders.append(payload)

    return jsonify({
        "success": True,
        "data": {
            "reminders": reminders,
            "count": len(reminders),
        }
    }), HTTPStatus.OK


@profile_bp.get("/health-history/")
@jwt_required()
def get_health_history():
    """Get user's health history with pagination."""
    user_id = get_jwt_identity()
    profile = _ensure_profile(user_id)

    if not profile:
        return jsonify({"error": "User not found"}), HTTPStatus.UNAUTHORIZED
    
    try:
        # Get pagination parameters
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 10)), 50)  # Max 50 per page
        
        # Query health entries
        entries_query = SymptomEntry.query.filter(
            SymptomEntry.profile_id == profile.id
        ).order_by(SymptomEntry.entered_at.desc())
        
        pagination = entries_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        health_history = []
        for entry in pagination.items:
            diagnoses = Diagnosis.query.filter(
                Diagnosis.symptom_entry_id == entry.id
            ).all()
            
            risk_eval = RiskEvaluation.query.filter(
                RiskEvaluation.symptom_entry_id == entry.id
            ).first()
            
            entry_data = {
                "id": entry.id,
                "symptoms": entry.symptoms,
                "entered_at": entry.entered_at.isoformat(),
                "diagnoses": [
                    {
                        "condition": d.condition_name,
                        "probability": d.probability,
                        "triage_level": d.triage_level
                    }
                    for d in diagnoses
                ],
                "risk_evaluation": {
                    "risk_level": risk_eval.risk_level,
                    "urgency": risk_eval.urgency,
                    "evaluated_at": risk_eval.evaluated_at.isoformat()
                } if risk_eval else None
            }
            health_history.append(entry_data)
        
        return jsonify({
            "success": True,
            "data": {
                "entries": health_history,
                "pagination": {
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev
                }
            }
        }), HTTPStatus.OK
        
    except Exception as exc:
        current_app.logger.exception("Failed to get health history: %s", exc)
        return jsonify({"error": "Failed to retrieve health history"}), HTTPStatus.INTERNAL_SERVER_ERROR

@profile_bp.get("/preferences/")
@jwt_required()
def get_preferences_route():
    user_id = get_jwt_identity()
    user = _get_user_by_identity(user_id)
    if not user:
        current_app.logger.warning("Preferences lookup failed: user not found for identity=%r", user_id)
        return jsonify({"error": "User not found"}), HTTPStatus.UNAUTHORIZED

    prefs = _ensure_preferences(user.id)
    return jsonify({"success": True, "data": _serialize_preferences(prefs)}), HTTPStatus.OK


@profile_bp.put("/preferences/")
@jwt_required()
def update_preferences_route():
    user_id = get_jwt_identity()
    user = _get_user_by_identity(user_id)
    if not user:
        current_app.logger.warning("Preferences update failed: user not found for identity=%r", user_id)
        return jsonify({"error": "User not found"}), HTTPStatus.UNAUTHORIZED

    data = request.get_json(silent=True) or {}

    prefs = _ensure_preferences(user.id)

    if "language" in data:
        language = str(data["language"]).lower().strip()
        if language not in _ALLOWED_LANGUAGES:
            return jsonify({"error": "language must be one of: en, de, es, fr, it"}), HTTPStatus.BAD_REQUEST
        prefs.language = language

    def _apply_bool(field: str) -> bool:
        if field not in data:
            return True
        value = data[field]
        if isinstance(value, bool):
            setattr(prefs, field, value)
            return True
        if isinstance(value, str):
            setattr(prefs, field, value.strip().lower() in {"1", "true", "yes"})
            return True
        return False

    if not all(_apply_bool(field) for field in ("notify_email", "notify_push", "notify_sms")):
        return jsonify({"error": "notification fields must be boolean"}), HTTPStatus.BAD_REQUEST

    prefs.updated_at = datetime.utcnow()

    try:
        db.session.add(prefs)
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("Failed to update preferences: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to update preferences"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"success": True, "data": _serialize_preferences(prefs)}), HTTPStatus.OK
