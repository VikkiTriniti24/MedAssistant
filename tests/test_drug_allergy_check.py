import pytest

from health_app import db
from health_app.models import Drug, Substance


pytestmark = pytest.mark.slow


def _seed_drug(app, name: str, substances: list[str]) -> None:
    with app.app_context():
        drug = Drug(name=name.lower(), standard_dosage="100 mg")
        db.session.add(drug)
        db.session.flush()

        for sub in substances:
            db.session.add(Substance(drug_id=drug.id, name=sub, type="active"))

        db.session.commit()


def test_allergy_check_uses_profile_allergies(app, client, auth_headers):
    _seed_drug(app, "Amoxicillin", ["Penicillin"])

    # add allergy via profile endpoint
    resp = client.post(
        "/profile/allergies/",
        headers=auth_headers,
        json={"name": "Penicillin"},
    )
    assert resp.status_code == 201

    payload = {
        "drugs": ["Amoxicillin"],
        "include_profile_allergies": True,
    }

    check = client.post(
        "/drug-check/allergy-check/",
        headers=auth_headers,
        json=payload,
    )

    assert check.status_code == 200
    data = check.get_json()["data"]
    assert data["summary"]["conflict_count"] == 1
    assert data["results"][0]["conflict"] is True
    assert "Penicillin" in data["results"][0]["allergens"]


def test_allergy_check_custom_allergies(app, client, auth_headers):
    _seed_drug(app, "Aspirin", ["Salicylate"])

    check = client.post(
        "/drug-check/allergy-check/",
        headers=auth_headers,
        json={
            "drugs": ["Aspirin"],
            "allergies": ["salicylate"],
        },
    )

    assert check.status_code == 200
    data = check.get_json()["data"]
    assert data["summary"]["conflict_count"] == 1
    assert data["matched_allergies"] == ["salicylate"]
    assert data["unmatched_allergies"] == []


def test_allergy_check_validation_errors(client, auth_headers):
    res = client.post(
        "/drug-check/allergy-check/",
        headers=auth_headers,
        json={"drugs": []},
    )
    assert res.status_code == 400

    res = client.post(
        "/drug-check/allergy-check/",
        headers=auth_headers,
        json={"drugs": [123]},
    )
    assert res.status_code == 400
