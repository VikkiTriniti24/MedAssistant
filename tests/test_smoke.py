"""High-level smoke tests to ensure critical flows respond successfully."""

import pytest
from http import HTTPStatus


pytestmark = pytest.mark.slow


def test_smoke_auth_flow(client):
    """User can register and subsequently log in."""
    email = "smoke-user@example.com"
    password = "Passw0rd!"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert register_resp.status_code == HTTPStatus.OK
    register_data = register_resp.get_json() or {}
    assert register_data.get("access_token"), "registration should issue access token"

    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == HTTPStatus.OK
    login_data = login_resp.get_json() or {}
    assert login_data.get("access_token"), "login should issue access token"


def test_smoke_chat_flow(client, auth_headers):
    """Authenticated user can post chat messages and receive a reply."""
    resp = client.post(
        "/chat/",
        headers=auth_headers,
        json={"messages": [{"role": "user", "content": "Hello, I feel tired."}]},
    )
    assert resp.status_code == HTTPStatus.OK
    payload = resp.get_json() or {}
    assert payload.get("kind") == "message"
    assert isinstance(payload.get("message"), str) and payload["message"].strip()


def test_smoke_drug_check_flow(client, auth_headers):
    """Drug check endpoint responds with core sections."""
    resp = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={"drugs": [{"name": "ibuprofen", "dose": "400 mg"}]},
    )
    assert resp.status_code == HTTPStatus.OK
    body = resp.get_json() or {}
    data = body.get("data") or body
    for key in ("interactions", "contraindications", "side_effect_warnings"):
        assert key in data
