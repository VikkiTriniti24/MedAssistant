import pytest

from health_app import create_app


@pytest.mark.parametrize(
    "secret_key,jwt_secret",
    [
        ("dev-secret", "custom"),
        ("custom", "dev-jwt-secret"),
        ("", ""),
    ],
)
def test_create_app_rejects_default_secrets(monkeypatch, secret_key, jwt_secret):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", secret_key)
    monkeypatch.setenv("JWT_SECRET_KEY", jwt_secret)

    with pytest.raises(RuntimeError) as exc:
        create_app()

    assert "Production startup aborted" in str(exc.value)


def test_create_app_allows_custom_secrets(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "prod-secret-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "prod-jwt-secret")

    app = create_app()

    assert app.config["SECRET_KEY"] == "prod-secret-key"
    assert app.config["JWT_SECRET_KEY"] == "prod-jwt-secret"

    # Cleanup to avoid leaking production env into other tests
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
