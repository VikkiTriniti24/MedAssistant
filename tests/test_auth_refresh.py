from http import HTTPStatus
from werkzeug.http import parse_cookie


def _apply_refresh_cookie(client, response):
    cookies = parse_cookie(response.headers.get("Set-Cookie", ""))
    refresh = cookies.get("refresh_token")
    if refresh:
        client.set_cookie("refresh_token", refresh)


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
