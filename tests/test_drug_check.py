from health_app import db
from health_app.models import Drug


def test_drug_check_minimal(client, auth_headers):
    payload = {"drugs": [{"name": "ibuprofen", "dose": "400 mg"}]}
    r = client.post("/drug-check/", headers=auth_headers, json=payload)
    assert r.status_code == 200
    data = r.get_json()
    body = data.get("data", data)
    assert "interactions" in body
    assert "overdose_alerts" in body
    assert "contraindications" in body

def test_drug_check_validation(client, auth_headers):
    r = client.post("/drug-check/", headers=auth_headers, json={"drugs": []})
    assert r.status_code in (400, 422)


def test_drug_check_case_insensitive_lookup(app, client, auth_headers):
    with app.app_context():
        drug = Drug(name="Ibuprofen", max_daily_dose=1600)
        db.session.add(drug)
        db.session.commit()
        drug_id = drug.id

    payload = {"drugs": [{"name": "IBUPROFEN", "dose": "400 mg"}]}
    r = client.post("/drug-check/", headers=auth_headers, json=payload)
    assert r.status_code == 200

    body = r.get_json()["data"]
    mapping = body["normalization"]["mapping"]
    assert mapping.get("ibuprofen") == drug_id
    assert all(key == key.lower() for key in mapping)
    assert body["normalization"]["unrecognized"] == []
