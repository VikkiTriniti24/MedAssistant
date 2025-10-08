from datetime import datetime, timedelta
from http import HTTPStatus

import pytest

from health_app import db
from health_app.models import User


pytestmark = pytest.mark.slow


def test_account_lockout_after_failed_attempts(client, app):
    email = "lockout@example.com"
    password = "Str0ngPass!"

    client.post("/auth/register", json={"email": email, "password": password})

    max_attempts = app.config["LOGIN_MAX_ATTEMPTS"]

    for attempt in range(max_attempts):
        resp = client.post(
            "/auth/login",
            json={"email": email, "password": "wrong"},
        )
        if attempt == max_attempts - 1:
            assert resp.status_code == HTTPStatus.LOCKED
        else:
            assert resp.status_code == HTTPStatus.UNAUTHORIZED

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user.locked_until is not None

        # Expire lockout manually and persist
        user.locked_until = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()

    success_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert success_resp.status_code == HTTPStatus.OK

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
