import pytest

from health_app import db
from health_app.models import Drug, SideEffect


pytestmark = pytest.mark.slow


def _seed_side_effect(app, drug_name: str, category: str, severity: str, description: str) -> None:
    with app.app_context():
        drug = Drug(name=drug_name.lower(), standard_dosage="10 mg")
        db.session.add(drug)
        db.session.flush()

        db.session.add(
            SideEffect(
                drug_id=drug.id,
                category=category,
                severity=severity,
                description=description,
            )
        )
        db.session.commit()


def test_side_effect_warnings_from_db(app, client, auth_headers):
    _seed_side_effect(app, "Metformin", "Metabolic", "severe", "Risk of lactic acidosis")

    resp = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={"drugs": [{"name": "Metformin"}]},
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]

    warnings = data["side_effect_warnings"]
    assert any(w.get("description") == "Risk of lactic acidosis" for w in warnings)
    summary = data["side_effect_summary"]
    assert "metformin" in {k.lower() for k in summary.keys()}


def test_ai_side_effects_included(monkeypatch, client, auth_headers):
    from health_app.routes import drug_check as drug_routes

    def fake_ai(enriched, conditions, allergies, pregnant, profile):
        return {
            "ai_overdose_alerts": [],
            "ai_interactions": [],
            "ai_contraindications": [],
            "ai_side_effects": [
                {
                    "drug": "Ibuprofen",
                    "effect": "Gastrointestinal bleeding",
                    "severity": "severe",
                    "recommendation": "Use proton pump inhibitor if long-term",
                }
            ],
            "ai_dosage_guidance": [],
            "ai_mode": "stub",
        }

    monkeypatch.setattr(drug_routes, "_ai_enhanced_drug_check", fake_ai)

    resp = client.post(
        "/drug-check/",
        headers=auth_headers,
        json={"drugs": [{"name": "Ibuprofen"}]},
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    warnings = data["side_effect_warnings"]
    assert any(w.get("effect") == "Gastrointestinal bleeding" for w in warnings)
