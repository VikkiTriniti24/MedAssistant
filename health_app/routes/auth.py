# health_app/routes/auth.py
from datetime import datetime, timedelta
from http import HTTPStatus
from string import ascii_letters, digits
from typing import Optional, List
import secrets

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .. import db
from ..models import (
    User,
    Profile,
    PasswordResetToken,
    EmailVerificationToken,
    MFAConfig,
    MFABackupCode,
)
from ..utils.rate_limit import enforce_rate_limit
from ..utils.email import send_password_reset_email, send_email_verification
from ..utils.i18n import resolve_user_language
from ..utils.totp import generate_secret as totp_generate_secret, verify_totp, build_otpauth_uri
from ..services.token_service import (
    register_refresh_token,
    revoke_refresh_token,
    revoke_user_refresh_tokens,
)

# Blueprint wird in __init__.py unter url_prefix="/auth" registriert
auth_bp = Blueprint("auth", __name__)


def _normalize_email(email: Optional[str]) -> Optional[str]:
    """Trim + lowercase; leere Strings -> None."""
    if not isinstance(email, str):
        return None
    email = email.strip().lower()
    return email or None


def _validate_password(password: Optional[str]) -> Optional[str]:
    """Simple password policy: >=8 chars, with letters and digits."""
    if not isinstance(password, str) or not password:
        return "password required"
    if len(password) < 8:
        return "password must be at least 8 characters long"
    has_letter = any(ch in ascii_letters for ch in password)
    has_digit = any(ch in digits for ch in password)
    if not has_letter or not has_digit:
        return "password must include letters and numbers"
    return None


def _resolve_user(identity) -> Optional[User]:
    if identity is None:
        return None
    try:
        return User.query.filter_by(id=int(identity)).first()
    except (TypeError, ValueError):
        pass
    normalized = str(identity).strip().lower()
    if not normalized:
        return None
    return User.query.filter_by(email=normalized).first()


def _is_account_locked(user: Optional[User]) -> bool:
    if not user or not getattr(user, "locked_until", None):
        return False
    return user.locked_until > datetime.utcnow()


def _record_failed_login(user: Optional[User]) -> Optional[datetime]:
    if not user:
        return None

    attempts = (user.failed_login_attempts or 0) + 1
    user.failed_login_attempts = attempts

    max_attempts = int(current_app.config.get("LOGIN_MAX_ATTEMPTS", 5))
    lock_minutes = int(current_app.config.get("LOGIN_LOCKOUT_MINUTES", 15))

    if attempts >= max_attempts:
        user.failed_login_attempts = 0
        user.locked_until = datetime.utcnow() + timedelta(minutes=max(1, lock_minutes))
        db.session.commit()
        return user.locked_until

    db.session.commit()
    return None


def _issue_reset_token(user: User) -> PasswordResetToken:
    token = secrets.token_urlsafe(32)
    minutes = int(current_app.config.get("PASSWORD_RESET_TOKEN_MINUTES", 30))
    expires_at = datetime.utcnow() + timedelta(minutes=max(1, minutes))
    reset = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
    db.session.add(reset)
    db.session.commit()
    return reset


def _issue_email_verification(user: User) -> EmailVerificationToken:
    token = secrets.token_urlsafe(32)
    minutes = int(current_app.config.get("EMAIL_VERIFICATION_TOKEN_MINUTES", 60))
    expires_at = datetime.utcnow() + timedelta(minutes=max(5, minutes))
    verification = EmailVerificationToken(user_id=user.id, token=token, expires_at=expires_at)
    db.session.add(verification)
    db.session.commit()
    return verification


def _ensure_mfa_config(user: User) -> MFAConfig:
    config = MFAConfig.query.filter_by(user_id=user.id).first()
    if config:
        return config
    config = MFAConfig(user_id=user.id, secret=totp_generate_secret(), enabled=False)
    db.session.add(config)
    db.session.commit()
    return config


def _generate_backup_codes(user: User, count: int = 10) -> List[str]:
    MFABackupCode.query.filter_by(user_id=user.id, used_at=None).delete(synchronize_session=False)
    codes: list[str] = []
    for _ in range(max(1, count)):
        raw = secrets.token_hex(4)
        code_hash = generate_password_hash(raw, method="pbkdf2:sha256", salt_length=12)
        db.session.add(MFABackupCode(user_id=user.id, code_hash=code_hash))
        codes.append(raw)
    db.session.commit()
    return codes


@auth_bp.post("/register")
def register():
    """
    Body: {"email": "...", "password": "..."}
    Antwort: {"access_token": "..."} bei Erfolg
    """
    data = request.get_json(silent=True) or {}

    rl_response = enforce_rate_limit("auth-register")
    if rl_response is not None:
        return rl_response
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""
    _mfa_code = str(data.get("mfa_code") or "").strip()  # optional eingereicht, derzeit ungenutzt

    if not email:
        return jsonify({"msg": "email and password required"}), HTTPStatus.BAD_REQUEST

    pwd_error = _validate_password(password)
    if pwd_error:
        return jsonify({"msg": pwd_error}), HTTPStatus.BAD_REQUEST

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

        if not Profile.query.filter_by(user_id=user.id).first():
            db.session.add(Profile(user_id=user.id))
        db.session.commit()

        verification_token = None
        try:
            verification = _issue_email_verification(user)
            verification_token = verification.token
            language = resolve_user_language(user)
            send_email_verification(
                user.email,
                verification.token,
                verification.expires_at,
                language=language,
            )
        except Exception as exc:
            current_app.logger.warning("Failed to send verification email: %s", exc)

        access_token = create_access_token(identity=str(user.id), additional_claims={"role": "user"})
        refresh_token = create_refresh_token(identity=str(user.id))

        register_refresh_token(user.id, refresh_token)

        resp = jsonify({
            "access_token": access_token,
            "verification_token": verification_token,
        })
        set_refresh_cookies(resp, refresh_token)
        return resp, HTTPStatus.OK

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
    mfa_code = str(data.get("mfa_code") or "").strip()
    backup_code = str(data.get("backup_code") or "").strip()

    rl_response = enforce_rate_limit("auth-login")
    if rl_response is not None:
        return rl_response

    if not email or not password:
        return jsonify({"msg": "email and password required"}), HTTPStatus.BAD_REQUEST

    try:
        user = User.query.filter_by(email=email).first()
        if _is_account_locked(user):
            locked_until = user.locked_until.isoformat() if user and user.locked_until else None
            return (
                jsonify({"msg": "account locked", "locked_until": locked_until}),
                HTTPStatus.LOCKED,
            )

        if not user or not check_password_hash(user.hashed_pwd, password):
            locked_until = _record_failed_login(user)
            if locked_until:
                return (
                    jsonify({"msg": "account locked", "locked_until": locked_until.isoformat()}),
                    HTTPStatus.LOCKED,
                )
            return jsonify({"msg": "invalid credentials"}), HTTPStatus.UNAUTHORIZED

        if not getattr(user, "is_active", True):
            return jsonify({"msg": "account deactivated"}), HTTPStatus.FORBIDDEN

        config = getattr(user, "mfa", None)
        if config and config.enabled:
            if not mfa_code and not backup_code:
                return jsonify({"msg": "mfa required", "mfa_required": True}), HTTPStatus.UNAUTHORIZED

            mfa_valid = False
            _used_backup = None  # aktuell ungenutzt, aber behalten

            if mfa_code:
                mfa_valid = verify_totp(config.secret, mfa_code)
                if not mfa_valid:
                    locked_until = _record_failed_login(user)
                    if locked_until:
                        return (
                            jsonify({"msg": "account locked", "locked_until": locked_until.isoformat()}),
                            HTTPStatus.LOCKED,
                        )
                    return jsonify({"msg": "invalid mfa code"}), HTTPStatus.UNAUTHORIZED
            elif backup_code:
                codes = MFABackupCode.query.filter_by(user_id=user.id, used_at=None).all()
                for candidate in codes:
                    if check_password_hash(candidate.code_hash, backup_code):
                        candidate.used_at = datetime.utcnow()
                        db.session.add(candidate)
                        mfa_valid = True
                        _used_backup = candidate  # aktuell ungenutzt, aber behalten
                        break
                if not mfa_valid:
                    locked_until = _record_failed_login(user)
                    if locked_until:
                        return (
                            jsonify({"msg": "account locked", "locked_until": locked_until.isoformat()}),
                            HTTPStatus.LOCKED,
                        )
                    return jsonify({"msg": "invalid mfa backup code"}), HTTPStatus.UNAUTHORIZED

        access_token = create_access_token(identity=str(user.id), additional_claims={"role": "user"})
        refresh_token = create_refresh_token(identity=str(user.id))

        user.failed_login_attempts = 0
        user.locked_until = None

        register_refresh_token(user.id, refresh_token)

        resp = jsonify({
            "access_token": access_token,
            "email_verified": bool(getattr(user, "email_verified", False)),
        })
        set_refresh_cookies(resp, refresh_token)
        return resp, HTTPStatus.OK

    except Exception as exc:
        current_app.logger.exception("login failed: %s", exc)
        return jsonify({"msg": "internal error"}), HTTPStatus.INTERNAL_SERVER_ERROR


@auth_bp.post("/reset/request")
def request_password_reset():
    data = request.get_json(silent=True) or {}

    rl_response = enforce_rate_limit("auth-reset-request")
    if rl_response is not None:
        return rl_response

    email = _normalize_email(data.get("email"))
    if not email:
        return jsonify({"msg": "email required"}), HTTPStatus.BAD_REQUEST

    user = User.query.filter_by(email=email).first()
    token_value = None
    if user:
        try:
            reset = _issue_reset_token(user)
            token_value = reset.token
            try:
                language = resolve_user_language(user)
                send_password_reset_email(
                    user.email,
                    reset.token,
                    reset.expires_at,
                    language=language,
                )
            except Exception as email_exc:
                current_app.logger.warning("Password reset email failed: %s", email_exc)
        except Exception as exc:
            current_app.logger.exception("reset token generation failed: %s", exc)
            db.session.rollback()

    response = {"msg": "If the account exists, a reset token has been issued."}
    if token_value:
        response["reset_token"] = token_value
        response["expires_at"] = reset.expires_at.isoformat()
    return jsonify(response), HTTPStatus.OK


@auth_bp.post("/verify/request")
@jwt_required()
def request_email_verification():
    user_id = get_jwt_identity()
    user = User.query.filter_by(id=int(user_id)).first()
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND

    if getattr(user, "email_verified", False):
        return jsonify({"msg": "email already verified"}), HTTPStatus.OK

    rl_response = enforce_rate_limit("auth-verify-request")
    if rl_response is not None:
        return rl_response

    try:
        verification = _issue_email_verification(user)
        language = resolve_user_language(user)
        send_email_verification(
            user.email,
            verification.token,
            verification.expires_at,
            language=language,
        )
        resp = {
            "msg": "verification email sent",
            "token": verification.token,
        }
        return jsonify(resp), HTTPStatus.OK
    except Exception as exc:
        current_app.logger.exception("verification email failed: %s", exc)
        db.session.rollback()
        return jsonify({"msg": "internal error"}), HTTPStatus.INTERNAL_SERVER_ERROR


@auth_bp.post("/verify/confirm")
def confirm_email_verification():
    data = request.get_json(silent=True) or {}
    token_str = (data.get("token") or "").strip()

    if not token_str:
        return jsonify({"msg": "token required"}), HTTPStatus.BAD_REQUEST

    verification = EmailVerificationToken.query.filter_by(token=token_str).first()
    if not verification or verification.used_at is not None or verification.expires_at < datetime.utcnow():
        return jsonify({"msg": "invalid or expired token"}), HTTPStatus.BAD_REQUEST

    user = User.query.filter_by(id=verification.user_id).first()
    if not user:
        return jsonify({"msg": "invalid token"}), HTTPStatus.BAD_REQUEST

    try:
        setattr(user, "email_verified", True)
        setattr(user, "is_active", True)
        verification.used_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"msg": "email verified"}), HTTPStatus.OK
    except Exception as exc:
        current_app.logger.exception("verify email failed: %s", exc)
        db.session.rollback()
        return jsonify({"msg": "internal error"}), HTTPStatus.INTERNAL_SERVER_ERROR


@auth_bp.post("/mfa/setup")
@jwt_required()
def mfa_setup():
    user_id = get_jwt_identity()
    user = _resolve_user(user_id)
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND

    rl_response = enforce_rate_limit("auth-mfa-setup")
    if rl_response is not None:
        return rl_response

    try:
        config = _ensure_mfa_config(user)
        config.secret = totp_generate_secret()
        config.enabled = False
        config.confirmed_at = None
        config.updated_at = datetime.utcnow()
        db.session.add(config)
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("mfa setup failed: %s", exc)
        db.session.rollback()
        return jsonify({"msg": "internal error"}), HTTPStatus.INTERNAL_SERVER_ERROR

    uri = build_otpauth_uri(config.secret, user.email)
    return jsonify({
        "secret": config.secret,
        "otpauth_uri": uri,
    }), HTTPStatus.OK


@auth_bp.post("/mfa/confirm")
@jwt_required()
def mfa_confirm():
    user_id = get_jwt_identity()
    user = _resolve_user(user_id)
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    code = str(data.get("code") or "").strip()

    if not code:
        return jsonify({"msg": "code required"}), HTTPStatus.BAD_REQUEST

    config = _ensure_mfa_config(user)

    rl_response = enforce_rate_limit("auth-mfa-confirm")
    if rl_response is not None:
        return rl_response

    if not verify_totp(config.secret, code):
        return jsonify({"msg": "invalid mfa code"}), HTTPStatus.UNAUTHORIZED

    config.enabled = True
    config.confirmed_at = datetime.utcnow()
    config.updated_at = datetime.utcnow()
    db.session.add(config)
    db.session.commit()

    backup_codes = _generate_backup_codes(user)

    return jsonify({"msg": "mfa enabled", "backup_codes": backup_codes}), HTTPStatus.OK


@auth_bp.post("/mfa/disable")
@jwt_required()
def mfa_disable():
    user_id = get_jwt_identity()
    user = _resolve_user(user_id)
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    code = str(data.get("code") or "").strip()
    password = data.get("password")

    config = user.mfa
    if not config or not config.enabled:
        return jsonify({"msg": "mfa not enabled"}), HTTPStatus.OK

    rl_response = enforce_rate_limit("auth-mfa-disable")
    if rl_response is not None:
        return rl_response

    if code:
        valid = verify_totp(config.secret, code)
    elif password:
        valid = check_password_hash(user.hashed_pwd, password)
    else:
        valid = False

    if not valid:
        return jsonify({"msg": "invalid credentials"}), HTTPStatus.UNAUTHORIZED

    config.enabled = False
    config.updated_at = datetime.utcnow()
    db.session.add(config)
    MFABackupCode.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    db.session.commit()

    return jsonify({"msg": "mfa disabled"}), HTTPStatus.OK


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh_access_token():
    user_id = get_jwt_identity()
    user = User.query.filter_by(id=int(user_id)).first()
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND
    if not getattr(user, "is_active", True):
        return jsonify({"msg": "account deactivated"}), HTTPStatus.FORBIDDEN

    access_token = create_access_token(identity=str(user.id), additional_claims={"role": "user"})
    return jsonify({
        "access_token": access_token,
        "email_verified": bool(getattr(user, "email_verified", False)),
    }), HTTPStatus.OK


@auth_bp.post("/logout")
@jwt_required(refresh=True)
def logout():
    payload = get_jwt()
    jti = payload.get("jti")
    identity = get_jwt_identity()

    if not jti:
        return jsonify({"msg": "token missing jti"}), HTTPStatus.BAD_REQUEST

    try:
        revoke_refresh_token(jti, user_id=int(identity) if identity is not None else None, reason="logout")
    except Exception as exc:
        current_app.logger.exception("logout failed: %s", exc)
        return jsonify({"msg": "internal error"}), HTTPStatus.INTERNAL_SERVER_ERROR

    resp = jsonify({"msg": "logout successful"})
    unset_jwt_cookies(resp)
    return resp, HTTPStatus.OK


@auth_bp.post("/reset/confirm")
def confirm_password_reset():
    data = request.get_json(silent=True) or {}

    rl_response = enforce_rate_limit("auth-reset-confirm")
    if rl_response is not None:
        return rl_response

    token_str = data.get("token")
    new_password = data.get("password")

    if not token_str or not isinstance(token_str, str):
        return jsonify({"msg": "token required"}), HTTPStatus.BAD_REQUEST

    pwd_error = _validate_password(new_password)
    if pwd_error:
        return jsonify({"msg": pwd_error}), HTTPStatus.BAD_REQUEST

    reset = PasswordResetToken.query.filter_by(token=token_str).first()
    if not reset:
        return jsonify({"msg": "invalid or expired token"}), HTTPStatus.BAD_REQUEST

    if reset.used_at is not None or reset.expires_at < datetime.utcnow():
        return jsonify({"msg": "invalid or expired token"}), HTTPStatus.BAD_REQUEST

    user = User.query.filter_by(id=reset.user_id).first()
    if not user:
        return jsonify({"msg": "invalid token"}), HTTPStatus.BAD_REQUEST

    try:
        user.hashed_pwd = generate_password_hash(
            new_password, method="pbkdf2:sha256", salt_length=16
        )
        reset.used_at = datetime.utcnow()
        revoke_user_refresh_tokens(user.id, reason="password-reset")
        return jsonify({"msg": "password updated"}), HTTPStatus.OK
    except Exception as exc:
        current_app.logger.exception("password reset failed: %s", exc)
        db.session.rollback()
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
@auth_bp.delete("/account")
@jwt_required()
def deactivate_account():
    data = request.get_json(silent=True) or {}
    password = data.get("password")
    hard_delete = bool(data.get("hard_delete", False))

    if not password:
        return jsonify({"msg": "password required"}), HTTPStatus.BAD_REQUEST

    user_id = get_jwt_identity()
    user = User.query.filter_by(id=int(user_id)).first()
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND

    if not check_password_hash(user.hashed_pwd, password):
        return jsonify({"msg": "invalid credentials"}), HTTPStatus.UNAUTHORIZED

    try:
        if hard_delete:
            db.session.delete(user)
        else:
            setattr(user, "is_active", False)
            db.session.add(user)
        db.session.commit()
        resp = jsonify({"msg": "account deactivated" if not hard_delete else "account deleted"})
        unset_jwt_cookies(resp)
        return resp, HTTPStatus.OK
    except Exception as exc:
        current_app.logger.exception("account deactivation failed: %s", exc)
        db.session.rollback()
        return jsonify({"msg": "internal error"}), HTTPStatus.INTERNAL_SERVER_ERROR


@auth_bp.post("/reactivate")
def reactivate_account():
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get("email"))
    password = data.get("password")

    if not email or not password:
        return jsonify({"msg": "email and password required"}), HTTPStatus.BAD_REQUEST

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.hashed_pwd, password):
        return jsonify({"msg": "invalid credentials"}), HTTPStatus.UNAUTHORIZED

    try:
        setattr(user, "is_active", True)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={"role": "user"})
        return jsonify({
            "access_token": token,
            "email_verified": bool(getattr(user, "email_verified", False)),
        }), HTTPStatus.OK
    except Exception as exc:
        current_app.logger.exception("reactivate failed: %s", exc)
        db.session.rollback()
        return jsonify({"msg": "internal error"}), HTTPStatus.INTERNAL_SERVER_ERROR
