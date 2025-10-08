from seed_drug_data import create_sample_drugs, create_sample_interactions
from health_app.models import Drug, SideEffect, DrugInteraction


def test_seed_sample_drugs(app):
    with app.app_context():
        created = create_sample_drugs()
        assert "ibuprofen" in created
        ibuprofen = Drug.query.filter_by(name="ibuprofen").one()
        assert "advil" in (ibuprofen.brand_synonyms or "").lower()
        assert SideEffect.query.filter_by(drug_id=ibuprofen.id).count() >= 2


def test_seed_interactions(app):
    with app.app_context():
        created = create_sample_drugs()
        create_sample_interactions(created)
        interaction = DrugInteraction.query.filter_by(severity="major").first()
        assert interaction is not None
