"""Local API key issuance and verification."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from zv67.persistence.models import ApiKey

API_KEY_PREFIX = "zv67_"


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_api_key(session: Session, name: str) -> tuple[str, ApiKey]:
    token = generate_api_key()
    record = ApiKey(
        id=f"key_{uuid.uuid4().hex}",
        name=name,
        key_hash=hash_api_key(token),
        prefix=token[:12],
    )
    session.add(record)
    session.flush()
    return token, record


def authenticate_api_key(session: Session, token: str) -> ApiKey | None:
    if not token.startswith(API_KEY_PREFIX):
        return None
    digest = hash_api_key(token)
    record = session.scalar(select(ApiKey).where(ApiKey.key_hash == digest))
    if record is None or record.revoked_at is not None:
        return None
    if not hmac.compare_digest(record.key_hash, digest):
        return None
    record.last_used_at = datetime.now(timezone.utc)
    return record


def revoke_api_key(session: Session, key_id: str) -> bool:
    record = session.get(ApiKey, key_id)
    if record is None or record.revoked_at is not None:
        return False
    record.revoked_at = datetime.now(timezone.utc)
    return True

