"""Tests for encryption, masking and API keys."""

from __future__ import annotations

import stat

import pytest
from cryptography.fernet import Fernet

from zv67.persistence.models import Account
from zv67.security.api_keys import (
    authenticate_api_key,
    create_api_key,
    revoke_api_key,
)
from zv67.security.credentials import CredentialService
from zv67.security.crypto import (
    FileMasterKeyStore,
    SecretBox,
    SecretDecryptionError,
)
from zv67.security.masking import mask_secret, redact


def test_secret_box_roundtrip_and_tamper_detection():
    box = SecretBox(Fernet.generate_key())
    ciphertext = box.encrypt('{"cookie":"secret-value"}')

    assert ciphertext.startswith(SecretBox.PREFIX)
    assert "secret-value" not in ciphertext
    assert box.decrypt(ciphertext) == '{"cookie":"secret-value"}'

    tampered = ciphertext[:-4] + "AAAA"
    with pytest.raises(SecretDecryptionError):
        box.decrypt(tampered)


def test_file_master_key_is_private_and_stable(tmp_path):
    path = tmp_path / "nested" / "master.key"
    store = FileMasterKeyStore(path)

    first = store.get_or_create()
    second = FileMasterKeyStore(path).get_or_create()

    assert first == second
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_credentials_are_encrypted_at_rest(tmp_path, client, app):
    database = app.state.database
    assert database is not None
    with database.session() as session:
        session.add(Account(id="acc_1", display_name="Test"))
        session.flush()
        service = app.state.credentials
        metadata = service.store(
            session,
            "acc_1",
            {"cookies": [{"name": "__Secure-1PSID", "value": "top-secret"}]},
        )
        assert "top-secret" not in metadata.ciphertext
        assert metadata.fingerprint
    with database.session() as session:
        loaded = app.state.credentials.load(session, "acc_1")
        assert loaded["cookies"][0]["value"] == "top-secret"


def test_api_key_lifecycle(client, app):
    database = app.state.database
    with database.session() as session:
        token, record = create_api_key(session, "test")
    with database.session() as session:
        assert authenticate_api_key(session, token).id == record.id
        assert authenticate_api_key(session, token + "x") is None
        assert authenticate_api_key(session, "wrong") is None
        assert revoke_api_key(session, record.id) is True
    with database.session() as session:
        assert authenticate_api_key(session, token) is None


def test_masking_hides_secrets_and_redacts_nested_values():
    assert mask_secret("super-secret-value") == "supe...ue"
    assert mask_secret("short") == "***"
    assert mask_secret(None) == "***"

    payload = {
        "Authorization": "Bearer abcdefghijkl",
        "nested": {"api_key": "1234567890123456", "safe": "visible"},
        "items": [{"cookie": "abcdefghijklmnop"}],
    }
    redacted = redact(payload)

    assert redacted["Authorization"] == "Bear...kl"
    assert redacted["nested"]["api_key"] == "1234...56"
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["items"][0]["cookie"] == "abcd...op"

