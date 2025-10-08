from http import HTTPStatus


def _register_and_get_token(client, email="account@example.com", password="StrongPass123"):
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code in (HTTPStatus.OK, HTTPStatus.CREATED)
    data = resp.get_json()
    token = data.get("access_token")
    assert token, "expected register to return access token"
    return email, password, token


def test_soft_deactivate_and_reactivate(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    email, password, token = _register_and_get_token(client, email="soft@example.com")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = client.delete("/auth/account", headers=headers, json={"password": password})
    assert resp.status_code == HTTPStatus.OK

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == HTTPStatus.FORBIDDEN

    reactivate = client.post(
        "/auth/reactivate",
        json={"email": email, "password": password},
    )
    assert reactivate.status_code == HTTPStatus.OK
    assert reactivate.get_json()["email_verified"] in {True, False}

    login2 = client.post("/auth/login", json={"email": email, "password": password})
    assert login2.status_code == HTTPStatus.OK


def test_hard_delete_account(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    email, password, token = _register_and_get_token(client, email="hard@example.com")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = client.delete(
        "/auth/account",
        headers=headers,
        json={"password": password, "hard_delete": True},
    )
    assert resp.status_code == HTTPStatus.OK

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.NOT_FOUND}


def test_reactivate_requires_credentials(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    email, password, token = _register_and_get_token(client, email="reactreq@example.com")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    client.delete("/auth/account", headers=headers, json={"password": password})

    resp = client.post("/auth/reactivate", json={"email": email, "password": "wrong"})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED

    resp = client.post("/auth/reactivate", json={"email": email, "password": password})
    assert resp.status_code == HTTPStatus.OK
