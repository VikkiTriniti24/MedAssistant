from http import HTTPStatus


def test_security_headers_present(client):
    resp = client.get("/healthz")
    assert resp.status_code == HTTPStatus.OK
    headers = resp.headers

    assert headers.get("Strict-Transport-Security", "").startswith("max-age=")
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")


def test_max_content_length_config(app):
    assert app.config["MAX_CONTENT_LENGTH"] == 1_048_576


def test_session_cookie_defaults(app):
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
