"""Lightweight helpers for language handling and translations."""
from __future__ import annotations

from typing import Optional

SUPPORTED_LANGUAGES = {"en", "de", "es", "fr", "it"}
DEFAULT_LANGUAGE = "en"


def normalize_language(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_LANGUAGE
    normalized = value.strip().lower()
    if normalized in SUPPORTED_LANGUAGES:
        return normalized
    return DEFAULT_LANGUAGE


def resolve_user_language(user) -> str:
    """Return the preferred language for a user object."""
    if not user:
        return DEFAULT_LANGUAGE
    prefs = getattr(user, "preferences", None)
    if prefs and getattr(prefs, "language", None):
        return normalize_language(prefs.language)
    return DEFAULT_LANGUAGE


__all__ = ["normalize_language", "resolve_user_language", "SUPPORTED_LANGUAGES", "DEFAULT_LANGUAGE"]
