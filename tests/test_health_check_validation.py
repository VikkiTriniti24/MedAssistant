# tests/test_health_check_validation.py

import pytest


pytestmark = pytest.mark.slow

def test_health_check_missing_symptoms(client, auth_headers):
    r = client.post("/health-check/", headers=auth_headers, json={})
    assert r.status_code == 400
    body = r.get_json()
    assert body["success"] is False
    assert any("symptoms" in e for e in body["errors"])

def test_health_check_invalid_sex(client, auth_headers):
    # HIER war vorher dein Syntaxfehler (falsches /> am Ende)
    r = client.post("/health-check/", headers=auth_headers,
                    json={"symptoms": "x", "sex": "???"})
    assert r.status_code == 400
    body = r.get_json()
    assert body["success"] is False
    assert any("sex" in e for e in body["errors"])

def test_health_check_happy(client, auth_headers):
    r = client.post("/health-check/", headers=auth_headers,
                    json={"symptoms": "fever 38.1, sore throat", "onset": "sudden"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert "data" in body
    assert "diagnoses" in body["data"]
