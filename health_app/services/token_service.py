"""Utility functions to manage refresh token lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask import current_app
from flask_jwt_extended import decode_token

from .. import db
from ..models import RevokedToken


def register_refresh_token(user_id: int, encoded_token: str) -> RevokedToken:
    """Persist metadata for an issued refresh token."""
    decoded = decode_token(encoded_token)
    if decoded.get("type") != "refresh":
        raise ValueError("register_refresh_token expects a refresh token")

    jti = decoded.get("jti")
    if not jti:
        raise ValueError("refresh token contains no jti")

    issued_at = _utc_from_claim(decoded.get("iat")) or datetime.utcnow()
    expires_at = _utc_from_claim(decoded.get("exp"))

    token = RevokedToken.query.filter_by(jti=jti).first()
    if token is None:
        token = RevokedToken(
            user_id=user_id,
            jti=jti,
            token_type=decoded.get("type", "refresh"),
            issued_at=issued_at,
            expires_at=expires_at,
        )
    else:
        token.user_id = user_id
        token.token_type = decoded.get("type", token.token_type)
        token.issued_at = issued_at
        token.expires_at = expires_at
        token.revoked_at = None
        token.revoked_reason = None

    db.session.add(token)
    db.session.commit()
    return token


def revoke_refresh_token(jti: str, user_id: Optional[int] = None, reason: Optional[str] = None) -> RevokedToken:
    """Mark a refresh token as revoked (logout, admin action, etc.)."""
    now = datetime.utcnow()
    token = RevokedToken.query.filter_by(jti=jti).first()

    if token is None:
        token = RevokedToken(
            user_id=user_id,
            jti=jti,
            token_type="refresh",
            revoked_at=now,
            revoked_reason=reason,
        )
    else:
        token.revoked_at = now
        token.revoked_reason = reason
        if user_id and not token.user_id:
            token.user_id = user_id

    db.session.add(token)
    db.session.commit()
    return token


def revoke_user_refresh_tokens(user_id: int, reason: Optional[str] = None) -> int:
    """Revoke all active refresh tokens for a user."""
    now = datetime.utcnow()
    updated = (
        RevokedToken.query.filter_by(user_id=user_id)
        .filter(RevokedToken.revoked_at.is_(None))
        .update({"revoked_at": now, "revoked_reason": reason}, synchronize_session=False)
    )
    db.session.commit()
    return updated


def revoke_all_refresh_tokens(reason: Optional[str] = None) -> int:
    """Revoke every active refresh token in the system."""
    now = datetime.utcnow()
    updated = (
        RevokedToken.query.filter(RevokedToken.revoked_at.is_(None))
        .update({"revoked_at": now, "revoked_reason": reason}, synchronize_session=False)
    )
    db.session.commit()
    return updated


def is_refresh_token_revoked(jti: str) -> bool:
    token = RevokedToken.query.filter_by(jti=jti).first()
    if token is None:
        # Unknown tokens are considered revoked to prevent replay of legacy tokens.
        return True
    if token.revoked_at is not None:
        return True
    if token.expires_at and token.expires_at < datetime.utcnow():
        return True
    return False


def _utc_from_claim(value: Optional[int]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(value))
    except Exception as exc:  # pragma: no cover - defensive logging only
        current_app.logger.warning("Failed to parse JWT claim timestamp: %s", exc)
        return None
