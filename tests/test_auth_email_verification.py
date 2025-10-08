from http import HTTPStatus
from datetime import datetime, timedelta

from health_app import db
from health_app.models import EmailVerificationToken, User


def test_email_verification_flow(client, register_user, monkeypatch):
    sent = {}

    def fake_send(email, token, expires_at, *, language=None):
        sent["email"] = email
        sent["token"] = token

    monkeypatch.setattr("health_app.routes.auth.send_email_verification", fake_send)

    email, _, register_resp = register_user(email="verify@example.com", password="StrongPass123")
    token = register_resp.get_json().get("verification_token")
    assert token is not None
    assert sent["email"] == email
    assert sent["token"] == token

    resp = client.post("/auth/verify/confirm", json={"token": token})
    assert resp.status_code == HTTPStatus.OK

    login_resp = client.post("/auth/login", json={"email": email, "password": "StrongPass123"})
    assert login_resp.status_code == HTTPStatus.OK
    assert login_resp.get_json()["email_verified"] is True


def test_verification_request_requires_auth(client, register_user, monkeypatch, access_token):
    sent = {}
    monkeypatch.setattr(
        "health_app.routes.auth.send_email_verification",
        lambda email, token, expires_at, *, language=None: sent.update(token=token),
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    resp = client.post("/auth/verify/request", headers=headers)
    assert resp.status_code == HTTPStatus.OK
    assert "token" in resp.get_json()


def test_verification_token_invalid(client, register_user):
    client.post("/auth/login", json={"email": "verify@example.com", "password": "StrongPass123"})
    resp = client.post("/auth/verify/confirm", json={"token": "invalid"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_verification_expired_token(client, register_user, app):
    email, _, _ = register_user(email="expiredv@example.com", password="StrongPass123")

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        token = EmailVerificationToken(
            user_id=user.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db.session.add(token)
        db.session.commit()

    resp = client.post("/auth/verify/confirm", json={"token": "expired_token"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
