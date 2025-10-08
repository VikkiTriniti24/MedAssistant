from datetime import datetime
from types import SimpleNamespace

from health_app.utils import email as email_utils


class DummySMTP:
    def __init__(self, *args, **kwargs):
        self.started_tls = False
        self.logged_in = False
        self.sent_messages = []

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, msg):
        self.sent_messages.append(msg)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_send_email_uses_smtp(monkeypatch, app):
    dummy = DummySMTP()
    monkeypatch.setattr(email_utils, "smtplib", SimpleNamespace(SMTP=lambda *a, **k: dummy))

    with app.app_context():
        app.config.update(
            MAIL_SERVER="smtp.example.com",
            MAIL_USERNAME="user",
            MAIL_PASSWORD="pass",
            MAIL_USE_TLS=True,
            MAIL_PORT=587,
        )
        email_utils.send_email("Subject", "to@example.com", "Body")

    assert dummy.started_tls is True
    assert dummy.logged_in == ("user", "pass")
    assert dummy.sent_messages


def test_send_email_skips_when_unconfigured(app):
    with app.app_context():
        app.config.pop("MAIL_SERVER", None)
        email_utils.send_email("Subject", "to@example.com", "Body")  # should not raise


def test_password_reset_email_localisation(monkeypatch, app):
    captured = {}
    monkeypatch.setattr(
        email_utils,
        "send_email",
        lambda subject, recipient, body, **_: captured.update(subject=subject, body=body, recipient=recipient),
    )

    with app.app_context():
        app.config.setdefault("PASSWORD_RESET_URL", "https://example/reset")
        email_utils.send_password_reset_email(
            "user@example.com",
            "abc123",
            datetime(2025, 1, 1, 8, 0, 0),
            language="de",
        )

    assert captured["recipient"] == "user@example.com"
    assert captured["subject"] == "Passwort zurücksetzen"
    assert "Reset-Token" in captured["body"]
    assert "https://example/reset?token=abc123" in captured["body"]
