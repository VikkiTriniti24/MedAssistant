"""Simple metrics registry for runtime counters."""
from __future__ import annotations

from collections import Counter
from threading import Lock
from typing import Dict, Iterable, Tuple


class _MetricsRegistry:
    """Thread-safe counter storage producing Prometheus-style text."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: Counter[Tuple[str, Tuple[Tuple[str, str], ...]]] = Counter()

    def increment(self, name: str, labels: Dict[str, str]) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += 1

    def snapshot(self) -> Counter:
        with self._lock:
            return self._counters.copy()

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


_registry = _MetricsRegistry()


def track_ai_fallback(language: str, reason: str) -> None:
    _registry.increment(
        "medassistant_ai_fallback_total",
        {"language": language, "reason": reason},
    )


def track_rate_limit_hit(action: str, role: str) -> None:
    _registry.increment(
        "medassistant_rate_limit_hit_total",
        {"action": action, "role": role},
    )


def render_metrics() -> str:
    counters = _registry.snapshot()
    if not counters:
        return "# no metrics yet\n"

    lines = []
    for (name, label_items), value in sorted(counters.items()):
        if label_items:
            label = ",".join(f"{k}=\"{v}\"" for k, v in label_items)
            lines.append(f"{name}{{{label}}} {value}")
        else:
            lines.append(f"{name} {value}")
    lines.append("")
    return "\n".join(lines)


def reset_metrics() -> None:
    _registry.reset()


__all__ = [
    "track_ai_fallback",
    "track_rate_limit_hit",
    "render_metrics",
    "reset_metrics",
]
