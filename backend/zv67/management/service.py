"""Runtime settings and administrative audit records."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select

from zv67.persistence.db import Database
from zv67.persistence.models import AdminAudit, Setting


class AuditEntry(BaseModel):
    id: int
    action: str
    target: str | None
    detail: str | None
    created_at: str


class SettingsStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, key: str, default: str | None = None) -> str | None:
        with self._database.session() as session:
            value = session.scalar(select(Setting.value).where(Setting.key == key))
        return default if value is None else value

    def set(self, key: str, value: str) -> None:
        with self._database.session() as session:
            record = session.get(Setting, key)
            if record is None:
                session.add(Setting(key=key, value=value))
            else:
                record.value = value

    def get_json(self, key: str, default: Any = None) -> Any:
        value = self.get(key)
        return default if value is None else json.loads(value)

    def set_json(self, key: str, value: Any) -> None:
        self.set(key, json.dumps(value, ensure_ascii=False))


class AuditLog:
    def __init__(self, database: Database) -> None:
        self._database = database

    def record(
        self,
        action: str,
        *,
        target: str | None = None,
        detail: str | None = None,
    ) -> None:
        with self._database.session() as session:
            session.add(
                AdminAudit(
                    action=action,
                    target=target,
                    detail=(detail or "")[:1000] or None,
                )
            )

    def recent(self, limit: int = 100) -> list[AuditEntry]:
        with self._database.session() as session:
            rows = session.scalars(
                select(AdminAudit)
                .order_by(AdminAudit.created_at.desc())
                .limit(min(max(limit, 1), 500))
            ).all()
            return [
                AuditEntry(
                    id=row.id,
                    action=row.action,
                    target=row.target,
                    detail=row.detail,
                    created_at=row.created_at.isoformat(),
                )
                for row in rows
            ]

