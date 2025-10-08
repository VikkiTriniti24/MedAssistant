"""Utilities for exporting audit logs in various formats."""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

from flask import current_app

from ..models import AuditLog


@dataclass(frozen=True)
class AuditExportFilters:
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    user_id: Optional[int] = None


def _apply_filters(query, filters: AuditExportFilters):
    if filters.start:
        query = query.filter(AuditLog.created_at >= filters.start)
    if filters.end:
        query = query.filter(AuditLog.created_at <= filters.end)
    if filters.user_id is not None:
        query = query.filter(AuditLog.user_id == filters.user_id)
    return query


def fetch_audit_rows(filters: Optional[AuditExportFilters] = None) -> List[AuditLog]:
    """Return audit rows ordered by creation time applying optional filters."""
    filters = filters or AuditExportFilters()
    query = AuditLog.query.order_by(AuditLog.created_at.asc())
    query = _apply_filters(query, filters)
    return list(query.all())


def _fingerprint(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:12]


def _pseudonymize(row: AuditLog) -> dict:
    user_label = None
    if row.user_id is not None:
        user_label = f"user-{_fingerprint(str(row.user_id))}"

    remote_addr = row.remote_addr or ""
    masked_addr = None
    if remote_addr:
        masked_addr = f"ip-{_fingerprint(remote_addr)}"

    user_agent = row.user_agent or None
    if user_agent:
        user_agent = f"ua-{_fingerprint(user_agent)}"

    return {
        "id": row.id,
        "user": user_label,
        "method": row.method,
        "path": row.path,
        "status_code": row.status_code,
        "duration_ms": row.duration_ms,
        "created_at": row.created_at.isoformat(),
        "remote_addr": masked_addr,
        "user_agent": user_agent,
    }


def _serialize_plain(row: AuditLog) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "method": row.method,
        "path": row.path,
        "status_code": row.status_code,
        "duration_ms": row.duration_ms,
        "created_at": row.created_at.isoformat(),
        "remote_addr": row.remote_addr,
        "user_agent": row.user_agent,
    }


def serialize_rows(rows: Sequence[AuditLog], *, pseudonymize: bool = False) -> List[dict]:
    serializer = _pseudonymize if pseudonymize else _serialize_plain
    return [serializer(row) for row in rows]


def serialize_csv(rows: Sequence[AuditLog], *, pseudonymize: bool = False) -> str:
    """Return rows encoded as CSV text."""
    data = serialize_rows(rows, pseudonymize=pseudonymize)
    if not data:
        return ""

    buffer = io.StringIO()
    headers = list(data[0].keys())
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(data)
    return buffer.getvalue()


def log_export(filters: AuditExportFilters, count: int, *, via: str) -> None:
    """Emit a debug log entry describing the export."""
    current_app.logger.info(
        "audit export | via=%s count=%s start=%s end=%s user_id=%s",
        via,
        count,
        filters.start.isoformat() if filters.start else None,
        filters.end.isoformat() if filters.end else None,
        filters.user_id,
    )


__all__ = [
    "AuditExportFilters",
    "fetch_audit_rows",
    "serialize_rows",
    "serialize_csv",
    "log_export",
]
