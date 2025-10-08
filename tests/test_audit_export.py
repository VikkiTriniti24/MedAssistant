from datetime import datetime, timedelta
import json

import pytest
from flask_jwt_extended import create_access_token

from health_app import db
from health_app.models import AuditLog, User


@pytest.fixture()
def seed_audit_logs(app):
    with app.app_context():
        AuditLog.query.delete()
        User.query.delete()
        db.session.commit()

        now = datetime.utcnow()
        earlier = now - timedelta(days=1)
        later = now + timedelta(hours=1)

        user_one = User(email="one@example.com", hashed_pwd="x")
        user_two = User(email="two@example.com", hashed_pwd="x")
        db.session.add_all([user_one, user_two])
        db.session.flush()

        db.session.add_all(
            [
                AuditLog(
                    user_id=user_one.id,
                    method="GET",
                    path="/health-check/",
                    status_code=200,
                    remote_addr="127.0.0.1",
                    user_agent="pytest-agent",
                    duration_ms=12.3,
                    created_at=earlier,
                ),
                AuditLog(
                    user_id=None,
                    method="POST",
                    path="/chat/",
                    status_code=201,
                    remote_addr="192.168.1.9",
                    user_agent="pytest-agent",
                    duration_ms=33.0,
                    created_at=now,
                ),
                AuditLog(
                    user_id=user_two.id,
                    method="GET",
                    path="/profile/export/",
                    status_code=200,
                    remote_addr="10.0.0.5",
                    user_agent="pytest-agent",
                    duration_ms=44.0,
                    created_at=later,
                ),
            ]
        )
        db.session.commit()
        return {
            "user_one": user_one.id,
            "user_two": user_two.id,
        }


def test_cli_json_export(app, runner, seed_audit_logs):
    _ = seed_audit_logs
    result = runner.invoke(
        args=["export-audit-logs", "--start", (datetime.utcnow() - timedelta(days=2)).isoformat(), "--pseudonymize"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["count"] == 3
    assert payload["items"][0]["user"].startswith("user-") or payload["items"][0]["user"] is None
    assert payload["items"][0]["remote_addr"].startswith("ip-")


def test_cli_csv_export(app, runner, seed_audit_logs):
    seed_info = seed_audit_logs
    result = runner.invoke(
        args=[
            "export-audit-logs",
            "--format",
            "csv",
            "--user-id",
            str(seed_info["user_one"]),
        ]
    )
    assert result.exit_code == 0
    output = result.output.strip()
    assert output.splitlines()[0].startswith("id,")
    assert "user_id" in output
    assert len(output.splitlines()) == 2  # header + one row


@pytest.fixture()
def admin_headers(app):
    with app.app_context():
        user = User(email="support@example.com", hashed_pwd="hash")
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={"role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_http_audit_export_requires_admin(client, auth_headers):
    resp = client.get("/support/audit-export", headers=auth_headers)
    assert resp.status_code == 403


def test_http_audit_export_json(client, admin_headers, seed_audit_logs):
    resp = client.get("/support/audit-export", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 3
    assert {item["path"] for item in data["items"]} == {"/health-check/", "/chat/", "/profile/export/"}


def test_http_audit_export_csv_pseudonymized(client, admin_headers, seed_audit_logs):
    resp = client.get(
        "/support/audit-export?format=csv&pseudonymize=true&start=1970-01-01",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("text/csv")
    body = resp.get_data(as_text=True)
    assert "user" in body
    assert "user_id" not in body
