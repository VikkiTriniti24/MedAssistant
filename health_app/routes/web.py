# health_app/routes/web.py
from http import HTTPStatus
from datetime import datetime, timezone
import time

from flask import Blueprint, render_template, jsonify, current_app

# Blueprint for all web pages (registered without prefix)
web_bp = Blueprint("web", __name__)

# Track process start time for /healthz uptime
_START_TS = time.time()


@web_bp.app_context_processor
def inject_globals():
    """
    Make version/env available in ALL templates (base.html footer, etc.)
    so you don't have to pass them on every render_template call.
    """
    return {
        "app_version": current_app.config.get("VERSION", "dev"),
        "app_env": current_app.config.get("ENV", "development"),
    }


@web_bp.get("/")
def index():
    """
    Render the main dashboard page.
    UI guards handle 'Requires login' based on JWT in localStorage (client-side).
    """
    return render_template(
        "dashboard.html",
        now_utc=datetime.now(timezone.utc),
    )


@web_bp.get("/login")
def login_page():
    """Render the login page (client-side fetch posts to /auth/login)."""
    return render_template("login.html")


@web_bp.get("/register")
def register_page():
    """Render the registration page (client-side fetch posts to /auth/register)."""
    return render_template("register.html")


@web_bp.get("/healthz")
def healthz():
    """
    Lightweight liveness/readiness endpoint for uptime checks and load balancers.
    Returns JSON and disables caching.
    """
    payload = {
        "ok": True,
        "status": "ok",
        "service": current_app.name,  # usually 'health_app'
        "version": current_app.config.get("VERSION", "dev"),
        "environment": current_app.config.get("ENV", "development"),
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - _START_TS, 3),
    }
    resp = jsonify(payload)
    resp.status_code = HTTPStatus.OK
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@web_bp.get("/favicon.ico")
def favicon():
    """
    Avoid 404 noise if no favicon is provided.
    Later you can serve a real icon from /static via send_from_directory.
    """
    return ("", HTTPStatus.NO_CONTENT)
