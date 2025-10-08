from http import HTTPStatus

from flask_jwt_extended import decode_token
from werkzeug.http import parse_cookie

from health_app.models import RevokedToken


def _apply_refresh_cookie(client, response):
    cookies = parse_cookie(response.headers.get("Set-Cookie", ""))
    refresh = cookies.get("refresh_token")
    if refresh:
        client.set_cookie("refresh_token", refresh)
    return refresh


def test_refresh_flow_sets_cookie(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    resp = client.post("/auth/register", json={"email": "refresh@example.com", "password": "StrongPass123"})
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()
    assert "access_token" in data

    _apply_refresh_cookie(client, resp)

    refresh_resp = client.post("/auth/refresh")
    assert refresh_resp.status_code == HTTPStatus.OK
    assert "access_token" in refresh_resp.get_json()


def test_refresh_requires_active_account(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    reg = client.post("/auth/register", json={"email": "inactive@example.com", "password": "StrongPass123"})
    token = reg.get_json()["access_token"]

    _apply_refresh_cookie(client, reg)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    client.delete("/auth/account", headers=headers, json={"password": "StrongPass123"})

    resp = client.post("/auth/refresh")
    assert resp.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}


def test_refresh_token_is_recorded(app, client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    resp = client.post("/auth/register", json={"email": "record@example.com", "password": "StrongPass123"})
    refresh_token = _apply_refresh_cookie(client, resp)
    assert refresh_token

    decoded = decode_token(refresh_token)
    jti = decoded["jti"]

    with app.app_context():
        stored = RevokedToken.query.filter_by(jti=jti).first()
        assert stored is not None
        assert stored.revoked_at is None
        assert stored.user_id is not None


def test_logout_revokes_refresh_token(app, client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    resp = client.post("/auth/register", json={"email": "logout@example.com", "password": "StrongPass123"})
    refresh_token = _apply_refresh_cookie(client, resp)
    assert refresh_token

    refresh_resp = client.post("/auth/refresh")
    assert refresh_resp.status_code == HTTPStatus.OK

    logout_resp = client.post("/auth/logout")
    assert logout_resp.status_code == HTTPStatus.OK

    blocked = client.post("/auth/refresh")
    assert blocked.status_code == HTTPStatus.UNAUTHORIZED

    decoded = decode_token(refresh_token)
    jti = decoded["jti"]
    with app.app_context():
        stored = RevokedToken.query.filter_by(jti=jti).first()
        assert stored is not None
        assert stored.revoked_at is not None


def test_password_reset_revokes_refresh_tokens(app, client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)

    captured = {}

    def fake_send(email, token, expires_at, language=None):
        captured["token"] = token

    monkeypatch.setattr("health_app.routes.auth.send_password_reset_email", fake_send)

    email = "reset-tokens@example.com"
    resp = client.post("/auth/register", json={"email": email, "password": "StrongPass123"})
    refresh_token = _apply_refresh_cookie(client, resp)
    assert refresh_token

    assert client.post("/auth/refresh").status_code == HTTPStatus.OK

    client.post("/auth/reset/request", json={"email": email})
    reset_token = captured.get("token")
    assert reset_token

    new_password = "NewPass123"
    confirm = client.post(
        "/auth/reset/confirm",
        json={"token": reset_token, "password": new_password},
    )
    assert confirm.status_code == HTTPStatus.OK

    decoded = decode_token(refresh_token)
    jti = decoded["jti"]

    with app.app_context():
        record = RevokedToken.query.filter_by(jti=jti).first()
        assert record is not None
        assert record.revoked_at is not None

    blocked = client.post("/auth/refresh")
    assert blocked.status_code == HTTPStatus.UNAUTHORIZED

    # User can log in with new password and receives a fresh refresh token
    login_resp = client.post("/auth/login", json={"email": email, "password": new_password})
    assert login_resp.status_code == HTTPStatus.OK
    new_refresh = _apply_refresh_cookie(client, login_resp)
    assert new_refresh
    assert client.post("/auth/refresh").status_code == HTTPStatus.OK
