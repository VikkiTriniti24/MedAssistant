# root-level conftest.py to support tests outside the tests/ package
import os
import pytest
from pathlib import Path

from health_app import create_app, db


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Create an app per test with isolated SQLite DB (root-level tests)."""
    monkeypatch.setenv("AI_STUB", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    app = create_app()
    db_path = Path(tmp_path) / "test.db"

    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY="test-jwt",
        VERSION="test",
        ENV="testing",
    )

    # Ensure AI service runs in stub mode during tests
    try:
        import health_app.services.ai_service as ai
        monkeypatch.setattr(ai, "chat_raw", lambda *a, **k: "[mocked ai reply]")
        monkeypatch.setattr(
            ai,
            "chat_json",
            lambda *a, **k: {
                "diagnoses": [
                    {
                        "condition": "Mock Condition",
                        "probability": 0.5,
                        "triage": "medium",
                    }
                ],
                "risk_evaluation": {"risk_level": "low", "urgency": "self-care"},
                "recommendations": ["Rest", "Hydrate"],
            },
        )
        monkeypatch.setattr(ai, "is_stub_mode", lambda: True)
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
def register_user(client):
    def _register(email="test@example.com", password="password123"):
        res = client.post("/auth/register", json={"email": email, "password": password})
        return email, password, res
    return _register


@pytest.fixture()
def access_token(client, register_user):
    email, password, _ = register_user()
    resp = client.post("/auth/login", json={"email": email, "password": password})
    data = resp.get_json() or {}
    return data.get("access_token")


@pytest.fixture()
def token(access_token):
    return access_token





