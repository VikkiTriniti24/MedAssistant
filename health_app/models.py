# health_app/models.py
from datetime import datetime
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
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime)

    profile = db.relationship(
        "Profile",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan"
    )
    preferences = db.relationship(
        "UserPreferences",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan"
    )
    mfa = db.relationship(
        "MFAConfig",
        uselist=False,
        backref="user",
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
    brand_synonyms  = db.Column(db.Text)
    rxnorm_code     = db.Column(db.String(64), unique=True)
    standard_dosage = db.Column(db.String(64))
    max_daily_dose  = db.Column(db.Float)  # >= 0
    overdose_alert  = db.Column(db.Boolean, default=False, nullable=False)

    substances = db.relationship("Substance", back_populates="drug", cascade="all, delete-orphan")
    side_effects = db.relationship("SideEffect", back_populates="drug", cascade="all, delete-orphan")

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


class SideEffect(db.Model):
    __tablename__ = "side_effects"

    id          = db.Column(db.Integer, primary_key=True)
    drug_id     = db.Column(db.Integer, FK("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    category    = db.Column(db.String(64), nullable=False)
    severity    = db.Column(db.String(16), nullable=False)  # mild|moderate|severe
    description = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    drug = db.relationship("Drug", back_populates="side_effects")

    __table_args__ = (
        CC("severity IN ('mild','moderate','severe')", name="ck_side_effects_severity"),
        IX("ix_side_effects_category", "category"),
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
    schedule = db.relationship(
        "MedicationSchedule",
        back_populates="medication",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CC("(ended_at IS NULL) OR (started_at IS NULL) OR (started_at <= ended_at)", name="ck_profile_med_dates"),
        UC("profile_id", "drug_id", "started_at", "ended_at", name="ux_profile_med_dedup"),
    )


class MedicationSchedule(db.Model):
    __tablename__ = "medication_schedules"

    id                      = db.Column(db.Integer, primary_key=True)
    profile_medication_id   = db.Column(db.Integer, FK("profile_medications.id", ondelete="CASCADE"), nullable=False, index=True)
    timezone                = db.Column(db.String(64), nullable=False, default="UTC")
    schedule_data           = db.Column(db.Text, nullable=False)
    start_date              = db.Column(db.Date)
    end_date                = db.Column(db.Date)
    remind_via_email        = db.Column(db.Boolean, nullable=False, default=False)
    remind_via_push         = db.Column(db.Boolean, nullable=False, default=False)
    remind_via_sms          = db.Column(db.Boolean, nullable=False, default=False)
    notes                   = db.Column(db.Text)
    created_at              = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at              = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    medication = db.relationship("ProfileMedication", back_populates="schedule")
    dispatch_logs = db.relationship(
        "ReminderDispatchLog",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CC(
            "(end_date IS NULL) OR (start_date IS NULL) OR (start_date <= end_date)",
            name="ck_med_schedule_dates",
        ),
        UC("profile_medication_id", name="ux_med_schedules_medication"),
    )


class ReminderDispatchLog(db.Model):
    __tablename__ = "reminder_dispatch_logs"

    id            = db.Column(db.Integer, primary_key=True)
    schedule_id   = db.Column(db.Integer, FK("medication_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    channel       = db.Column(db.String(16), nullable=False)  # email|push|sms
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    sent_at       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status        = db.Column(db.String(16), nullable=False, default="sent")  # sent|failed|skipped
    detail        = db.Column(db.Text)

    schedule = db.relationship("MedicationSchedule", back_populates="dispatch_logs")

    __table_args__ = (
        CC("channel IN ('email','push','sms')", name="ck_reminder_dispatch_channel"),
        UC("schedule_id", "channel", "scheduled_for", name="ux_reminder_dispatch_unique"),
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


class SymptomSeverity(db.Model):
    __tablename__ = "symptom_severities"

    id               = db.Column(db.Integer, primary_key=True)
    symptom_entry_id = db.Column(db.Integer, FK("symptom_entries.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    score            = db.Column(db.Integer, nullable=False)
    level            = db.Column(db.String(16), nullable=False)  # low|moderate|high|critical
    factors          = db.Column(db.JSON, nullable=False, default=list)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CC("score >= 0 AND score <= 100", name="ck_symptom_severity_score"),
        CC("level IN ('low','moderate','high','critical')", name="ck_symptom_severity_level"),
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


class EmergencyContact(db.Model):
    __tablename__ = "emergency_contacts"

    id          = db.Column(db.Integer, primary_key=True)
    profile_id  = db.Column(db.Integer, FK("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name        = db.Column(db.String(255), nullable=False)
    relationship= db.Column(db.String(64))
    phone       = db.Column(db.String(32))
    email       = db.Column(db.String(255))
    is_primary  = db.Column(db.Boolean, nullable=False, default=False)
    notes       = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        IX("ix_emergency_profile_primary", "profile_id", "is_primary"),
    )


class FamilyMember(db.Model):
    __tablename__ = "family_members"

    id             = db.Column(db.Integer, primary_key=True)
    profile_id     = db.Column(db.Integer, FK("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name           = db.Column(db.String(255), nullable=False)
    relationship   = db.Column(db.String(64), nullable=False)
    birthdate      = db.Column(db.Date)
    notes          = db.Column(db.Text)
    share_preferences = db.Column(db.Boolean, nullable=False, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        IX("ix_family_profile_relationship", "profile_id", "relationship"),
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


class RateLimitHit(db.Model):
    __tablename__ = "rate_limit_hits"

    id         = db.Column(db.Integer, primary_key=True)
    key        = db.Column(db.String(255), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        IX("ix_rate_limit_hits_key_created", "key", "created_at"),
    )


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, FK("users.id", ondelete="SET NULL"))
    method       = db.Column(db.String(16), nullable=False)
    path         = db.Column(db.String(255), nullable=False, index=True)
    status_code  = db.Column(db.Integer, nullable=False)
    remote_addr  = db.Column(db.String(64))
    user_agent   = db.Column(db.String(255))
    duration_ms  = db.Column(db.Float)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        IX("ix_audit_logs_path_created", "path", "created_at"),
    )


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, FK("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token      = db.Column(db.String(128), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at    = db.Column(db.DateTime)

    __table_args__ = (
        IX("ix_password_reset_user_created", "user_id", "created_at"),
    )


class EmailVerificationToken(db.Model):
    __tablename__ = "email_verification_tokens"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, FK("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token      = db.Column(db.String(128), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at    = db.Column(db.DateTime)

    __table_args__ = (
        IX("ix_email_verification_user_created", "user_id", "created_at"),
    )


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, FK("users.id", ondelete="CASCADE"), index=True)
    jti            = db.Column(db.String(64), nullable=False, unique=True, index=True)
    token_type     = db.Column(db.String(16), nullable=False, default="refresh")
    issued_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at     = db.Column(db.DateTime)
    revoked_at     = db.Column(db.DateTime)
    revoked_reason = db.Column(db.String(255))


class MFAConfig(db.Model):
    __tablename__ = "mfa_totp_configs"

    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, FK("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    secret        = db.Column(db.String(64), nullable=False)
    enabled       = db.Column(db.Boolean, nullable=False, default=False)
    confirmed_at  = db.Column(db.DateTime)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class MFABackupCode(db.Model):
    __tablename__ = "mfa_backup_codes"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, FK("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash  = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    used_at    = db.Column(db.DateTime)

    __table_args__ = (
        UC("user_id", "code_hash", name="ux_mfa_backup_code_unique"),
    )

class UserPreferences(db.Model):
    __tablename__ = "user_preferences"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, FK("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    language     = db.Column(db.String(16), nullable=False, default="en")
    notify_email = db.Column(db.Boolean, nullable=False, default=True)
    notify_push  = db.Column(db.Boolean, nullable=False, default=False)
    notify_sms   = db.Column(db.Boolean, nullable=False, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="preferences")

    __table_args__ = (
        CC("language IN ('en','de','es','fr','it')", name="ck_user_pref_language"),
    )
