import pytest


pytestmark = pytest.mark.slow

def test_drug_check_minimal(client, auth_headers):
    payload = {"drugs": [{"name": "ibuprofen", "dose": "400 mg"}]}
    r = client.post("/drug-check/", headers=auth_headers, json=payload)
    assert r.status_code == 200
    data = r.get_json()
    body = data.get("data", data)
    assert "interactions" in body
    assert "overdose_alerts" in body
    assert "contraindications" in body
    assert "side_effect_warnings" in body
    assert "side_effect_summary" in body
    assert "dosage_guidance" in body

def test_drug_check_validation(client, auth_headers):
    r = client.post("/drug-check/", headers=auth_headers, json={"drugs": []})
    assert r.status_code in (400, 422)
