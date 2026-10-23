"""Account lifecycle, session isolation and idempotent tool calls."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from zv67.accounts.service import AccountService, AccountStatus
from zv67.persistence.models import ChatSession, SessionTurn
from zv67.sessions.manager import (
    SessionAccountConflict,
    SessionExpired,
    SessionManager,
)


@pytest.fixture
def services(client, app):
    database = app.state.database
    return (
        AccountService(database, app.state.credentials),
        SessionManager(database, app.state.secret_box),
        database,
    )


def test_account_crud_and_credential_isolation(client, services):
    accounts, _, _ = services
    first = accounts.add(
        "Primary",
        credentials={"cookies": [{"name": "__Secure-1PSID", "value": "one"}]},
    )
    second = accounts.add("Secondary", credentials={"cookies": [{"name": "__Secure-1PSID", "value": "two"}]})

    assert first.has_credentials is True
    assert [item.display_name for item in accounts.list()] == ["Primary", "Secondary"]

    accounts.record_success(first.id)
    accounts.record_error(second.id, "temporary failure", AccountStatus.DEGRADED)
    refreshed = accounts.get(first.id)
    assert refreshed.connection_status == "ACTIVE"
    assert refreshed.last_error is None

    assert accounts.set_enabled(second.id, False) is True
    assert accounts.get(second.id).connection_status == "DISABLED"
    assert accounts.remove(second.id) is True
    assert accounts.get(second.id) is None


def test_session_history_is_encrypted_and_account_pinned(client, services):
    accounts, sessions, database = services
    primary = accounts.add("Primary")
    secondary = accounts.add("Secondary")

    session = sessions.create(account_id=primary.id)
    sessions.append_turn(session.id, "user", "secret prompt")
    sessions.append_turn(session.id, "assistant", "answer")

    history = sessions.history(session.id)
    assert [turn.content for turn in history] == ["secret prompt", "answer"]

    with database.session() as db:
        stored = db.scalar(
            select(SessionTurn.content_ciphertext).where(
                SessionTurn.session_id == session.id
            )
        )
    assert "secret prompt" not in stored

    with pytest.raises(SessionAccountConflict):
        sessions.bind_account(session.id, secondary.id)

    assert sessions.get(session.id).turn_count == 2
    assert sessions.delete(session.id) is True
    assert sessions.get(session.id) is None


def test_expired_session_cannot_be_reused(client, services):
    accounts, sessions, database = services
    account = accounts.add("Primary")
    session = sessions.create(account_id=account.id)

    with database.session() as db:
        record = db.get(ChatSession, session.id)
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(SessionExpired):
        sessions.ensure(session.id)
    assert sessions.purge_expired() == 1


def test_tool_calls_are_idempotent(client, services):
    accounts, sessions, _ = services
    account = accounts.add("Primary")
    session = sessions.create(account_id=account.id)

    first = sessions.register_tool_call(
        session.id, "call_1", "read_file", '{"path":"a.txt"}'
    )
    duplicate = sessions.register_tool_call(
        session.id, "call_1", "read_file", '{"path":"a.txt"}'
    )

    assert first.created is True
    assert duplicate.created is False
    assert sessions.complete_tool_call("call_1", "content") is True
    assert sessions.complete_tool_call("call_1", "content again") is False
    assert sessions.get_tool_call("call_1").result == "content"
    assert sessions.tool_call_arguments("call_1") == '{"path":"a.txt"}'


def test_removing_account_deletes_its_sessions(client, services):
    accounts, sessions, database = services
    account = accounts.add("Primary")
    session = sessions.create(account_id=account.id)

    assert accounts.remove(account.id) is True

    with database.session() as db:
        assert db.get(ChatSession, session.id) is None

