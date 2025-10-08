import pytest

from health_app import db
from health_app.models import Drug


pytestmark = pytest.mark.slow


def _seed_brand_drug(app):
    with app.app_context():
        drug = Drug(name="acetaminophen", standard_dosage="500 mg", brand_synonyms="Tylenol, Panadol")
        db.session.add(drug)
        db.session.commit()


def test_brand_name_recognized(app, client, auth_headers):
    _seed_brand_drug(app)

    resp = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={"drugs": [{"name": "Tylenol"}]},
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    normalization = data["normalization"]
    assert "tylenol" not in normalization["unrecognized"]
    mapping = normalization["mapping"]
    assert "acetaminophen" in mapping


def test_brand_and_generic_same_drug(app, client, auth_headers):
    _seed_brand_drug(app)

    resp = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={"drugs": [{"name": "Tylenol"}, {"name": "acetaminophen"}]},
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    # Should not mark either as unrecognized
    assert not data["normalization"]["unrecognized"]
    # Interactions list should be empty since it's the same underlying drug counted twice
    assert not data["interactions"]
