# health_app/models.py
from datetime import datetime, date
from . import db

# Aliases (kurz)
UC = db.UniqueConstraint
CC = db.CheckConstraint
IX = db.Index
FK = db.ForeignKey


# --- Auth & Profile ---------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(255), nullable=False, unique=True, index=True)
    hashed_pwd = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    profile = db.relationship(
        "Profile",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan"
    )


class Profile(db.Model):
    __tablename__ = "profiles"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, FK("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    age        = db.Column(db.Integer)
    sex        = db.Column(db.String(16))  # female|male|other|unknown
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="profile")

    allergies   = db.relationship("Allergy", back_populates="profile", cascade="all, delete-orphan")
    conditions  = db.relationship("Condition", back_populates="profile", cascade="all, delete-orphan")
    medications = db.relationship("ProfileMedication", back_populates="profile", cascade="all, delete-orphan")

    __table_args__ = (
        CC("sex IN ('female','male','other','unknown')", name="ck_profiles_sex"),
    )


class Allergy(db.Model):
    __tablename__ = "allergies"

    id         = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, FK("profiles.id", ondelete="CASCADE"), nullable=False)
    name       = db.Column(db.String(255), nullable=False)

    profile = db.relationship("Profile", back_populates="allergies")

    __table_args__ = (
        UC("profile_id", "name", name="ux_allergies_profile_name"),
        IX("ix_allergies_profile", "profile_id"),
    )


class Condition(db.Model):
    """
    Profil-gebundene Zustände (einfach & pragmatisch).
    Wenn du später globale Krankheits-Konzepte (ICD/SNOMED) brauchst,
    kannst du ein separates medical_conditions + profile_conditions einführen.
    """
    __tablename__ = "conditions"

    id         = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, FK("profiles.id", ondelete="CASCADE"), nullable=False)
    name       = db.Column(db.String(255), nullable=False)

    profile = db.relationship("Profile", back_populates="conditions")

    __table_args__ = (
        UC("profile_id", "name", name="ux_conditions_profile_name"),
        IX("ix_conditions_profile", "profile_id"),
    )


# --- Drugs & Substances -----------------------------------------------------
class Drug(db.Model):
    __tablename__ = "drugs"

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(255), nullable=False, unique=True, index=True)
    rxnorm_code     = db.Column(db.String(64), unique=True)
    standard_dosage = db.Column(db.String(64))
    max_daily_dose  = db.Column(db.Float)  # >= 0
    overdose_alert  = db.Column(db.Boolean, default=False, nullable=False)

    substances = db.relationship("Substance", back_populates="drug", cascade="all, delete-orphan")

    __table_args__ = (
        CC("max_daily_dose IS NULL OR max_daily_dose >= 0", name="ck_drugs_max_daily_dose"),
    )


class Substance(db.Model):
    __tablename__ = "substances"

    id     = db.Column(db.Integer, primary_key=True)
    drug_id= db.Column(db.Integer, FK("drugs.id", ondelete="CASCADE"), nullable=False)
    name   = db.Column(db.String(255), nullable=False)
    type   = db.Column(db.String(16), nullable=False)  # active|helper

    drug = db.relationship("Drug", back_populates="substances")

    __table_args__ = (
        CC("type IN ('active','helper')", name="ck_substances_type"),
        IX("ix_substances_drug", "drug_id"),
    )


class ProfileMedication(db.Model):
    __tablename__ = "profile_medications"

    id         = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, FK("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    drug_id    = db.Column(db.Integer, FK("drugs.id", ondelete="RESTRICT"), nullable=False, index=True)
    dosage     = db.Column(db.String(64))
    started_at = db.Column(db.Date)
    ended_at   = db.Column(db.Date)

    profile = db.relationship("Profile", back_populates="medications")
    drug    = db.relationship("Drug")

    __table_args__ = (
        CC("(ended_at IS NULL) OR (started_at IS NULL) OR (started_at <= ended_at)", name="ck_profile_med_dates"),
        UC("profile_id", "drug_id", "started_at", "ended_at", name="ux_profile_med_dedup"),
    )


class DrugInteraction(db.Model):
    __tablename__ = "drug_interactions"

    id        = db.Column(db.Integer, primary_key=True)
    drug1_id  = db.Column(db.Integer, FK("drugs.id", ondelete="CASCADE"), nullable=False)
    drug2_id  = db.Column(db.Integer, FK("drugs.id", ondelete="CASCADE"), nullable=False)
    severity  = db.Column(db.String(16), nullable=False)  # minor|moderate|major
    description = db.Column(db.Text)

    __table_args__ = (
        CC("drug1_id < drug2_id", name="ck_drug_interactions_order"),  # kanonische Ordnung
        UC("drug1_id", "drug2_id", name="ux_drug_interactions_pair"),
        CC("severity IN ('minor','moderate','major')", name="ck_drug_interactions_severity"),
        IX("ix_drug_interactions_drug1", "drug1_id"),
        IX("ix_drug_interactions_drug2", "drug2_id"),
    )


class Contraindication(db.Model):
    __tablename__ = "contraindications"

    id           = db.Column(db.Integer, primary_key=True)
    drug_id      = db.Column(db.Integer, FK("drugs.id", ondelete="CASCADE"), nullable=False)
    condition_id = db.Column(db.Integer, FK("conditions.id", ondelete="CASCADE"), nullable=False)  # profilgebunden pragmatisch
    notes        = db.Column(db.Text)

    __table_args__ = (
        UC("drug_id", "condition_id", name="ux_contraindications_unique"),
        IX("ix_contraindications_drug", "drug_id"),
        IX("ix_contraindications_condition", "condition_id"),
    )


# --- Symptoms, Diagnosis & Risk --------------------------------------------
class SymptomEntry(db.Model):
    __tablename__ = "symptom_entries"

    id         = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, FK("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    symptoms   = db.Column(db.Text, nullable=False)
    entered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Diagnosis(db.Model):
    __tablename__ = "diagnoses"

    id               = db.Column(db.Integer, primary_key=True)
    symptom_entry_id = db.Column(db.Integer, FK("symptom_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    condition_name   = db.Column(db.String(255), nullable=False)
    probability      = db.Column(db.Float, nullable=False)     # 0..1
    triage_level     = db.Column(db.String(16), nullable=False)  # low|medium|high

    __table_args__ = (
        CC("probability >= 0.0 AND probability <= 1.0", name="ck_diagnoses_probability"),
        CC("triage_level IN ('low','medium','high')", name="ck_diagnoses_triage"),
    )


class RiskEvaluation(db.Model):
    __tablename__ = "risk_evaluations"

    id               = db.Column(db.Integer, primary_key=True)
    symptom_entry_id = db.Column(db.Integer, FK("symptom_entries.id", ondelete="CASCADE"), nullable=False, unique=True)
    risk_level       = db.Column(db.String(16), nullable=False)   # low|medium|high|critical
    urgency          = db.Column(db.String(16), nullable=False)   # self-care|see-doctor|urgent-care|emergency
    evaluated_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CC("risk_level IN ('low','medium','high','critical')", name="ck_risk_level"),
        CC("urgency IN ('self-care','see-doctor','urgent-care','emergency')", name="ck_urgency"),
    )


# --- Drug Check results (Audit/History) ------------------------------------
class DrugCheck(db.Model):
    __tablename__ = "drug_checks"

    id         = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, FK("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class DrugCheckItem(db.Model):
    __tablename__ = "drug_check_items"

    id            = db.Column(db.Integer, primary_key=True)
    drug_check_id = db.Column(db.Integer, FK("drug_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    drug_id       = db.Column(db.Integer, FK("drugs.id", ondelete="RESTRICT"), nullable=False, index=True)


class InteractionResult(db.Model):
    __tablename__ = "interaction_results"

    id            = db.Column(db.Integer, primary_key=True)
    drug_check_id = db.Column(db.Integer, FK("drug_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    drug1_id      = db.Column(db.Integer, FK("drugs.id", ondelete="RESTRICT"), nullable=False)
    drug2_id      = db.Column(db.Integer, FK("drugs.id", ondelete="RESTRICT"), nullable=False)
    severity      = db.Column(db.String(16))    # minor|moderate|major
    description   = db.Column(db.Text)

    __table_args__ = (
        CC("severity IS NULL OR severity IN ('minor','moderate','major')", name="ck_interaction_result_severity"),
        IX("ix_interaction_results_check", "drug_check_id"),
    )


# --- Chat -------------------------------------------------------------------
class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id         = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, FK("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    messages = db.relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, FK("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    sender     = db.Column(db.String(16), nullable=False)  # user|assistant
    message_text = db.Column(db.Text, nullable=False)
    sent_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        CC("sender IN ('user','assistant')", name="ck_chat_message_sender"),
    )
