"""Account lifecycle and per-account statistics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from zv67.persistence.db import Database
from zv67.persistence.models import Account, ChatSession, RequestRecord
from zv67.security.credentials import CredentialService


class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    UNAUTHORIZED = "UNAUTHORIZED"
    DEGRADED = "DEGRADED"
    COOLDOWN = "COOLDOWN"
    UNKNOWN = "UNKNOWN"


class AccountView(BaseModel):
    id: str
    display_name: str
    subscription_status: str
    enabled: bool
    connection_status: str
    concurrency_limit: int
    routing_weight: int
    last_success_at: datetime | None
    last_error: str | None
    created_at: datetime
    has_credentials: bool


def _view(account: Account, session: Session) -> AccountView:
    has_credentials = bool(account.credential_ref)
    return AccountView(
        id=account.id,
        display_name=account.display_name,
        subscription_status=account.subscription_status,
        enabled=account.enabled,
        connection_status=account.connection_status,
        concurrency_limit=account.concurrency_limit,
        routing_weight=account.routing_weight,
        last_success_at=account.last_success_at,
        last_error=account.last_error,
        created_at=account.created_at,
        has_credentials=has_credentials,
    )


class AccountService:
    """Creates, updates and removes accounts with isolated credentials."""

    def __init__(
        self,
        database: Database,
        credentials: CredentialService | None = None,
    ) -> None:
        self._database = database
        self._credentials = credentials

    def add(
        self,
        display_name: str,
        *,
        subscription_status: str = "unknown",
        concurrency_limit: int = 1,
        routing_weight: int = 100,
        credentials: Mapping[str, Any] | None = None,
    ) -> AccountView:
        if not display_name.strip():
            raise ValueError("display_name must not be empty")
        if concurrency_limit < 1:
            raise ValueError("concurrency_limit must be at least 1")
        if routing_weight < 1:
            raise ValueError("routing_weight must be at least 1")
        with self._database.session() as session:
            account = Account(
                id=f"acc_{uuid.uuid4().hex[:12]}",
                display_name=display_name.strip(),
                subscription_status=subscription_status,
                concurrency_limit=concurrency_limit,
                routing_weight=routing_weight,
                connection_status=AccountStatus.UNKNOWN.value,
            )
            session.add(account)
            session.flush()
            if credentials:
                if self._credentials is None:
                    raise ValueError("credentials cannot be stored without a credential service")
                self._credentials.store(session, account.id, credentials)
            session.flush()
            return _view(account, session)

    def list(self) -> list[AccountView]:
        with self._database.session() as session:
            accounts = session.scalars(select(Account).order_by(Account.created_at)).all()
            return [_view(account, session) for account in accounts]

    def get(self, account_id: str) -> AccountView | None:
        with self._database.session() as session:
            account = session.get(Account, account_id)
            return _view(account, session) if account else None

    def set_enabled(self, account_id: str, enabled: bool) -> bool:
        with self._database.session() as session:
            account = session.get(Account, account_id)
            if account is None:
                return False
            account.enabled = enabled
            account.connection_status = (
                AccountStatus.UNKNOWN.value if enabled else AccountStatus.DISABLED.value
            )
            return True

    def set_status(self, account_id: str, status: AccountStatus) -> bool:
        with self._database.session() as session:
            account = session.get(Account, account_id)
            if account is None:
                return False
            account.connection_status = status.value
            return True

    def update(
        self,
        account_id: str,
        *,
        display_name: str | None = None,
        concurrency_limit: int | None = None,
        routing_weight: int | None = None,
    ) -> AccountView | None:
        if concurrency_limit is not None and concurrency_limit < 1:
            raise ValueError("concurrency_limit must be at least 1")
        if routing_weight is not None and routing_weight < 1:
            raise ValueError("routing_weight must be at least 1")
        with self._database.session() as session:
            account = session.get(Account, account_id)
            if account is None:
                return None
            if display_name is not None:
                if not display_name.strip():
                    raise ValueError("display_name must not be empty")
                account.display_name = display_name.strip()
            if concurrency_limit is not None:
                account.concurrency_limit = concurrency_limit
            if routing_weight is not None:
                account.routing_weight = routing_weight
            session.flush()
            return _view(account, session)

    def record_success(self, account_id: str) -> None:
        with self._database.session() as session:
            account = session.get(Account, account_id)
            if account is None:
                return
            account.connection_status = AccountStatus.ACTIVE.value
            account.last_success_at = datetime.now(timezone.utc)
            account.last_error = None

    def record_error(self, account_id: str, message: str, status: AccountStatus) -> None:
        with self._database.session() as session:
            account = session.get(Account, account_id)
            if account is None:
                return
            account.connection_status = status.value
            account.last_error = message[:500]

    def remove(self, account_id: str) -> bool:
        """Remove the account together with its credentials and sessions."""

        with self._database.session() as session:
            account = session.get(Account, account_id)
            if account is None:
                return False
            session.delete(account)
            return True

    def statistics(self, account_id: str) -> dict[str, int | float | None]:
        with self._database.session() as session:
            requests = session.scalars(
                select(RequestRecord).where(RequestRecord.account_id == account_id)
            ).all()
        total = len(requests)
        successes = sum(1 for item in requests if item.status == "SUCCESS")
        errors = sum(1 for item in requests if item.status == "ERROR")
        latencies = [item.latency_ms for item in requests if item.latency_ms is not None]
        return {
            "requests": total,
            "successes": successes,
            "errors": errors,
            "avg_latency_ms": (
                round(sum(latencies) / len(latencies)) if latencies else None
            ),
            "session_count": self._session_count(account_id),
        }

    def _session_count(self, account_id: str) -> int:
        with self._database.session() as session:
            return len(
                session.scalars(
                    select(ChatSession.id).where(ChatSession.account_id == account_id)
                ).all()
            )

