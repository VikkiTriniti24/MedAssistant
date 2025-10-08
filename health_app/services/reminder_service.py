"""Medication reminder scheduling utilities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Callable, Dict, Iterable, List, Optional

from zoneinfo import ZoneInfo

from flask import current_app

from .. import db
from ..models import (
    MedicationSchedule,
    ProfileMedication,
    ReminderDispatchLog,
    User,
    UserPreferences,
)
from ..utils.email import send_email


def _safe_json(raw: str) -> Dict[str, object]:
    import json

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _parse_times(schedule_data: Dict[str, Iterable[str]]) -> List[str]:
    times = schedule_data.get("times", []) if schedule_data else []
    return [str(t) for t in times if t]


def _apply_timezone(t: time, tz: ZoneInfo, base_date) -> datetime:
    return datetime.combine(base_date, t, tzinfo=tz)


def _next_occurrence(
    schedule: MedicationSchedule,
    schedule_data: Dict[str, object],
    *,
    reference: Optional[datetime] = None,
) -> Optional[str]:
    times = _parse_times(schedule_data)
    if not times:
        return None

    tz_name = schedule.timezone or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    if reference is not None:
        ref = reference
        if ref.tzinfo:
            now = ref.astimezone(tz)
        else:
            now = ref.replace(tzinfo=timezone.utc).astimezone(tz)
    else:
        now = datetime.now(tz)
    start_date = schedule.start_date or now.date()
    if start_date > now.date():
        current_date = start_date
    else:
        current_date = now.date()

    end_date = schedule.end_date

    parsed_times: List[time] = []
    for entry in times:
        try:
            hour, minute = entry.split(":")
            parsed_times.append(time(int(hour), int(minute)))
        except Exception:
            continue

    if not parsed_times:
        return None

    for day_offset in range(0, 14):
        candidate_date = current_date + timedelta(days=day_offset)
        if end_date and candidate_date > end_date:
            break
        for t in sorted(parsed_times):
            candidate_dt = _apply_timezone(t, tz, candidate_date)
            if candidate_dt >= now:
                return candidate_dt.isoformat()
    return None


def generate_reminder_windows(schedule: MedicationSchedule) -> List[Dict[str, str]]:
    schedule_data = _safe_json(schedule.schedule_data)
    times = _parse_times(schedule_data)
    return [
        {
            "time": t,
            "timezone": schedule.timezone,
        }
        for t in times
    ]


def build_reminder_payload(
    medication: ProfileMedication,
    *,
    reference: Optional[datetime] = None,
) -> Dict[str, object]:
    schedule = medication.schedule
    if not schedule:
        return {}

    schedule_data = _safe_json(schedule.schedule_data)
    windows = generate_reminder_windows(schedule)
    next_occurrence = _next_occurrence(schedule, schedule_data, reference=reference)

    return {
        "medication_id": medication.id,
        "drug_name": medication.drug.name if medication.drug else None,
        "dosage": medication.dosage,
        "schedule": schedule_data,
        "next_reminder_at": next_occurrence,
        "reminders": {
            "windows": windows,
            "channels": {
                "email": schedule.remind_via_email,
                "push": schedule.remind_via_push,
                "sms": schedule.remind_via_sms,
            },
        },
    }


@dataclass
class ReminderDeliveryContext:
    channel: str
    user: User
    medication: ProfileMedication
    schedule: MedicationSchedule
    target_time: datetime
    payload: Dict[str, object]


SenderFn = Callable[[ReminderDeliveryContext], None]


def _parse_iso_to_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _preference_flags(user: User) -> Dict[str, bool]:
    prefs = getattr(user, "preferences", None)
    if isinstance(prefs, UserPreferences):
        return {
            "email": bool(prefs.notify_email),
            "push": bool(prefs.notify_push),
            "sms": bool(prefs.notify_sms),
        }
    # Defaults align with model defaults
    return {"email": True, "push": False, "sms": False}


def _channels_for(schedule: MedicationSchedule, user: User) -> Dict[str, bool]:
    prefs = _preference_flags(user)
    return {
        "email": bool(schedule.remind_via_email and prefs.get("email")),
        "push": bool(schedule.remind_via_push and prefs.get("push")),
        "sms": bool(schedule.remind_via_sms and prefs.get("sms")),
    }


def _already_dispatched(schedule_id: int, channel: str, scheduled_for: datetime) -> bool:
    existing = ReminderDispatchLog.query.filter_by(
        schedule_id=schedule_id,
        channel=channel,
        scheduled_for=scheduled_for,
    ).first()
    return existing is not None


def _create_dispatch_log(
    schedule_id: int,
    channel: str,
    scheduled_for: datetime,
    *,
    status: str,
    detail: Optional[str] = None,
) -> ReminderDispatchLog:
    log = ReminderDispatchLog(
        schedule_id=schedule_id,
        channel=channel,
        scheduled_for=scheduled_for,
        status=status,
        detail=detail,
    )
    db.session.add(log)
    return log


def _send_email_channel(ctx: ReminderDeliveryContext) -> None:
    recipient = ctx.user.email
    if not recipient:
        raise ValueError("user has no email address configured")

    drug_name = ctx.payload.get("drug_name") or ctx.medication.dosage or "Medication"
    subject = f"MedAssistant Erinnerung: {drug_name}"
    body_lines = [
        f"Dies ist eine Erinnerung für Ihre Medikation {drug_name}.",
    ]
    dosage = ctx.payload.get("dosage")
    if dosage:
        body_lines.append(f"Dosis: {dosage}")
    body_lines.append(f"Geplanter Zeitpunkt: {ctx.target_time.isoformat()} UTC")
    body_lines.append("Bitte beachten Sie Ihren individuellen Einnahmeplan.")

    send_email(subject, recipient, "\n".join(body_lines))


def _send_push_channel(ctx: ReminderDeliveryContext) -> None:
    current_app.logger.info(
        "dispatch-reminder | channel=push user=%s medication=%s time=%s",
        ctx.user.id,
        ctx.payload.get("drug_name"),
        ctx.target_time.isoformat(),
    )


def _send_sms_channel(ctx: ReminderDeliveryContext) -> None:
    current_app.logger.info(
        "dispatch-reminder | channel=sms user=%s medication=%s time=%s",
        ctx.user.id,
        ctx.payload.get("drug_name"),
        ctx.target_time.isoformat(),
    )


DEFAULT_SENDERS: Dict[str, SenderFn] = {
    "email": _send_email_channel,
    "push": _send_push_channel,
    "sms": _send_sms_channel,
}


def dispatch_due_reminders(
    *,
    now: Optional[datetime] = None,
    grace_minutes: int = 5,
    senders: Optional[Dict[str, SenderFn]] = None,
) -> Dict[str, int]:
    """Process medication schedules and dispatch reminders when due."""

    current_time = now or datetime.utcnow()
    tolerance = timedelta(minutes=max(grace_minutes, 0))
    sender_map = {**DEFAULT_SENDERS, **(senders or {})}

    summary = {
        "schedules_checked": 0,
        "channels_attempted": 0,
        "sent": 0,
        "failed": 0,
        "skipped": 0,
    }

    changed = False

    schedules = MedicationSchedule.query.all()
    today = current_time.date()

    for schedule in schedules:
        summary["schedules_checked"] += 1

        medication = schedule.medication
        if not medication:
            summary["skipped"] += 1
            continue

        if medication.ended_at and medication.ended_at < today:
            summary["skipped"] += 1
            continue

        profile = medication.profile
        user = getattr(profile, "user", None)
        if not user or not getattr(user, "is_active", True):
            summary["skipped"] += 1
            continue

        if schedule.end_date and schedule.end_date < today:
            summary["skipped"] += 1
            continue

        payload = build_reminder_payload(medication, reference=current_time)
        next_at = _parse_iso_to_utc(payload.get("next_reminder_at"))
        if not next_at:
            summary["skipped"] += 1
            continue

        if next_at > current_time + tolerance:
            summary["skipped"] += 1
            continue

        channels = _channels_for(schedule, user)
        if not any(channels.values()):
            summary["skipped"] += 1
            continue

        for channel, enabled in channels.items():
            if not enabled:
                continue

            sender = sender_map.get(channel)
            if sender is None:
                current_app.logger.warning("No sender configured for channel %s", channel)
                summary["skipped"] += 1
                continue

            if _already_dispatched(schedule.id, channel, next_at):
                summary["skipped"] += 1
                continue

            summary["channels_attempted"] += 1
            ctx = ReminderDeliveryContext(
                channel=channel,
                user=user,
                medication=medication,
                schedule=schedule,
                target_time=next_at,
                payload=payload,
            )

            try:
                sender(ctx)
                _create_dispatch_log(schedule.id, channel, next_at, status="sent")
                changed = True
                summary["sent"] += 1
            except Exception as exc:  # pragma: no cover - exceptional path
                current_app.logger.exception(
                    "Failed to send reminder | channel=%s schedule=%s", channel, schedule.id
                )
                _create_dispatch_log(
                    schedule.id,
                    channel,
                    next_at,
                    status="failed",
                    detail=str(exc),
                )
                changed = True
                summary["failed"] += 1

    if changed:
        db.session.commit()

    return summary


__all__ = [
    "build_reminder_payload",
    "generate_reminder_windows",
    "dispatch_due_reminders",
]
