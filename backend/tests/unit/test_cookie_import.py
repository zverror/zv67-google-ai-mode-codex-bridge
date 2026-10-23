"""Credential format parsing tests."""

from __future__ import annotations

import pytest

from zv67.security.cookie_import import (
    CredentialParseError,
    normalize_credentials,
    parse_credentials_text,
)


def test_cookie_editor_array_is_wrapped():
    parsed = parse_credentials_text(
        '[{"domain": ".google.com", "name": "__Secure-1PSID", "value": "abc"}]'
    )

    assert parsed["cookies"][0]["name"] == "__Secure-1PSID"
    assert parsed["cookies"][0]["domain"] == ".google.com"


def test_netscape_file_with_http_only_prefix():
    parsed = parse_credentials_text(
        "# Netscape HTTP Cookie File\n"
        "#HttpOnly_.google.com\tTRUE\t/\tTRUE\t1824327060\t__Secure-1PSID\tvalue-1\n"
        ".google.com\tTRUE\t/\tTRUE\t0\tNID\tvalue-2\n"
    )

    cookies = parsed["cookies"]
    assert [cookie["name"] for cookie in cookies] == ["__Secure-1PSID", "NID"]
    assert cookies[0]["httpOnly"] is True
    assert cookies[0]["secure"] is True
    assert cookies[1]["httpOnly"] is False
    assert cookies[1]["expirationDate"] == 0.0


def test_plain_cookie_header_is_parsed():
    parsed = parse_credentials_text("SID=one; HSID=two")

    assert [(c["name"], c["value"]) for c in parsed["cookies"]] == [
        ("SID", "one"),
        ("HSID", "two"),
    ]


def test_invalid_json_is_rejected_with_location():
    with pytest.raises(CredentialParseError, match="invalid JSON"):
        parse_credentials_text('[{"name": "SID",]')


def test_array_without_names_is_rejected():
    with pytest.raises(CredentialParseError, match="no name"):
        normalize_credentials([{"value": "x"}])


def test_empty_payload_is_rejected():
    with pytest.raises(CredentialParseError, match="empty"):
        parse_credentials_text("   ")
