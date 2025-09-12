# health_app/__init__.py
import os
import logging
from pathlib import Path

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from dotenv import load_dotenv

# --- Extensions --------------------------------------------------------------
db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()

logger = logging.getLogger("health_app")
if not logger.handlers:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


def create_app() -> Flask:
    """
    Application factory:
    - load .env
    - set config defaults (overridable via env / instance/config.py)
    - init extensions
    - ensure dev DB (inside app context, dev/testing only)
    - register blueprints
    """
    load_dotenv()

    pkg_dir = Path(__file__).resolve().parent            # .../health_app
    instance_dir = pkg_dir.parent / "instance"           # <root>/instance

    app = Flask(
        __name__,
        static_folder=str(pkg_dir / "static"),
        template_folder=str(pkg_dir / "templates"),
        instance_relative_config=True,
    )

    os.makedirs(app.instance_path, exist_ok=True)

    default_db_path = instance_dir / "health_app.db"
    app.config.from_mapping(
        # Flask
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret"),
        ENV=os.getenv("FLASK_ENV", os.getenv("ENV", "development")),
        VERSION=os.getenv("VERSION", "0.1.0"),
        JSON_SORT_KEYS=False,

        # SQLAlchemy
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL",
            f"sqlite:///{default_db_path}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,

        # JWT
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "dev-jwt-secret"),
        JWT_TOKEN_LOCATION=["headers"],
        JWT_HEADER_NAME=os.getenv("JWT_HEADER_NAME", "Authorization"),
        JWT_HEADER_TYPE=os.getenv("JWT_HEADER_TYPE", "Bearer"),
    )

    # Optional instance overrides
    app.config.from_pyfile("config.py", silent=True)

    # Init extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # ---- Dev DB bootstrap (inside app context!) ----------------------------
    try:
        from .utils.dev_setup import ensure_dev_db
        with app.app_context():
            ensure_dev_db(app)  # pass app explicitly, runs only in dev/testing
    except Exception as exc:
        app.logger.warning("Dev DB bootstrap skipped/failed: %s", exc)

    # Helpful (robust) logging for templates
    try:
        loader = app.jinja_env.loader
        # Not all loaders have 'searchpath'; fall back to template_folder
        search_paths = getattr(loader, "searchpath", None)
        app.logger.info(
            "Jinja search paths: %s",
            search_paths if search_paths else [app.template_folder]
        )
    except Exception as e:
        app.logger.debug("Template loader info unavailable: %s", e)

    # Register blueprints
    from .routes.web import web_bp
    from .routes.auth import auth_bp
    from .routes.health_check import health_check_bp
    from .routes.drug_check import drug_check_bp
    from .routes.chat import chat_bp

    app.register_blueprint(web_bp,          url_prefix="")
    app.register_blueprint(auth_bp,         url_prefix="/auth")
    app.register_blueprint(health_check_bp, url_prefix="/health-check")
    app.register_blueprint(drug_check_bp,   url_prefix="/drug-check")
    app.register_blueprint(chat_bp,         url_prefix="/chat")

    return app


__all__ = ["create_app", "db", "jwt", "migrate"]
