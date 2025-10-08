from http import HTTPStatus


def _auth_headers_for(client, email="pref@example.com", password="StrongPass123"):
    resp = client.post("/auth/register", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def test_get_preferences_returns_defaults(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    headers = _auth_headers_for(client)

    resp = client.get("/profile/preferences/", headers=headers)
    assert resp.status_code == HTTPStatus.OK
    body = resp.get_json()["data"]
    assert body["language"] == "en"
    assert body["notify_email"] is True
    assert body["notify_push"] is False
    assert body["notify_sms"] is False


def test_update_preferences(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    headers = _auth_headers_for(client, email="prefupdate@example.com")

    payload = {
        "language": "de",
        "notify_email": False,
        "notify_push": True,
    }
    resp = client.put("/profile/preferences/", headers=headers, json=payload)
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()["data"]
    assert data["language"] == "de"
    assert data["notify_email"] is False
    assert data["notify_push"] is True


def test_update_preferences_invalid_language(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    headers = _auth_headers_for(client, email="preffail@example.com")

    resp = client.put("/profile/preferences/", headers=headers, json={"language": "jp"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
