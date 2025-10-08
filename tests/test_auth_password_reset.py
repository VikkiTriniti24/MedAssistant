from http import HTTPStatus
from datetime import datetime, timedelta

from health_app import db
from health_app.models import PasswordResetToken, User


def test_password_reset_flow(client, register_user, monkeypatch):
    sent = {}

    def fake_send(email, token, expires_at, *, language=None):
        sent["email"] = email
        sent["token"] = token

    monkeypatch.setattr("health_app.routes.auth.send_password_reset_email", fake_send)

    email, old_password, _ = register_user(email="reset@example.com", password="OldPass123")

    # request reset
    resp = client.post("/auth/reset/request", json={"email": email})
    assert resp.status_code == HTTPStatus.OK
    body = resp.get_json()
    token = body.get("reset_token")
    assert token is not None
    assert sent.get("email") == email
    assert sent.get("token") == token

    # confirm reset
    new_password = "NewPass123"
    resp = client.post(
        "/auth/reset/confirm",
        json={"token": token, "password": new_password},
    )
    assert resp.status_code == HTTPStatus.OK

    # old password should fail
    login_old = client.post("/auth/login", json={"email": email, "password": old_password})
    assert login_old.status_code == HTTPStatus.UNAUTHORIZED

    # new password works
    login_new = client.post("/auth/login", json={"email": email, "password": new_password})
    assert login_new.status_code == HTTPStatus.OK


def test_reset_token_invalid_or_expired(client, register_user, app):
    email, _, _ = register_user(email="expired@example.com", password="GoodPass123")

    # create token manually
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        token = PasswordResetToken(
            user_id=user.id,
            token="expired",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db.session.add(token)
        db.session.commit()

    # expired
    resp = client.post("/auth/reset/confirm", json={"token": "expired", "password": "Another123"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST

    # invalid token
    resp = client.post("/auth/reset/confirm", json={"token": "nope", "password": "Another123"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_reset_request_missing_email(client):
    resp = client.post("/auth/reset/request", json={})
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_reset_confirm_requires_strong_password(client, register_user, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_password_reset_email", lambda *a, **k: None)
    email, _, _ = register_user(email="weakreset@example.com", password="Strong123")
    token_resp = client.post("/auth/reset/request", json={"email": email})
    token = token_resp.get_json()["reset_token"]

    resp = client.post("/auth/reset/confirm", json={"token": token, "password": "short"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
