# health_app/__init__.py
import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
import shutil
import secrets
from typing import Optional

import click
from flask import Flask, g, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from dotenv import load_dotenv

from .utils.rate_limit import PersistentRateLimiter, SimpleRateLimiter

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
    max_body_bytes = int(os.getenv("MAX_CONTENT_LENGTH", "1048576"))
    app.config.from_mapping(
        # Flask
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret"),
        ENV=os.getenv("FLASK_ENV", os.getenv("ENV", "development")),
        VERSION=os.getenv("VERSION", "0.1.0"),
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=max_body_bytes,
        RATE_LIMIT_DEFAULT_LIMIT=int(os.getenv("RATE_LIMIT_DEFAULT_LIMIT", "60")),
        RATE_LIMIT_DEFAULT_WINDOW=int(os.getenv("RATE_LIMIT_DEFAULT_WINDOW", "60")),
        RATE_LIMIT_AUTH_LIMIT=int(os.getenv("RATE_LIMIT_AUTH_LIMIT", "30")),
        RATE_LIMIT_AUTH_WINDOW=int(os.getenv("RATE_LIMIT_AUTH_WINDOW", "60")),
        RATE_LIMIT_HEALTH_CHECK_LIMIT=int(os.getenv("RATE_LIMIT_HEALTH_CHECK_LIMIT", "40")),
        RATE_LIMIT_HEALTH_CHECK_WINDOW=int(os.getenv("RATE_LIMIT_HEALTH_CHECK_WINDOW", "60")),
        RATE_LIMIT_CHAT_LIMIT=int(os.getenv("RATE_LIMIT_CHAT_LIMIT", "60")),
        RATE_LIMIT_CHAT_WINDOW=int(os.getenv("RATE_LIMIT_CHAT_WINDOW", "60")),
        RATE_LIMIT_DRUG_CHECK_LIMIT=int(os.getenv("RATE_LIMIT_DRUG_CHECK_LIMIT", "25")),
        RATE_LIMIT_DRUG_CHECK_WINDOW=int(os.getenv("RATE_LIMIT_DRUG_CHECK_WINDOW", "60")),
        RATE_LIMITING_DISABLED=os.getenv("RATE_LIMITING_DISABLED", "0") in {"1", "true", "True"},
        RATE_LIMIT_ROLE_MULTIPLIER_USER=float(os.getenv("RATE_LIMIT_ROLE_MULTIPLIER_USER", "1.0")),
        RATE_LIMIT_ROLE_MULTIPLIER_ADMIN=float(os.getenv("RATE_LIMIT_ROLE_MULTIPLIER_ADMIN", "2.0")),
        CHAT_HISTORY_RETENTION_DAYS=int(os.getenv("CHAT_HISTORY_RETENTION_DAYS", "90")),
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.getenv("SESSION_COOKIE_SAMESITE", "Lax"),
        AUDIT_LOG_ENABLED=os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true",
        AUDIT_LOG_EXCLUDE_PREFIXES=tuple(
            p.strip()
            for p in os.getenv(
                "AUDIT_LOG_EXCLUDE_PREFIXES",
                "/static,/favicon.ico,/healthz",
            ).split(",")
            if p.strip()
        ),
        AUDIT_LOG_RETENTION_DAYS=int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "90")),
        PASSWORD_RESET_TOKEN_MINUTES=int(os.getenv("PASSWORD_RESET_TOKEN_MINUTES", "30")),
        EMAIL_VERIFICATION_TOKEN_MINUTES=int(os.getenv("EMAIL_VERIFICATION_TOKEN_MINUTES", "60")),
        EMAIL_VERIFICATION_URL=os.getenv("EMAIL_VERIFICATION_URL"),
        MAIL_SERVER=os.getenv("MAIL_SERVER"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
        MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "true").lower() in {"1", "true", "yes"},
        MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", "no-reply@medassistant.local"),

        # SQLAlchemy
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL",
            f"sqlite:///{default_db_path}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,

        # JWT
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "dev-jwt-secret"),
        JWT_TOKEN_LOCATION=["headers", "cookies"],
        JWT_HEADER_NAME=os.getenv("JWT_HEADER_NAME", "Authorization"),
        JWT_HEADER_TYPE=os.getenv("JWT_HEADER_TYPE", "Bearer"),
        JWT_ACCESS_TOKEN_EXPIRES=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "1800")),
        JWT_REFRESH_TOKEN_EXPIRES=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", "604800")),
        JWT_REFRESH_COOKIE_NAME=os.getenv("JWT_REFRESH_COOKIE_NAME", "refresh_token"),
        JWT_REFRESH_COOKIE_SECURE=os.getenv("JWT_REFRESH_COOKIE_SECURE", "true").lower() == "true",
        JWT_REFRESH_COOKIE_SAMESITE=os.getenv("JWT_REFRESH_COOKIE_SAMESITE", "Lax"),
        JWT_COOKIE_CSRF_PROTECT=os.getenv("JWT_COOKIE_CSRF_PROTECT", "false").lower() in {"1", "true", "yes"},

        # Auth lockout
        LOGIN_MAX_ATTEMPTS=int(os.getenv("LOGIN_MAX_ATTEMPTS", "5")),
        LOGIN_LOCKOUT_MINUTES=int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15")),
    )

    # Optional instance overrides
    app.config.from_pyfile("config.py", silent=True)

    # Init extensions
    db.init_app(app)
    from flask_jwt_extended import JWTManager

    JWTManager(app)  # init, Variable nicht nötig
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

    @app.before_request
    def _set_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def inject_security_nonce():
        return {'csp_nonce': getattr(g, 'csp_nonce', '')}

    @app.before_request
    def _capture_audit_start():
        if app.config.get("AUDIT_LOG_ENABLED", True):
            g.audit_start = time.perf_counter()

    @app.after_request
    def apply_security_headers(resp):
        """Attach baseline security headers to every response unless preset."""
        nonce = getattr(g, 'csp_nonce', None)
        if not nonce:
            nonce = secrets.token_urlsafe(16)
            g.csp_nonce = nonce

        script_src = ["'self'", f"'nonce-{nonce}'"]
        style_src = ["'self'"]

        csp_value = (
            "default-src 'self'; "
            f"script-src {' '.join(script_src)}; "
            f"style-src {' '.join(style_src)}; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "object-src 'none'"
        )

        security_headers = {
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
        }
        resp.headers['Content-Security-Policy'] = csp_value
        for header, value in security_headers.items():
            resp.headers.setdefault(header, value)
        return resp

    @app.after_request
    def log_audit_event(resp):
        if not app.config.get("AUDIT_LOG_ENABLED", True):
            return resp

        path = request.path or ""
        exclude_prefixes = app.config.get("AUDIT_LOG_EXCLUDE_PREFIXES", ())
        if any(path.startswith(prefix) for prefix in exclude_prefixes):
            return resp

        try:
            duration = None
            if hasattr(g, "audit_start"):
                duration = (time.perf_counter() - g.audit_start) * 1000

            user_id = None
            try:
                from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

                verify_jwt_in_request(optional=True)
                identity = get_jwt_identity()
                if identity is not None:
                    try:
                        user_id = int(identity)
                    except (TypeError, ValueError):
                        user_id = None
            except Exception:
                user_id = None

            from .models import AuditLog

            log_entry = AuditLog(
                user_id=user_id,
                method=request.method,
                path=path[:255],
                status_code=resp.status_code,
                remote_addr=(request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:64],
                user_agent=(request.user_agent.string or "")[:255],
                duration_ms=duration,
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as exc:
            app.logger.debug("Audit log skipped: %s", exc)
            db.session.rollback()

        return resp

    try:
        app.extensions["rate_limiter"] = PersistentRateLimiter(db)
    except Exception:
        # Fallback to in-memory limiter if DB setup fails early
        app.extensions["rate_limiter"] = SimpleRateLimiter()

    @app.cli.command("backup-db")
    @click.option(
        "--dest",
        type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
        help="Output directory for the backup (defaults to instance/backups)",
    )
    def backup_db(dest: Optional[str] = None) -> None:
        """Create a timestamped copy of the SQLite database."""
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if not uri.startswith("sqlite:///"):
            click.echo("Only SQLite databases are supported by this backup command.")
            return

        src_path = Path(uri.replace("sqlite:///", ""))
        if not src_path.exists():
            click.echo(f"Database file not found: {src_path}")
            return

        backup_dir = Path(dest) if dest else (Path(app.instance_path) / "backups")
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        backup_name = f"{src_path.stem}-{timestamp}{src_path.suffix or '.db'}"
        backup_path = backup_dir / backup_name

        shutil.copy2(src_path, backup_path)
        click.echo(f"Database backup created at {backup_path}")

    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        try:
            if normalized.endswith("Z"):
                normalized = normalized[:-1]
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise click.BadParameter(f"Invalid ISO timestamp: {value}") from exc
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @app.cli.command("prune-audit-logs")
    @click.option(
        "--days",
        type=int,
        help="Delete audit entries older than this many days (default from AUDIT_LOG_RETENTION_DAYS)",
    )
    def prune_audit_logs(days: Optional[int] = None) -> None:
        """Remove audit log rows older than N days."""
        retention_days = days or int(app.config.get("AUDIT_LOG_RETENTION_DAYS", 90))
        if retention_days <= 0:
            click.echo("Retention must be positive.")
            return

        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        from .models import AuditLog

        deleted = AuditLog.query.filter(AuditLog.created_at < cutoff).delete()
        db.session.commit()
        click.echo(f"Deleted {deleted} audit log entries older than {retention_days} days.")

    @app.cli.command("export-audit-logs")
    @click.option("--start", "start_ts", help="ISO-8601 timestamp inclusive lower bound")
    @click.option("--end", "end_ts", help="ISO-8601 timestamp inclusive upper bound")
    @click.option("--user-id", type=int, help="Filter by a specific user id")
    @click.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "csv"], case_sensitive=False),
        default="json",
        show_default=True,
    )
    @click.option(
        "--output",
        type=click.Path(dir_okay=False, writable=True, resolve_path=True),
        help="Optional output file path (stdout if omitted)",
    )
    @click.option("--pseudonymize/--no-pseudonymize", default=False, show_default=True)
    def export_audit_logs(start_ts, end_ts, user_id, fmt, output, pseudonymize):
        """Export audit logs as JSON or CSV with optional pseudonymisation."""
        from .services.audit_exporter import (
            AuditExportFilters,
            fetch_audit_rows,
            log_export,
            serialize_csv,
            serialize_rows,
        )

        filters = AuditExportFilters(
            start=_parse_iso_datetime(start_ts),
            end=_parse_iso_datetime(end_ts),
            user_id=user_id,
        )

        rows = fetch_audit_rows(filters)
        log_export(filters, len(rows), via="cli")

        if fmt.lower() == "csv":
            payload = serialize_csv(rows, pseudonymize=pseudonymize)
        else:
            data = serialize_rows(rows, pseudonymize=pseudonymize)
            payload = json.dumps({"count": len(data), "items": data}, indent=2)

        if output:
            path = Path(output)
            path.write_text(payload or "", encoding="utf-8")
            click.echo(f"Wrote {len(rows)} rows to {path}")
        else:
            click.echo(payload)

    @app.cli.command("dispatch-reminders")
    @click.option(
        "--grace-minutes",
        type=int,
        default=5,
        show_default=True,
        help="Allow reminders scheduled within this many minutes in the future",
    )
    def dispatch_reminders(grace_minutes: int) -> None:
        """Run the reminder dispatcher once."""
        from .services.reminder_service import dispatch_due_reminders

        summary = dispatch_due_reminders(grace_minutes=grace_minutes)
        click.echo(
            " | ".join(
                [
                    f"checked={summary['schedules_checked']}",
                    f"attempted={summary['channels_attempted']}",
                    f"sent={summary['sent']}",
                    f"failed={summary['failed']}",
                    f"skipped={summary['skipped']}",
                ]
            )
        )

    @app.cli.command("prune-chat-history")
    @click.option(
        "--days",
        type=int,
        help="Delete chat messages and sessions older than this many days (defaults to CHAT_HISTORY_RETENTION_DAYS)",
    )
    def prune_chat_history(days: Optional[int] = None) -> None:
        """Remove chat history older than N days and orphaned sessions."""
        retention_days = days or int(app.config.get("CHAT_HISTORY_RETENTION_DAYS", 90))
        if retention_days <= 0:
            click.echo("Retention must be positive.")
            return

        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        from .models import ChatMessage, ChatSession

        messages_deleted = ChatMessage.query.filter(ChatMessage.sent_at < cutoff).delete(synchronize_session=False)
        db.session.commit()

        sessions_deleted = ChatSession.query.filter(
            ChatSession.created_at < cutoff,
            ~ChatSession.messages.any(),
        ).delete(synchronize_session=False)
        db.session.commit()

        click.echo(
            f"Deleted {messages_deleted} chat messages and {sessions_deleted} chat sessions older than {retention_days} days."
        )

    # Register blueprints
    from .routes.web import web_bp
    from .routes.auth import auth_bp
    from .routes.health_check import health_check_bp
    from .routes.drug_check import drug_check_bp
    from .routes.chat import chat_bp
    from .routes.profile import profile_bp
    from .routes.support import support_bp

    app.register_blueprint(web_bp,          url_prefix="")
    app.register_blueprint(auth_bp,         url_prefix="/auth")
    app.register_blueprint(health_check_bp, url_prefix="/health-check")
    app.register_blueprint(drug_check_bp,   url_prefix="/drug-check")
    app.register_blueprint(chat_bp,         url_prefix="/chat")
    app.register_blueprint(profile_bp,      url_prefix="/profile")
    app.register_blueprint(support_bp,      url_prefix="/support")

    return app


__all__ = ["create_app", "db", "jwt", "migrate"]
