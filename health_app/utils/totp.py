"""Minimal TOTP utilities (RFC 6238)."""
from __future__ import annotations

import base64
import hmac
import os
import struct
import time
from typing import Optional


_DIGITS_POWER = (0, 1, 10, 100, 1000, 10000, 100000, 1000000, 10000000, 100000000)


def generate_secret(length: int = 20) -> str:
    """Generate a base32 secret for TOTP provisioning."""
    return base64.b32encode(os.urandom(length)).decode("utf-8").strip("=")


def _totp_counter(timestamp: Optional[float] = None, step: int = 30) -> int:
    if timestamp is None:
        timestamp = time.time()
    return int(timestamp // step)


def _dynamic_truncate(hmac_digest: bytes) -> int:
    offset = hmac_digest[-1] & 0x0F
    binary = (
        ((hmac_digest[offset] & 0x7F) << 24)
        | ((hmac_digest[offset + 1] & 0xFF) << 16)
        | ((hmac_digest[offset + 2] & 0xFF) << 8)
        | (hmac_digest[offset + 3] & 0xFF)
    )
    return binary


def generate_totp(secret: str, timestamp: Optional[float] = None, step: int = 30, digits: int = 6) -> str:
    """Generate a TOTP code for the given secret."""
    secret = secret.strip().upper()
    # Pad secret for base32 decode
    missing_padding = len(secret) % 8
    if missing_padding:
        secret += "=" * (8 - missing_padding)

    key = base64.b32decode(secret)
    counter = _totp_counter(timestamp, step)
    counter_bytes = struct.pack(">Q", counter)

    hmac_digest = hmac.new(key, counter_bytes, "sha1").digest()
    code_int = _dynamic_truncate(hmac_digest) % _DIGITS_POWER[digits]
    return str(code_int).zfill(digits)


def verify_totp(secret: str, code: str, *, timestamp: Optional[float] = None, step: int = 30, digits: int = 6, window: int = 1) -> bool:
    """Verify that a code matches within +/- window steps."""
    code = (code or "").strip()
    if not code.isdigit() or len(code) != digits:
        return False

    ts = time.time() if timestamp is None else timestamp
    for offset in range(-window, window + 1):
        test_ts = ts + (offset * step)
        if generate_totp(secret, timestamp=test_ts, step=step, digits=digits) == code:
            return True
    return False


def build_otpauth_uri(secret: str, email: str, issuer: str = "MedAssistant") -> str:
    return f"otpauth://totp/{issuer}:{email}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
