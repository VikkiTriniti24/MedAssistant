from datetime import timedelta

# Security / JWT
JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)

# Flask
JSON_SORT_KEYS = False
PREFERRED_URL_SCHEME = "http"   # Setze auf "https" in Prod

# Cookies (in Prod aktivieren)
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False   # True hinter einem HTTPS-Proxy

# App Meta (wird im Template benutzt)
VERSION = "0.1.0"
ENV = "development"

# SQLAlchemy – optional, wenn du den Default überschreiben willst
# SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://user:pass@localhost:5432/health_app"
