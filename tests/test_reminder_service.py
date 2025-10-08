from datetime import datetime, timedelta

from health_app import db
from health_app.models import (
    Drug,
    MedicationSchedule,
    Profile,
    ProfileMedication,
    ReminderDispatchLog,
    User,
    UserPreferences,
)
from health_app.services.reminder_service import build_reminder_payload, dispatch_due_reminders


def test_build_reminder_payload(app):
    with app.app_context():
        user = User(email="reminder@example.com", hashed_pwd="x")
        drug = Drug(name="lisinopril")
        db.session.add_all([user, drug])
        db.session.flush()

        profile = Profile(user_id=user.id)
        db.session.add(profile)
        db.session.flush()

        medication = ProfileMedication(profile_id=profile.id, drug_id=drug.id, dosage="10 mg")
        db.session.add(medication)
        db.session.flush()

        schedule = MedicationSchedule(
            profile_medication_id=medication.id,
            timezone="UTC",
            schedule_data='{"times": ["08:00", "20:00"]}',
            remind_via_email=True,
            remind_via_push=False,
            remind_via_sms=True,
        )
        db.session.add(schedule)
        db.session.commit()

        payload = build_reminder_payload(medication)
        assert payload["medication_id"] == medication.id
        assert payload["drug_name"] == "lisinopril"
        assert payload["reminders"]["channels"]["email"] is True
        assert payload["reminders"]["windows"][0]["time"] == "08:00"
        assert payload["next_reminder_at"] is not None


def test_next_reminder_future_start(app):
    with app.app_context():
        user = User(email="future@example.com", hashed_pwd="x")
        drug = Drug(name="amlodipine")
        db.session.add_all([user, drug])
        db.session.flush()

        profile = Profile(user_id=user.id)
        db.session.add(profile)
        db.session.flush()

        medication = ProfileMedication(profile_id=profile.id, drug_id=drug.id, dosage="5 mg")
        db.session.add(medication)
        db.session.flush()

        schedule = MedicationSchedule(
            profile_medication_id=medication.id,
            timezone="UTC",
            schedule_data='{"times": ["07:00"]}',
            start_date=datetime.utcnow().date() + timedelta(days=1),
        )
        db.session.add(schedule)
        db.session.commit()

        payload = build_reminder_payload(medication)
        assert payload["next_reminder_at"].startswith(str(schedule.start_date))


def test_dispatch_respects_preferences(app):
    with app.app_context():
        now = datetime(2025, 1, 1, 8, 0, 0)

        user = User(email="prefs@example.com", hashed_pwd="x")
        drug = Drug(name="Metformin")
        db.session.add_all([user, drug])
        db.session.flush()

        profile = Profile(user_id=user.id)
        db.session.add(profile)
        db.session.flush()

        prefs = UserPreferences(
            user_id=user.id,
            language="en",
            notify_email=False,
            notify_push=True,
            notify_sms=False,
        )
        db.session.add(prefs)

        medication = ProfileMedication(
            profile_id=profile.id,
            drug_id=drug.id,
            dosage="500 mg",
            started_at=now.date(),
        )
        db.session.add(medication)
        db.session.flush()

        schedule = MedicationSchedule(
            profile_medication_id=medication.id,
            timezone="UTC",
            schedule_data='{"times": ["08:00"]}',
            remind_via_email=True,
            remind_via_push=True,
            remind_via_sms=False,
        )
        db.session.add(schedule)
        db.session.commit()

        calls = []

        def push_sender(ctx):
            calls.append((ctx.channel, ctx.user.email, ctx.target_time))

        summary = dispatch_due_reminders(
            now=now,
            grace_minutes=0,
            senders={"push": push_sender},
        )

        assert summary["sent"] == 1
        assert summary["channels_attempted"] == 1
        assert calls and calls[0][0] == "push"

        logs = ReminderDispatchLog.query.all()
        assert len(logs) == 1
        assert logs[0].channel == "push"
        assert logs[0].scheduled_for == now


def test_dispatch_idempotent(app):
    with app.app_context():
        now = datetime(2025, 1, 1, 9, 30, 0)

        user = User(email="repeat@example.com", hashed_pwd="x")
        drug = Drug(name="Atorvastatin")
        db.session.add_all([user, drug])
        db.session.flush()

        profile = Profile(user_id=user.id)
        db.session.add(profile)
        db.session.flush()

        prefs = UserPreferences(user_id=user.id, language="en", notify_email=True)
        db.session.add(prefs)

        medication = ProfileMedication(
            profile_id=profile.id,
            drug_id=drug.id,
            dosage="20 mg",
            started_at=now.date(),
        )
        db.session.add(medication)
        db.session.flush()

        schedule = MedicationSchedule(
            profile_medication_id=medication.id,
            timezone="UTC",
            schedule_data='{"times": ["09:30"]}',
            remind_via_email=True,
        )
        db.session.add(schedule)
        db.session.commit()

        calls = []

        def email_sender(ctx):
            calls.append(ctx.target_time)

        summary_first = dispatch_due_reminders(
            now=now,
            grace_minutes=0,
            senders={"email": email_sender},
        )
        assert summary_first["sent"] == 1
        assert len(calls) == 1

        summary_second = dispatch_due_reminders(
            now=now + timedelta(minutes=1),
            grace_minutes=0,
            senders={"email": email_sender},
        )
        assert summary_second["sent"] == 0
        assert ReminderDispatchLog.query.count() == 1
