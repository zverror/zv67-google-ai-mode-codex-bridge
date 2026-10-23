"""Authenticated encryption for credentials and conversation content."""

from __future__ import annotations

import base64
import os
import platform
import subprocess
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken

KEYCHAIN_SERVICE = "zv67-master-key"


class SecretDecryptionError(ValueError):
    """Ciphertext is corrupt, was tampered with or belongs to another key."""


class MasterKeyStore(Protocol):
    def get_or_create(self) -> bytes:
        """Return a 32-byte url-safe base64 Fernet key."""


class FileMasterKeyStore:
    """Development fallback. The file is created with mode 0600."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def get_or_create(self) -> bytes:
        if self.path.exists():
            return self.path.read_bytes().strip()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, key)
        finally:
            os.close(fd)
        return key


class KeychainMasterKeyStore:
    """Stores the master key in the macOS login keychain."""

    def __init__(self, service: str = KEYCHAIN_SERVICE) -> None:
        self.service = service

    def get_or_create(self) -> bytes:
        existing = self._read()
        if existing:
            return existing
        key = Fernet.generate_key()
        # The security CLI accepts the secret as an argument; the exposure window
        # is limited to this one-time provisioning call.
        result = subprocess.run(
            [
                "/usr/bin/security",
                "add-generic-password",
                "-U",
                "-s",
                self.service,
                "-w",
                key.decode("ascii"),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            raise RuntimeError("failed to store the ZV67 master key in Keychain")
        return key

    def _read(self) -> bytes | None:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                self.service,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return None
        value = result.stdout.strip().encode("ascii")
        return value or None


def resolve_master_key_store(data_dir: Path, mode: str = "auto") -> MasterKeyStore:
    if mode == "file":
        return FileMasterKeyStore(data_dir / "master.key")
    if mode == "keychain":
        return KeychainMasterKeyStore()
    if platform.system() == "Darwin" and Path("/usr/bin/security").exists():
        return KeychainMasterKeyStore()
    return FileMasterKeyStore(data_dir / "master.key")


class SecretBox:
    """Encrypts UTF-8 strings with Fernet and a versioned prefix."""

    PREFIX = "zv67:v1:"

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        return self.PREFIX + token

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext.startswith(self.PREFIX):
            raise SecretDecryptionError("unsupported ciphertext version")
        try:
            return self._fernet.decrypt(
                ciphertext[len(self.PREFIX) :].encode("ascii")
            ).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise SecretDecryptionError("ciphertext could not be decrypted") from exc

    @staticmethod
    def fingerprint(plaintext: str) -> str:
        import hashlib

        return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def generate_key() -> bytes:
        return base64.urlsafe_b64encode(os.urandom(32))

