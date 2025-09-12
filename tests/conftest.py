# tests/conftest.py
import os
import json
import pytest
from pathlib import Path

from health_app import create_app, db

@pytest.fixture(scope="session")
def app_root():
    # Repo-Root bestimmen (nützlich für Pfade)
    return Path(__file__).resolve().parents[1]

@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Create an app per test with isolated SQLite DB."""
    app = create_app()
    db_path = Path(tmp_path) / "test.db"

    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY="test-jwt",     # Test-Secret
        VERSION="test",
        ENV="testing",
    )

    # Optional: AI-Service stumm schalten, falls /chat/ getestet wird
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")  # verhindert asserts in libs
    try:
        import health_app.services.ai_service as ai
        monkeypatch.setattr(ai, "chat_raw", lambda *a, **k: "[mocked ai reply]")
    except Exception:
        pass

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def runner(app):
    return app.test_cli_runner()

# ---------- Auth-Helper ----------

@pytest.fixture()
def register_user(client):
    """Registers a user; returns (email, password)."""
    def _register(email="test@example.com", password="password123"):
        res = client.post("/auth/register", json={"email": email, "password": password})
        return email, password, res
    return _register

@pytest.fixture()
def access_token(client, register_user):
    """Creates a user and returns a fresh JWT access token."""
    email, password, _ = register_user()
    resp = client.post("/auth/login", json={"email": email, "password": password})
    data = resp.get_json() or {}
    return data.get("access_token")

@pytest.fixture()
def auth_headers(access_token):
    """JSON headers incl. Bearer token."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
