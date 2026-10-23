"""Typed runtime configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _default_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "ZV67"


class Settings(BaseModel):
    """Runtime settings with localhost-safe defaults."""

    model_config = ConfigDict(frozen=True)

    host: str = "127.0.0.1"
    port: int = Field(default=18080, ge=1, le=65535)
    api_key: str | None = None
    request_timeout_seconds: float = Field(default=120.0, gt=0, le=3600)
    max_messages: int = Field(default=200, ge=1, le=10_000)
    max_message_chars: int = Field(default=200_000, ge=1, le=10_000_000)
    log_level: str = "INFO"
    data_dir: Path = Field(default_factory=_default_data_dir)
    database_path: Path | None = None
    master_key_store: Literal["auto", "keychain", "file"] = "auto"
    auto_migrate: bool = True
    routing_strategy: Literal[
        "round_robin", "weighted_round_robin", "least_busy", "manual"
    ] = "round_robin"
    session_ttl_hours: int = Field(default=168, ge=1, le=24 * 365)
    stream_chunk_chars: int = Field(default=32, ge=1, le=4096)

    @field_validator("host")
    @classmethod
    def _host_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("host must not be empty")
        return value.strip()

    @field_validator("api_key")
    @classmethod
    def _empty_api_key_means_disabled(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("data_dir", "database_path", mode="before")
    @classmethod
    def _expand_paths(cls, value: object) -> object:
        if isinstance(value, str):
            return Path(value).expanduser()
        return value

    @property
    def resolved_database_path(self) -> Path:
        if self.database_path is not None:
            return self.database_path
        return self.data_dir / "zv67.sqlite3"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        values: dict[str, object] = {}
        for field_name in cls.model_fields:
            env_name = "ZV67_" + field_name.upper()
            raw = source.get(env_name)
            if raw is not None:
                values[field_name] = raw
        return cls.model_validate(values)

