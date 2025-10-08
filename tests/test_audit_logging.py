from http import HTTPStatus

from datetime import datetime, timedelta

import pytest

from health_app import db
from health_app.models import AuditLog


pytestmark = pytest.mark.slow


def test_audit_log_records_authenticated_call(app, client, auth_headers):
    payload = {"symptoms": "dry cough"}

    with app.app_context():
        before = AuditLog.query.count()

    response = client.post("/health-check/", headers=auth_headers, json=payload)
    assert response.status_code == HTTPStatus.OK

    with app.app_context():
        after = AuditLog.query.count()
        assert after > before
        latest = AuditLog.query.order_by(AuditLog.id.desc()).first()
        assert latest is not None
        assert latest.path == "/health-check/"
        assert latest.method == "POST"
        assert latest.status_code == HTTPStatus.OK
        assert latest.user_id is not None


def test_audit_log_can_be_disabled(app, client):
    app.config["AUDIT_LOG_ENABLED"] = False

    with app.app_context():
        before = AuditLog.query.count()

    resp = client.get("/")
    assert resp.status_code == HTTPStatus.OK

    with app.app_context():
        after = AuditLog.query.count()
        assert after == before


def test_prune_audit_logs_cli(app, runner):
    with app.app_context():
        db.session.add_all(
            [
                AuditLog(
                    user_id=None,
                    method="GET",
                    path="/old",
                    status_code=200,
                    created_at=datetime.utcnow() - timedelta(days=120),
                ),
                AuditLog(
                    user_id=None,
                    method="GET",
                    path="/recent",
                    status_code=200,
                ),
            ]
        )
        db.session.commit()

    result = runner.invoke(args=["prune-audit-logs", "--days=90"])
    assert result.exit_code == 0
    assert "Deleted" in result.output

    with app.app_context():
        paths = [row.path for row in AuditLog.query.all()]
        assert "/old" not in paths
        assert "/recent" in paths
