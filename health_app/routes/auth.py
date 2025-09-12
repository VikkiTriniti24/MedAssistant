# health_app/routes/auth.py
from http import HTTPStatus
from typing import Optional

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .. import db
from ..models import User, Profile

# Blueprint wird in __init__.py unter url_prefix="/auth" registriert
auth_bp = Blueprint("auth", __name__)


def _normalize_email(email: Optional[str]) -> Optional[str]:
    """Trim + lowercase; leere Strings -> None."""
    if not isinstance(email, str):
        return None
    email = email.strip().lower()
    return email or None


@auth_bp.post("/register")
def register():
    """
    Body: {"email": "...", "password": "..."}
    Antwort: {"access_token": "..."} bei Erfolg
    """
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"msg": "email and password required"}), HTTPStatus.BAD_REQUEST

    try:
        # E-Mail muss eindeutig sein
        if User.query.filter_by(email=email).first():
            return jsonify({"msg": "email already registered"}), HTTPStatus.CONFLICT

        # User + leeres Profil anlegen
        user = User(
            email=email,
            hashed_pwd=generate_password_hash(
                password, method="pbkdf2:sha256", salt_length=16
            ),
        )
        db.session.add(user)
        db.session.flush()  # damit user.id vorhanden ist

        profile = Profile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()

        # JWT als String-Identity (Kompatibilität mit flask-jwt-extended)
        token = create_access_token(identity=str(user.id), additional_claims={"role": "user"})
        return jsonify({"access_token": token}), HTTPStatus.OK

    except Exception as exc:
        current_app.logger.exception("register failed: %s", exc)
        db.session.rollback()
        return jsonify({"msg": "internal error"}), HTTPStatus.INTERNAL_SERVER_ERROR


@auth_bp.post("/login")
def login():
    """
    Body: {"email": "...", "password": "..."}
    Antwort: {"access_token": "..."} bei Erfolg
    """
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"msg": "email and password required"}), HTTPStatus.BAD_REQUEST

    try:
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.hashed_pwd, password):
            return jsonify({"msg": "invalid credentials"}), HTTPStatus.UNAUTHORIZED

        token = create_access_token(identity=str(user.id), additional_claims={"role": "user"})
        return jsonify({"access_token": token}), HTTPStatus.OK

    except Exception as exc:
        current_app.logger.exception("login failed: %s", exc)
        return jsonify({"msg": "internal error"}), HTTPStatus.INTERNAL_SERVER_ERROR


@auth_bp.get("/me")
@jwt_required()
def me():
    """
    Einfache Probe: validiert das JWT und liefert die User-ID zurück.
    Frontend kann damit den Login-Zustand prüfen.
    """
    uid = get_jwt_identity()  # string (wie oben erzeugt)
    return jsonify({"user_id": uid}), HTTPStatus.OK
