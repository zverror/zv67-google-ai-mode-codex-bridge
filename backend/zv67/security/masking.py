"""Redaction helpers for logs and diagnostics."""

from __future__ import annotations

from typing import Any

SENSITIVE_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
)


def mask_secret(value: str | None) -> str:
    if not value:
        return "***"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-2:]}"


def _is_sensitive(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in SENSITIVE_PARTS)


def redact(value: Any) -> Any:
    """Recursively mask mapping values whose keys look sensitive."""

    if isinstance(value, dict):
        return {
            key: mask_secret(item) if _is_sensitive(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value

