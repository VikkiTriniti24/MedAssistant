import pytest

from health_app import db
from health_app.models import Drug, Contraindication, Condition


pytestmark = pytest.mark.slow


def _seed_drug(app, name: str) -> int:
    with app.app_context():
        drug = Drug(name=name.lower(), standard_dosage="5 mg")
        db.session.add(drug)
        db.session.commit()
        return drug.id


def test_contraindication_detected_via_profile_condition(app, client, auth_headers):
    drug_id = _seed_drug(app, "Warfarin")

    add_condition = client.post(
        "/profile/conditions/",
        headers=auth_headers,
        json={"name": "Liver Disease"},
    )
    assert add_condition.status_code == 201

    with app.app_context():
        condition = Condition.query.filter_by(name="Liver Disease").first()
        assert condition is not None
        contraindication = Contraindication(
            drug_id=drug_id,
            condition_id=condition.id,
            notes="Increased bleeding risk",
        )
        db.session.add(contraindication)
        db.session.commit()

    response = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={"drugs": [{"name": "Warfarin"}]},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    contraindications = data["contraindications"]
    assert any(item.get("condition") == "Liver Disease" for item in contraindications)
    analysis = data["contraindication_analysis"]
    assert "Liver Disease" in analysis["matched_conditions"]


def test_contraindication_unmatched_conditions(client, auth_headers):
    resp = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={
            "drugs": [{"name": "Ibuprofen"}],
            "conditions": ["Unknown Condition"],
        },
    )

    assert resp.status_code == 200
    analysis = resp.get_json()["data"]["contraindication_analysis"]
    assert "Unknown Condition" in analysis["unmatched_conditions"]
