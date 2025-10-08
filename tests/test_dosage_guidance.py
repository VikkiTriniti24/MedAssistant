import pytest

from health_app import db
from health_app.models import Drug


pytestmark = pytest.mark.slow


def _seed_drug(app, name: str, standard: str, max_daily: float) -> None:
    with app.app_context():
        drug = Drug(name=name.lower(), standard_dosage=standard, max_daily_dose=max_daily)
        db.session.add(drug)
        db.session.commit()


def test_dosage_guidance_includes_standard(app, client, auth_headers):
    _seed_drug(app, "Atorvastatin", "10 mg", 80.0)

    resp = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={"drugs": [{"name": "Atorvastatin", "dose": "20 mg", "freq_per_day": 1}]},
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    guidance = data["dosage_guidance"]
    assert any("Typical dose 10 mg" in g.get("note", "") for g in guidance)
    assert any("Reported dose 20 mg" in g.get("note", "") for g in guidance)
