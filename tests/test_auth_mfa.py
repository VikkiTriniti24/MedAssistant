from http import HTTPStatus
from time import time

import pytest

from health_app.utils import totp


pytestmark = pytest.mark.slow


def register_without_email(client, email="mfa@example.com", password="StrongPass123"):
    resp = client.post("/auth/register", json={"email": email, "password": password})
    data = resp.get_json()
    return email, password, data["access_token"], resp


def test_mfa_setup_confirm_and_login(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    email, password, token, _ = register_without_email(client)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    setup = client.post("/auth/mfa/setup", headers=headers)
    assert setup.status_code == HTTPStatus.OK
    secret = setup.get_json()["secret"]

    code = totp.generate_totp(secret, timestamp=time())
    confirm = client.post("/auth/mfa/confirm", headers=headers, json={"code": code})
    assert confirm.status_code == HTTPStatus.OK
    confirm_payload = confirm.get_json()
    backup_codes = confirm_payload.get("backup_codes")
    assert isinstance(backup_codes, list) and backup_codes

    login_no_code = client.post("/auth/login", json={"email": email, "password": password})
    assert login_no_code.status_code == HTTPStatus.UNAUTHORIZED
    assert login_no_code.get_json().get("mfa_required") is True

    code = totp.generate_totp(secret, timestamp=time())
    login_with_code = client.post(
        "/auth/login",
        json={"email": email, "password": password, "mfa_code": code},
    )
    assert login_with_code.status_code == HTTPStatus.OK


def test_login_with_backup_code(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    email, password, token, _ = register_without_email(client, email="mfa-backup@example.com")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    setup = client.post("/auth/mfa/setup", headers=headers)
    secret = setup.get_json()["secret"]

    code = totp.generate_totp(secret, timestamp=time())
    confirm = client.post("/auth/mfa/confirm", headers=headers, json={"code": code})
    backup_codes = confirm.get_json().get("backup_codes")
    assert backup_codes, "expected backup codes after confirmation"

    backup_code = backup_codes[0]

    login_using_backup = client.post(
        "/auth/login",
        json={"email": email, "password": password, "backup_code": backup_code},
    )
    assert login_using_backup.status_code == HTTPStatus.OK

    reuse_backup = client.post(
        "/auth/login",
        json={"email": email, "password": password, "backup_code": backup_code},
    )
    assert reuse_backup.status_code == HTTPStatus.UNAUTHORIZED


def test_mfa_disable_with_code(client, monkeypatch):
    monkeypatch.setattr("health_app.routes.auth.send_email_verification", lambda *a, **k: None)
    email, password, token, _ = register_without_email(client, email="mfadisable@example.com")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    setup = client.post("/auth/mfa/setup", headers=headers)
    secret = setup.get_json()["secret"]
    code = totp.generate_totp(secret)
    client.post("/auth/mfa/confirm", headers=headers, json={"code": code})

    disable_code = totp.generate_totp(secret)
    disable_resp = client.post(
        "/auth/mfa/disable",
        headers=headers,
        json={"code": disable_code},
    )
    assert disable_resp.status_code == HTTPStatus.OK

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == HTTPStatus.OK
