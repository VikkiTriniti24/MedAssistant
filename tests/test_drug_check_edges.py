import pytest


pytestmark = pytest.mark.slow

def test_drug_check_requires_list(client, auth_headers):
    r = client.post("/drug-check/", headers=auth_headers, json={"drugs": {}})
    assert r.status_code == 400

def test_drug_check_item_requires_name(client, auth_headers):
    r = client.post("/drug-check/", headers=auth_headers, json={"drugs":[{}]})
    assert r.status_code == 400

def test_drug_check_happy(client, auth_headers):
    r = client.post("/drug-check/", headers=auth_headers, json={"drugs":[{"name":"ibuprofen","dose":"400 mg"}]})
    assert r.status_code == 200
    body = r.get_json()["data"]
    for key in ("interactions","overdose_alerts","contraindications","summary","side_effect_warnings","dosage_guidance"):
        assert key in body
