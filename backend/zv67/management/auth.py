"""Password authentication and signed admin session cookies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from sqlalchemy import select

from zv67.persistence.db import Database
from zv67.persistence.models import Setting

COOKIE_NAME = "zv67_admin"
PASSWORD_KEY = "admin_password_hash"
MIN_PASSWORD_LENGTH = 12


class AdminAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdminClaims:
    jti: str
    expires_at: int


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt$16384$8$1${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_unb64(digest)),
        )
        return hmac.compare_digest(candidate, _unb64(digest))
    except (ValueError, TypeError):
        return False


class AdminAuth:
    """Signed stateless sessions with a CSRF token bound to each session."""

    def __init__(
        self,
        database: Database,
        secret: bytes,
        *,
        ttl_seconds: int = 12 * 3600,
    ) -> None:
        self._database = database
        self._secret = secret
        self._ttl = ttl_seconds
        self._failures: defaultdict[str, deque[float]] = defaultdict(deque)

    def configured(self) -> bool:
        return self._read_password_hash() is not None

    def setup(self, password: str) -> None:
        self._validate_password(password)
        if self.configured():
            raise AdminAuthError("administrator password is already configured")
        self._write_password_hash(hash_password(password))

    def change_password(self, current: str, new: str) -> None:
        stored = self._read_password_hash()
        if stored is None or not verify_password(current, stored):
            raise AdminAuthError("current password is incorrect")
        self._validate_password(new)
        self._write_password_hash(hash_password(new))

    def login(self, client_key: str, password: str) -> tuple[str, str, int] | None:
        now = time.time()
        attempts = self._failures[client_key]
        while attempts and now - attempts[0] > 300:
            attempts.popleft()
        if len(attempts) >= 5:
            raise AdminAuthError("too many failed attempts, try again later")
        stored = self._read_password_hash()
        if stored is None or not verify_password(password, stored):
            attempts.append(now)
            return None
        attempts.clear()
        expires_at = int(now) + self._ttl
        jti = _b64(os.urandom(18))
        body = _b64(
            json.dumps({"jti": jti, "exp": expires_at}, separators=(",", ":")).encode()
        )
        signature = _b64(
            hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).digest()
        )
        return f"{body}.{signature}", self.csrf_for(jti), expires_at

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AdminAuthError(
                f"password must be at least {MIN_PASSWORD_LENGTH} characters"
            )

    def verify_session(self, token: str | None) -> AdminClaims | None:
        if not token or "." not in token:
            return None
        body, signature = token.split(".", 1)
        expected = _b64(
            hmac.new(self._secret, body.encode("ascii", "ignore"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return None
        try:
            payload = json.loads(_unb64(body))
            expires_at = int(payload["exp"])
            jti = str(payload["jti"])
        except (ValueError, KeyError, TypeError):
            return None
        if expires_at <= int(time.time()):
            return None
        return AdminClaims(jti=jti, expires_at=expires_at)

    def csrf_for(self, jti: str) -> str:
        return _b64(
            hmac.new(
                self._secret, f"csrf:{jti}".encode("ascii"), hashlib.sha256
            ).digest()[:18]
        )

    def check_csrf(self, claims: AdminClaims, provided: str | None) -> bool:
        if not provided:
            return False
        return hmac.compare_digest(provided, self.csrf_for(claims.jti))

    def _read_password_hash(self) -> str | None:
        with self._database.session() as session:
            return session.scalar(
                select(Setting.value).where(Setting.key == PASSWORD_KEY)
            )

    def _write_password_hash(self, value: str) -> None:
        with self._database.session() as session:
            record = session.get(Setting, PASSWORD_KEY)
            if record is None:
                session.add(Setting(key=PASSWORD_KEY, value=value))
            else:
                record.value = value

