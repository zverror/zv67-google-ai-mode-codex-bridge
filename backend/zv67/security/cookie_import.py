"""Parse Cookie-Editor JSON, Netscape cookie files and Cookie headers."""

from __future__ import annotations

import json
from typing import Any

MAX_CREDENTIAL_BYTES = 5_000_000
MAX_COOKIES = 3000


class CredentialParseError(ValueError):
    pass


def _validate_cookies(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise CredentialParseError("'cookies' must be a list")
    if len(items) > MAX_COOKIES:
        raise CredentialParseError(f"too many cookies (limit {MAX_COOKIES})")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CredentialParseError(f"cookie #{index + 1} must be an object")
        name = item.get("name")
        value = item.get("value")
        if not isinstance(name, str) or not name:
            raise CredentialParseError(f"cookie #{index + 1} has no name")
        if not isinstance(value, str):
            raise CredentialParseError(f"cookie '{name}' has no string value")
        result.append(item)
    if not result:
        raise CredentialParseError("cookie list is empty")
    return result


def normalize_credentials(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        return {"cookies": _validate_cookies(data)}
    if isinstance(data, dict):
        if "cookies" in data:
            return {**data, "cookies": _validate_cookies(data["cookies"])}
        return data
    raise CredentialParseError("credentials must be a JSON object or array")


def _parse_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CredentialParseError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    return normalize_credentials(data)


def _parse_netscape(text: str) -> list[dict[str, Any]]:
    cookies: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip("\r")
        if not line.strip():
            continue
        http_only = False
        if line.startswith("#HttpOnly_"):
            http_only = True
            line = line[len("#HttpOnly_") :]
        elif line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, include_subdomains, path, secure, expiry, name = parts[:6]
        value = "\t".join(parts[6:])
        if not domain or not name:
            continue
        expiration: float | None
        try:
            expiration = float(expiry) if expiry.strip() else None
        except ValueError:
            expiration = None
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path or "/",
                "secure": secure.strip().upper() == "TRUE",
                "httpOnly": http_only,
                "expirationDate": expiration,
                "hostOnly": include_subdomains.strip().upper() != "TRUE",
                "sameSite": "unspecified",
            }
        )
    return cookies


def _parse_cookie_header(text: str) -> list[dict[str, Any]]:
    if "=" not in text:
        return []
    cookies: list[dict[str, Any]] = []
    for chunk in text.split(";"):
        name, separator, value = chunk.strip().partition("=")
        if not separator or not name:
            continue
        cookies.append(
            {
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".google.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "hostOnly": False,
                "sameSite": "unspecified",
            }
        )
    return cookies


def parse_credentials_text(text: str) -> dict[str, Any]:
    """Accept Cookie-Editor JSON, Netscape or a plain Cookie header."""

    if len(text.encode("utf-8")) > MAX_CREDENTIAL_BYTES:
        raise CredentialParseError("credentials payload is too large")
    stripped = text.strip()
    if not stripped:
        raise CredentialParseError("credentials payload is empty")
    if stripped[0] in "[{":
        return _parse_json(stripped)

    cookies = _parse_netscape(stripped)
    if cookies:
        return {"cookies": _validate_cookies(cookies)}

    cookies = _parse_cookie_header(stripped)
    if cookies:
        return {"cookies": _validate_cookies(cookies)}

    raise CredentialParseError(
        "unrecognized format: use Cookie-Editor JSON, Netscape or name=value pairs"
    )

