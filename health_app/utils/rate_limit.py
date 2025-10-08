"""Rate limiting helpers."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from threading import Lock
from time import monotonic
from typing import Deque, Dict, Optional, Tuple

from flask import current_app, jsonify, request

from ..metrics import track_rate_limit_hit


class SimpleRateLimiter:
    """In-memory rate limiter used as a fallback when persistence is unavailable."""

    def __init__(self) -> None:
        self._events: Dict[str, Deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, float]:
        now = monotonic()
        retry_after = 0.0

        with self._lock:
            q = self._events.setdefault(key, deque())
            cutoff = now - window_seconds
            while q and q[0] <= cutoff:
                q.popleft()

            if len(q) >= limit:
                retry_after = max(0.0, (q[0] + window_seconds) - now)
                return False, retry_after

            q.append(now)

        return True, retry_after


class PersistentRateLimiter:
    """Database-backed limiter so thresholds survive process restarts."""

    def __init__(self, db):
        self._db = db

    def check(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, float]:
        from health_app.models import RateLimitHit

        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=window_seconds)
        retry_after = 0.0

        session = self._db.session
        try:
            session.query(RateLimitHit).filter(
                RateLimitHit.key == key,
                RateLimitHit.created_at < cutoff,
            ).delete()

            count = session.query(RateLimitHit).filter(RateLimitHit.key == key).count()
            if count >= limit:
                oldest = (
                    session.query(RateLimitHit)
                    .filter(RateLimitHit.key == key)
                    .order_by(RateLimitHit.created_at.asc())
                    .first()
                )
                if oldest:
                    retry_after = max(
                        0.0,
                        window_seconds - (now - oldest.created_at).total_seconds(),
                    )
                session.commit()
                return False, retry_after

            session.add(RateLimitHit(key=key, created_at=now))
            session.commit()
        except Exception:
            session.rollback()
            raise

        return True, retry_after


def _resolve_limits(action: str, role: str) -> Tuple[int, int]:
    cfg = current_app.config
    default_limit = int(cfg.get("RATE_LIMIT_DEFAULT_LIMIT", 60))
    default_window = int(cfg.get("RATE_LIMIT_DEFAULT_WINDOW", 60))

    key_base = action.upper().replace("-", "_")
    limit_key = f"RATE_LIMIT_{key_base}_LIMIT"
    window_key = f"RATE_LIMIT_{key_base}_WINDOW"

    limit = cfg.get(limit_key)
    window = cfg.get(window_key)

    if limit is None and "_" in key_base:
        prefix = key_base.split("_")[0]
        limit = cfg.get(f"RATE_LIMIT_{prefix}_LIMIT")
    if window is None and "_" in key_base:
        prefix = key_base.split("_")[0]
        window = cfg.get(f"RATE_LIMIT_{prefix}_WINDOW")

    if limit is None:
        limit = default_limit
    if window is None:
        window = default_window

    limit = max(1, int(limit))
    window = max(1, int(window))

    multiplier = float(cfg.get(f"RATE_LIMIT_ROLE_MULTIPLIER_{role.upper()}", 1.0))
    if multiplier <= 0:
        multiplier = 1.0

    adjusted_limit = max(1, int(round(limit * multiplier)))
    return adjusted_limit, window


def enforce_rate_limit(
    action: str,
    *,
    identifier: Optional[str] = None,
    role: str = "user",
):
    if current_app.config.get("RATE_LIMITING_DISABLED"):
        return None

    limiter = current_app.extensions.get("rate_limiter")
    if not limiter:
        return None

    role = role or "user"
    limit, window = _resolve_limits(action, role)
    key_parts = [action, role]
    if identifier:
        key_parts.append(str(identifier))
    else:
        key_parts.append(request.remote_addr or "unknown")
    key = ":".join(key_parts)

    allowed, retry_after = limiter.check(key, limit, window)
    if allowed:
        return None

    retry_after = max(1, int(round(retry_after or window)))
    try:
        track_rate_limit_hit(action, role)
    except Exception:
        current_app.logger.debug("metrics: failed to track rate limit hit", exc_info=True)
    resp = jsonify({
        "msg": "too many requests",
        "retry_after": retry_after,
    })
    resp.status_code = 429
    resp.headers["Retry-After"] = str(retry_after)
    return resp


__all__ = ["SimpleRateLimiter", "PersistentRateLimiter", "enforce_rate_limit"]
