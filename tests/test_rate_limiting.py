from http import HTTPStatus

import pytest
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from health_app import db
from health_app.models import Profile, User


pytestmark = pytest.mark.slow


def test_login_rate_limit_enforced(app, client):
    with app.app_context():
        db.drop_all()
        db.create_all()

    app.config.update(
        RATE_LIMIT_AUTH_LIMIT=3,
        RATE_LIMIT_AUTH_WINDOW=60,
        RATE_LIMITING_DISABLED=False,
    )

    creds = {"email": "rate@example.com", "password": "StrongPass123"}
    assert client.post("/auth/register", json=creds).status_code == HTTPStatus.OK

    statuses = [client.post("/auth/login", json=creds).status_code for _ in range(3)]
    assert statuses.count(HTTPStatus.OK) == 3, statuses

    blocked = client.post("/auth/login", json=creds)
    assert blocked.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert "Retry-After" in blocked.headers
    body = blocked.get_json()
    assert body["msg"] == "too many requests"


def test_register_rate_limit_blocks_spam(app, client):
    with app.app_context():
        db.drop_all()
        db.create_all()

    app.config.update(
        RATE_LIMIT_AUTH_LIMIT=2,
        RATE_LIMIT_AUTH_WINDOW=60,
        RATE_LIMITING_DISABLED=False,
    )

    for idx in range(2):
        payload = {"email": f"many{idx}@example.com", "password": "StrongPass123"}
        assert client.post("/auth/register", json=payload).status_code in (HTTPStatus.OK, HTTPStatus.CREATED)

    spam = client.post(
        "/auth/register",
        json={"email": "blocked@example.com", "password": "StrongPass123"},
    )
    assert spam.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_health_check_rate_limit_blocks_user(app, client):
    with app.app_context():
        db.drop_all()
        db.create_all()

    app.config.update(
        RATE_LIMIT_HEALTH_CHECK_LIMIT=2,
        RATE_LIMIT_HEALTH_CHECK_WINDOW=60,
        RATE_LIMITING_DISABLED=False,
    )

    creds = {"email": "hc@example.com", "password": "StrongPass123"}
    assert client.post("/auth/register", json=creds).status_code == HTTPStatus.OK
    token_resp = client.post("/auth/login", json=creds)
    token = token_resp.get_json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {"symptoms": "mild cough"}
    for _ in range(2):
        assert client.post("/health-check/", headers=headers, json=payload).status_code == HTTPStatus.OK

    blocked = client.post("/health-check/", headers=headers, json=payload)
    assert blocked.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_admin_multiplier_allows_additional_requests(app, client):
    with app.app_context():
        db.drop_all()
        db.create_all()

    app.config.update(
        RATE_LIMIT_HEALTH_CHECK_LIMIT=1,
        RATE_LIMIT_HEALTH_CHECK_WINDOW=60,
        RATE_LIMIT_ROLE_MULTIPLIER_ADMIN=6,
        RATE_LIMITING_DISABLED=False,
    )

    with app.app_context():
        admin = User(
            email="admin@example.com",
            hashed_pwd=generate_password_hash("AdminPass123", method="pbkdf2:sha256", salt_length=16),
        )
        db.session.add(admin)
        db.session.flush()
        db.session.add(Profile(user_id=admin.id))
        db.session.commit()
        token = create_access_token(identity=str(admin.id), additional_claims={"role": "admin"})

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"symptoms": "monitor"}

    allowed = max(
        1,
        int(
            round(
                app.config["RATE_LIMIT_HEALTH_CHECK_LIMIT"]
                * app.config["RATE_LIMIT_ROLE_MULTIPLIER_ADMIN"]
            )
        ),
    )

    for _ in range(allowed):
        assert client.post("/health-check/", headers=headers, json=payload).status_code == HTTPStatus.OK

    blocked = client.post("/health-check/", headers=headers, json=payload)
    assert blocked.status_code == HTTPStatus.TOO_MANY_REQUESTS
