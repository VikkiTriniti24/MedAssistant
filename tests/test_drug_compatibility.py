import pytest

from health_app import db
from health_app.models import Drug, DrugInteraction


pytestmark = pytest.mark.slow


def _seed_drugs_with_interaction(app):
    with app.app_context():
        drug_a = Drug(name="drug-a", standard_dosage="10 mg")
        drug_b = Drug(name="drug-b", standard_dosage="5 mg")
        db.session.add_all([drug_a, drug_b])
        db.session.flush()

        db.session.add(
            DrugInteraction(
                drug1_id=drug_a.id,
                drug2_id=drug_b.id,
                severity="major",
                description="Significant interaction",
            )
        )
        db.session.commit()


def test_compatibility_issues_returned(app, client, auth_headers):
    _seed_drugs_with_interaction(app)

    resp = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={"drugs": [{"name": "drug-a"}, {"name": "drug-b"}]},
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    compatibility = data["compatibility"]
    assert compatibility["compatible"] is False
    assert compatibility["issues"]


def test_compatibility_pass(client, auth_headers):
    resp = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={"drugs": [{"name": "ibuprofen"}, {"name": "acetaminophen"}]},
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["compatibility"]["compatible"] is True
