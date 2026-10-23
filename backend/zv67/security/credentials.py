"""Encrypted credential payloads bound to an account."""

from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from zv67.persistence.models import Account, CredentialMetadata
from zv67.security.crypto import SecretBox


class MissingAccountError(LookupError):
    pass


class CredentialService:
    """Stores credential JSON only as authenticated ciphertext."""

    def __init__(self, box: SecretBox) -> None:
        self._box = box

    def store(
        self,
        session: Session,
        account_id: str,
        payload: Mapping[str, Any],
    ) -> CredentialMetadata:
        account = session.get(Account, account_id)
        if account is None:
            raise MissingAccountError(f"account '{account_id}' does not exist")
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        ciphertext = self._box.encrypt(serialized)
        fingerprint = SecretBox.fingerprint(serialized)
        secret_ref = f"account:{account_id}"
        record = session.scalar(
            select(CredentialMetadata).where(
                CredentialMetadata.account_id == account_id
            )
        )
        if record is None:
            record = CredentialMetadata(
                id=f"cred_{uuid.uuid4().hex}",
                account_id=account_id,
                secret_ref=secret_ref,
                scheme="fernet_v1",
                fingerprint=fingerprint,
                ciphertext=ciphertext,
            )
            session.add(record)
        else:
            record.ciphertext = ciphertext
        record.fingerprint = fingerprint
        record.secret_ref = secret_ref
        account.credential_ref = secret_ref
        session.flush()
        return record

    def load(self, session: Session, account_id: str) -> dict[str, Any] | None:
        record = session.scalar(
            select(CredentialMetadata).where(
                CredentialMetadata.account_id == account_id
            )
        )
        if record is None:
            return None
        raw = self._box.decrypt(record.ciphertext)
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ValueError("credential payload is not an object")
        return loaded

    def delete(self, session: Session, account_id: str) -> bool:
        record = session.scalar(
            select(CredentialMetadata).where(
                CredentialMetadata.account_id == account_id
            )
        )
        if record is None:
            return False
        session.delete(record)
        return True

