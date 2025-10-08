#!/usr/bin/env python3
"""
Sample data seeder for MedAssistant drug database

This script populates the database with sample drugs, substances, and interactions
for testing the drug interaction checking system.
"""

import sys
from pathlib import Path
from typing import Dict, List

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from health_app import create_app, db  # noqa: E402
from health_app.models import Drug, Substance, DrugInteraction, SideEffect  # noqa: E402

def _merge_brand_synonyms(existing: Drug, new_synonyms: List[str]) -> None:
    current = existing.brand_synonyms or ""
    tokens = {s.strip().lower() for s in current.split(",") if s.strip()} if current else set()
    for synonym in new_synonyms:
        normalized = synonym.strip().lower()
        if normalized and normalized not in tokens:
            tokens.add(normalized)
    existing.brand_synonyms = ", ".join(sorted(tokens)) if tokens else None


def _upsert_side_effects(drug: Drug, side_effects: List[Dict[str, str]]) -> None:
    existing_map = {}
    for effect in drug.side_effects:
        key = (effect.category or "", effect.description or "")
        existing_map[key] = effect
    for side_effect in side_effects or []:
        key = (side_effect["category"], side_effect["description"])
        if key in existing_map:
            existing_map[key].severity = side_effect["severity"]
            continue
        db.session.add(
            SideEffect(
                drug_id=drug.id,
                category=side_effect["category"],
                severity=side_effect["severity"],
                description=side_effect["description"],
            )
        )


def create_sample_drugs():
    """Create sample drugs with substances and interactions."""
    
    # Sample drugs data
    drugs_data = [
        {
            "name": "ibuprofen",
            "rxnorm_code": "5640",
            "standard_dosage": "200-400 mg",
            "max_daily_dose": 2400.0,
            "brand_synonyms": ["Advil", "Motrin"],
            "side_effects": [
                {"category": "Gastrointestinal", "severity": "moderate", "description": "May cause stomach upset or ulcers"},
                {"category": "Renal", "severity": "mild", "description": "Monitor kidney function with prolonged use"},
            ],
            "substances": [
                {"name": "ibuprofen", "type": "active"},
                {"name": "starch", "type": "helper"},
                {"name": "magnesium stearate", "type": "helper"}
            ]
        },
        {
            "name": "aspirin",
            "rxnorm_code": "1191",
            "standard_dosage": "81-325 mg",
            "max_daily_dose": 4000.0,
            "brand_synonyms": ["Bayer"],
            "side_effects": [
                {"category": "Bleeding", "severity": "severe", "description": "Increases bleeding risk especially with anticoagulants"}
            ],
            "substances": [
                {"name": "acetylsalicylic acid", "type": "active"},
                {"name": "cellulose", "type": "helper"}
            ]
        },
        {
            "name": "warfarin",
            "rxnorm_code": "11289",
            "standard_dosage": "2-10 mg",
            "max_daily_dose": 10.0,
            "brand_synonyms": ["Coumadin"],
            "side_effects": [
                {"category": "Hematologic", "severity": "severe", "description": "Serious bleeding can occur"}
            ],
            "substances": [
                {"name": "warfarin sodium", "type": "active"},
                {"name": "lactose", "type": "helper"}
            ]
        },
        {
            "name": "digoxin",
            "rxnorm_code": "3407",
            "standard_dosage": "0.125-0.25 mg",
            "max_daily_dose": 0.5,
            "brand_synonyms": ["Lanoxin"],
            "side_effects": [
                {"category": "Cardiac", "severity": "severe", "description": "May cause arrhythmias at high levels"}
            ],
            "substances": [
                {"name": "digoxin", "type": "active"}
            ]
        },
        {
            "name": "furosemide",
            "rxnorm_code": "4609",
            "standard_dosage": "20-80 mg",
            "max_daily_dose": 600.0,
            "brand_synonyms": ["Lasix"],
            "side_effects": [
                {"category": "Electrolyte", "severity": "moderate", "description": "May cause hypokalemia"}
            ],
            "substances": [
                {"name": "furosemide", "type": "active"},
                {"name": "sodium chloride", "type": "helper"}
            ]
        },
        {
            "name": "potassium chloride",
            "rxnorm_code": "8540",
            "standard_dosage": "10-40 mEq",
            "max_daily_dose": 100.0,
            "brand_synonyms": ["Klor-Con"],
            "side_effects": [
                {"category": "Gastrointestinal", "severity": "moderate", "description": "High doses may cause GI irritation"}
            ],
            "substances": [
                {"name": "potassium chloride", "type": "active"}
            ]
        },
        {
            "name": "acetaminophen",
            "rxnorm_code": "161",
            "standard_dosage": "325-650 mg",
            "max_daily_dose": 4000.0,
            "brand_synonyms": ["Tylenol", "Panadol"],
            "side_effects": [
                {"category": "Hepatic", "severity": "severe", "description": "Overdose may cause liver failure"}
            ],
            "substances": [
                {"name": "acetaminophen", "type": "active"},
                {"name": "corn starch", "type": "helper"}
            ]
        },
        {
            "name": "metformin",
            "rxnorm_code": "6809",
            "standard_dosage": "500-2000 mg",
            "max_daily_dose": 2550.0,
            "brand_synonyms": ["Glucophage"],
            "side_effects": [
                {"category": "Metabolic", "severity": "moderate", "description": "Risk of lactic acidosis in renal impairment"}
            ],
            "substances": [
                {"name": "metformin hydrochloride", "type": "active"}
            ]
        }
    ]
    
    # Create drugs and substances
    created_drugs = {}
    for drug_data in drugs_data:
        # Check if drug already exists
        existing_drug = Drug.query.filter_by(name=drug_data["name"]).first()
        if existing_drug:
            print(f"ℹ️  Drug '{drug_data['name']}' already exists, updating metadata...")
            _merge_brand_synonyms(existing_drug, drug_data.get("brand_synonyms", []))
            _upsert_side_effects(existing_drug, drug_data.get("side_effects", []))
            created_drugs[drug_data["name"]] = existing_drug
            continue

        drug = Drug(
            name=drug_data["name"],
            rxnorm_code=drug_data["rxnorm_code"],
            standard_dosage=drug_data["standard_dosage"],
            max_daily_dose=drug_data["max_daily_dose"],
            brand_synonyms=", ".join(drug_data.get("brand_synonyms", [])) or None,
        )
        db.session.add(drug)
        db.session.flush()  # Get the ID
        
        # Create substances
        for substance_data in drug_data["substances"]:
            substance = Substance(
                drug_id=drug.id,
                name=substance_data["name"],
                type=substance_data["type"]
            )
            db.session.add(substance)

        _upsert_side_effects(drug, drug_data.get("side_effects", []))
        
        created_drugs[drug_data["name"]] = drug
        print(f"✅ Created drug: {drug_data['name']}")
    
    # Commit all drugs and substances
    db.session.commit()
    return created_drugs

def create_sample_interactions(created_drugs):
    """Create sample drug interactions."""
    
    interactions_data = [
        {
            "drug1": "ibuprofen",
            "drug2": "aspirin",
            "severity": "moderate",
            "description": "Increased risk of gastrointestinal bleeding when taken together"
        },
        {
            "drug1": "ibuprofen",
            "drug2": "warfarin",
            "severity": "major",
            "description": "Ibuprofen may increase warfarin's anticoagulant effect, increasing bleeding risk"
        },
        {
            "drug1": "aspirin",
            "drug2": "warfarin",
            "severity": "major",
            "description": "Combined anticoagulant effect increases bleeding risk significantly"
        },
        {
            "drug1": "digoxin",
            "drug2": "furosemide",
            "severity": "moderate",
            "description": "Furosemide may increase digoxin toxicity by causing hypokalemia"
        },
        {
            "drug1": "digoxin",
            "drug2": "potassium chloride",
            "severity": "minor",
            "description": "Potassium supplements may reduce digoxin effectiveness"
        },
        {
            "drug1": "acetaminophen",
            "drug2": "warfarin",
            "severity": "moderate",
            "description": "High doses of acetaminophen may enhance warfarin's anticoagulant effect"
        },
        {
            "drug1": "metformin",
            "drug2": "furosemide",
            "severity": "minor",
            "description": "Furosemide may increase risk of lactic acidosis with metformin"
        }
    ]
    
    created_interactions = 0
    for interaction_data in interactions_data:
        drug1_name = interaction_data["drug1"]
        drug2_name = interaction_data["drug2"]
        
        drug1 = created_drugs.get(drug1_name)
        drug2 = created_drugs.get(drug2_name)
        
        if not drug1 or not drug2:
            print(f"⚠️  Skipping interaction {drug1_name} + {drug2_name} (drugs not found)")
            continue
        
        # Check if interaction already exists
        existing = DrugInteraction.query.filter(
            ((DrugInteraction.drug1_id == drug1.id) & (DrugInteraction.drug2_id == drug2.id)) |
            ((DrugInteraction.drug1_id == drug2.id) & (DrugInteraction.drug2_id == drug1.id))
        ).first()
        
        if existing:
            print(f"ℹ️  Interaction {drug1_name} + {drug2_name} already exists, skipping...")
            continue
        
        # Ensure drug1_id < drug2_id for canonical ordering
        if drug1.id < drug2.id:
            interaction = DrugInteraction(
                drug1_id=drug1.id,
                drug2_id=drug2.id,
                severity=interaction_data["severity"],
                description=interaction_data["description"]
            )
        else:
            interaction = DrugInteraction(
                drug1_id=drug2.id,
                drug2_id=drug1.id,
                severity=interaction_data["severity"],
                description=interaction_data["description"]
            )
        
        db.session.add(interaction)
        created_interactions += 1
        print(f"✅ Created interaction: {drug1_name} + {drug2_name} ({interaction_data['severity']})")
    
    db.session.commit()
    print(f"✅ Created {created_interactions} drug interactions")

def main():
    """Main seeding function."""
    print("🌱 Seeding MedAssistant Drug Database")
    print("=" * 40)
    
    # Create Flask app context
    app = create_app()
    with app.app_context():
        try:
            # Create sample drugs
            print("\n📦 Creating sample drugs...")
            created_drugs = create_sample_drugs()
            
            # Create sample interactions
            print("\n🔗 Creating sample interactions...")
            create_sample_interactions(created_drugs)
            
            print("\n🎉 Database seeding completed successfully!")
            print(f"📊 Created {len(created_drugs)} drugs with substances and interactions")
            
        except Exception as e:
            print(f"❌ Error seeding database: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    main()
