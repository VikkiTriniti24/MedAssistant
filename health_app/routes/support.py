"""Support-facing endpoints (audit export, etc.)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required

from ..services.audit_exporter import (
    AuditExportFilters,
    fetch_audit_rows,
    log_export,
    serialize_csv,
    serialize_rows,
)

support_bp = Blueprint("support", __name__)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
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
        raise ValueError(f"Invalid timestamp '{value}'") from exc
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _as_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


@support_bp.get("/audit-export")
@jwt_required()
def audit_export() -> Response:
    claims = get_jwt() or {}
    if claims.get("role") != "admin":
        return jsonify({"error": "forbidden"}), 403

    try:
        start = _parse_iso(request.args.get("start"))
        end = _parse_iso(request.args.get("end"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    user_id = request.args.get("user_id")
    try:
        user_id_int = int(user_id) if user_id is not None else None
    except ValueError:
        return jsonify({"error": "user_id must be an integer"}), 400

    fmt = (request.args.get("format") or "json").strip().lower()
    if fmt not in {"json", "csv"}:
        return jsonify({"error": "format must be one of: json, csv"}), 400

    pseudonymize = _as_bool(request.args.get("pseudonymize"))

    filters = AuditExportFilters(start=start, end=end, user_id=user_id_int)
    rows = fetch_audit_rows(filters)
    log_export(filters, len(rows), via="http")

    if fmt == "csv":
        csv_body = serialize_csv(rows, pseudonymize=pseudonymize)
        resp = Response(csv_body, mimetype="text/csv")
        resp.headers["Content-Disposition"] = "attachment; filename=audit-export.csv"
        return resp

    items = serialize_rows(rows, pseudonymize=pseudonymize)
    payload = {"count": len(items), "items": items}
    return jsonify(payload)


__all__ = ["support_bp"]
