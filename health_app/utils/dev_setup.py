# health_app/utils/dev_setup.py
from typing import Optional, TYPE_CHECKING

from flask import current_app

if TYPE_CHECKING:
    from flask import Flask

from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from .. import db
from ..models import User, Profile


def ensure_dev_db(app: Optional[Flask] = None) -> None:
    """
    In development/testing:
      - legt fehlende Tabellen an
      - legt einen Demo-User + Profil an (demo@example.com / password123)
    Ist idempotent (kann mehrfach gefahrlos aufgerufen werden).
    """
    # App ermitteln
    app = app or current_app
    env = (app.config.get("ENV") or "").lower()
    if env not in {"development", "testing", "dev", "test", ""}:
        return  # in Prod nichts tun

    # Immer im App-Kontext arbeiten
    if app is not current_app._get_current_object():
        ctx = app.app_context()
        ctx.push()
        try:
            _ensure(app)
        finally:
            ctx.pop()
    else:
        _ensure(app)


def _ensure(app):
    inspector = inspect(db.engine)

    # Tabellen anlegen, falls 'users' fehlt (als Sentinel)
    if not inspector.has_table("users"):
        db.create_all()

    # Demo-User seed
    demo_email = "demo@example.com"
    user = User.query.filter_by(email=demo_email).first()
    if not user:
        user = User(
            email=demo_email,
            hashed_pwd=generate_password_hash(
                "password123", method="pbkdf2:sha256", salt_length=16
            ),
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(Profile(user_id=user.id, age=34, sex="female"))
        db.session.commit()
