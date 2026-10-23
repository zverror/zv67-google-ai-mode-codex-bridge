"""Encrypted session history with account affinity and tool-call idempotency."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from zv67.persistence.db import Database
from zv67.persistence.models import ChatSession, SessionTurn, ToolCall
from zv67.security.crypto import SecretBox

DEFAULT_TTL = timedelta(days=7)


class SessionAccountConflict(RuntimeError):
    """A session cannot silently move to another account."""


class SessionExpired(RuntimeError):
    """The requested session is past its TTL."""


class SessionView(BaseModel):
    id: str
    account_id: str | None
    external_thread_id: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    turn_count: int = 0


class TurnView(BaseModel):
    role: str
    content: str
    created_at: datetime


class ToolCallView(BaseModel):
    call_id: str
    session_id: str
    tool_name: str
    status: str
    result: str | None
    created: bool = True


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class SessionManager:
    def __init__(
        self,
        database: Database,
        box: SecretBox,
        *,
        default_ttl: timedelta = DEFAULT_TTL,
    ) -> None:
        self._database = database
        self._box = box
        self._ttl = default_ttl

    def create(
        self,
        *,
        account_id: str | None = None,
        external_thread_id: str | None = None,
        session_id: str | None = None,
    ) -> SessionView:
        now = datetime.now(timezone.utc)
        with self._database.session() as session:
            record = ChatSession(
                id=session_id or f"sess_{uuid.uuid4().hex}",
                account_id=account_id,
                external_thread_id=external_thread_id,
                created_at=now,
                updated_at=now,
                expires_at=now + self._ttl,
            )
            session.add(record)
            session.flush()
            return self._view(record, 0)

    def ensure(
        self,
        session_id: str | None,
        *,
        account_id: str | None = None,
        external_thread_id: str | None = None,
    ) -> SessionView:
        if session_id is None:
            return self.create(
                account_id=account_id, external_thread_id=external_thread_id
            )
        existing = self.get(session_id)
        if existing is None:
            return self.create(
                account_id=account_id,
                external_thread_id=external_thread_id,
                session_id=session_id,
            )
        if existing.expires_at and _aware(existing.expires_at) <= datetime.now(
            timezone.utc
        ):
            raise SessionExpired(f"session '{session_id}' has expired")
        if account_id is not None and existing.account_id != account_id:
            self.bind_account(session_id, account_id)
        return existing

    def get(self, session_id: str) -> SessionView | None:
        with self._database.session() as session:
            record = session.get(ChatSession, session_id)
            if record is None:
                return None
            turns = session.scalar(
                select(func.count())
                .select_from(SessionTurn)
                .where(SessionTurn.session_id == session_id)
            )
            return self._view(record, int(turns or 0))

    def bind_account(self, session_id: str, account_id: str) -> None:
        with self._database.session() as session:
            record = session.get(ChatSession, session_id)
            if record is None:
                raise KeyError(f"session '{session_id}' does not exist")
            if record.account_id is None:
                record.account_id = account_id
            elif record.account_id != account_id:
                raise SessionAccountConflict(
                    "session is pinned to a different account"
                )

    def append_turn(self, session_id: str, role: str, content: str) -> None:
        with self._database.session() as session:
            record = session.get(ChatSession, session_id)
            if record is None:
                raise KeyError(f"session '{session_id}' does not exist")
            session.add(
                SessionTurn(
                    session_id=session_id,
                    role=role,
                    content_ciphertext=self._box.encrypt(content),
                )
            )
            record.updated_at = datetime.now(timezone.utc)

    def history(self, session_id: str, *, limit: int = 100) -> list[TurnView]:
        with self._database.session() as session:
            rows = session.scalars(
                select(SessionTurn)
                .where(SessionTurn.session_id == session_id)
                .order_by(SessionTurn.id.desc())
                .limit(limit)
            ).all()
            return [
                TurnView(
                    role=row.role,
                    content=self._box.decrypt(row.content_ciphertext),
                    created_at=row.created_at,
                )
                for row in reversed(rows)
            ]

    def delete(self, session_id: str) -> bool:
        with self._database.session() as session:
            record = session.get(ChatSession, session_id)
            if record is None:
                return False
            session.delete(record)
            return True

    def list_sessions(self, *, limit: int = 100) -> list[SessionView]:
        with self._database.session() as session:
            records = session.scalars(
                select(ChatSession)
                .order_by(ChatSession.updated_at.desc())
                .limit(min(max(limit, 1), 500))
            ).all()
            views: list[SessionView] = []
            for record in records:
                turns = session.scalar(
                    select(func.count())
                    .select_from(SessionTurn)
                    .where(SessionTurn.session_id == record.id)
                )
                views.append(self._view(record, int(turns or 0)))
            return views

    def purge_expired(self) -> int:
        now = datetime.now(timezone.utc)
        with self._database.session() as session:
            expired = session.scalars(
                select(ChatSession).where(ChatSession.expires_at <= now)
            ).all()
            for record in expired:
                session.delete(record)
            return len(expired)

    def register_tool_call(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: str,
    ) -> ToolCallView:
        with self._database.session() as session:
            existing = session.scalar(
                select(ToolCall).where(ToolCall.call_id == call_id)
            )
            if existing is not None:
                return self._tool_view(existing, created=False)
            if session.get(ChatSession, session_id) is None:
                raise KeyError(f"session '{session_id}' does not exist")
            row = ToolCall(
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments_ciphertext=self._box.encrypt(arguments),
            )
            session.add(row)
            session.flush()
            return self._tool_view(row, created=True)

    def complete_tool_call(self, call_id: str, result: str) -> bool:
        with self._database.session() as session:
            row = session.scalar(select(ToolCall).where(ToolCall.call_id == call_id))
            if row is None:
                raise KeyError(f"tool call '{call_id}' does not exist")
            if row.status == "COMPLETED":
                return False
            row.result_ciphertext = self._box.encrypt(result)
            row.status = "COMPLETED"
            row.completed_at = datetime.now(timezone.utc)
            return True

    def get_tool_call(self, call_id: str) -> ToolCallView | None:
        with self._database.session() as session:
            row = session.scalar(select(ToolCall).where(ToolCall.call_id == call_id))
            return self._tool_view(row) if row else None

    def tool_call_arguments(self, call_id: str) -> str | None:
        with self._database.session() as session:
            row = session.scalar(select(ToolCall).where(ToolCall.call_id == call_id))
            if row is None:
                return None
            return self._box.decrypt(row.arguments_ciphertext)

    @staticmethod
    def _view(record: ChatSession, turns: int) -> SessionView:
        return SessionView(
            id=record.id,
            account_id=record.account_id,
            external_thread_id=record.external_thread_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            expires_at=record.expires_at,
            turn_count=turns,
        )

    def _tool_view(self, row: ToolCall, *, created: bool = True) -> ToolCallView:
        return ToolCallView(
            call_id=row.call_id,
            session_id=row.session_id,
            tool_name=row.tool_name,
            status=row.status,
            result=(
                self._box.decrypt(row.result_ciphertext)
                if row.result_ciphertext
                else None
            ),
            created=created,
        )

