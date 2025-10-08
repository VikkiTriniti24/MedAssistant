"""Lightweight SMTP email helpers."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Iterable, Optional, Tuple

from flask import current_app
from .i18n import normalize_language


def _build_message(subject: str, sender: str, recipients: Iterable[str], body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)
    return msg


def send_email(subject: str, recipient: str, body: str, *, sender: Optional[str] = None) -> None:
    """Send an email using configured SMTP settings. Fails silently if misconfigured."""
    app = current_app
    mail_server = app.config.get("MAIL_SERVER")
    if not mail_server:
        app.logger.info("MAIL_SERVER not configured; skipping email to %s", recipient)
        return

    sender = sender or app.config.get("MAIL_DEFAULT_SENDER", "no-reply@localhost")
    msg = _build_message(subject, sender, [recipient], body)

    port = int(app.config.get("MAIL_PORT", 587))
    use_tls = app.config.get("MAIL_USE_TLS", True)
    username = app.config.get("MAIL_USERNAME")
    password = app.config.get("MAIL_PASSWORD")

    try:
        with smtplib.SMTP(mail_server, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
    except Exception as exc:
        app.logger.warning("Failed to send email to %s: %s", recipient, exc)


_EMAIL_TEMPLATES = {
    "password_reset": {
        "subject": {
            "en": "Password Reset",
            "de": "Passwort zurücksetzen",
        },
        "body": {
            "en": (
                "You requested a password reset for MedAssistant.\n\n"
                "Reset token: {token}\n"
                "Expires at: {expires} UTC\n\n"
                "If a reset URL is configured, you can visit:\n{link}\n\n"
                "If you did not request this, you can ignore this email."
            ),
            "de": (
                "Du hast eine Passwortzurücksetzung für MedAssistant angefordert.\n\n"
                "Reset-Token: {token}\n"
                "Gültig bis: {expires} UTC\n\n"
                "Falls eine Reset-URL konfiguriert ist, kannst du sie hier öffnen:\n{link}\n\n"
                "Wenn du diese Anfrage nicht gestellt hast, kannst du diese E-Mail ignorieren."
            ),
        },
    },
    "email_verification": {
        "subject": {
            "en": "Email Verification",
            "de": "E-Mail-Verifizierung",
        },
        "body": {
            "en": (
                "Please verify your MedAssistant email address.\n\n"
                "Verification token: {token}\n"
                "Expires at: {expires} UTC\n\n"
                "To complete verification, follow this link if available:\n{link}\n\n"
                "If you did not create an account, you can ignore this email."
            ),
            "de": (
                "Bitte bestätige deine MedAssistant-E-Mail-Adresse.\n\n"
                "Verifizierungscode: {token}\n"
                "Gültig bis: {expires} UTC\n\n"
                "Zum Abschluss der Verifizierung kannst du (falls verfügbar) diesen Link öffnen:\n{link}\n\n"
                "Wenn du kein Konto erstellt hast, kannst du diese E-Mail ignorieren."
            ),
        },
    },
}


def _render_email(kind: str, language: str, **context) -> Tuple[str, str]:
    lang = normalize_language(language)
    template = _EMAIL_TEMPLATES[kind]
    subject_template = template["subject"].get(lang) or template["subject"]["en"]
    body_template = template["body"].get(lang) or template["body"]["en"]
    return subject_template.format(**context), body_template.format(**context)


def send_password_reset_email(
    recipient: str,
    token: str,
    expires_at,
    *,
    language: str = "en",
) -> None:
    app = current_app
    reset_url = app.config.get("PASSWORD_RESET_URL")
    if reset_url:
        reset_link = f"{reset_url}?token={token}"
    else:
        reset_link = token  # fallback for dev/testing

    subject, body = _render_email(
        "password_reset",
        language,
        token=token,
        expires=expires_at.isoformat(),
        link=reset_link,
    )
    send_email(subject, recipient, body)


def send_email_verification(
    recipient: str,
    token: str,
    expires_at,
    *,
    language: str = "en",
) -> None:
    app = current_app
    verify_url = app.config.get("EMAIL_VERIFICATION_URL")
    if verify_url:
        verify_link = f"{verify_url}?token={token}"
    else:
        verify_link = token

    subject, body = _render_email(
        "email_verification",
        language,
        token=token,
        expires=expires_at.isoformat(),
        link=verify_link,
    )
    send_email(subject, recipient, body)
