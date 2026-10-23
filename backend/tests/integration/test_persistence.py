"""Database lifecycle, migrations and restart persistence."""

from __future__ import annotations

import sqlite3

from sqlalchemy import select

from zv67.persistence.db import Database
from zv67.persistence.migrations import downgrade_to_base, run_migrations
from zv67.persistence.models import Account


def test_migrations_apply_to_empty_database_and_survive_restart(tmp_path):
    path = tmp_path / "zv67.sqlite3"

    run_migrations(path)
    with Database(path).session() as session:
        session.add(Account(id="acc_1", display_name="Persisted"))

    database = Database(path)
    with database.session() as session:
        assert session.scalar(select(Account.display_name)) == "Persisted"
    database.close()

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "accounts" in tables
        assert "alembic_version" in tables
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_downgrade_and_upgrade_roundtrip(tmp_path):
    path = tmp_path / "zv67.sqlite3"

    run_migrations(path)
    downgrade_to_base(path)

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "accounts" not in tables

    run_migrations(path)
    with Database(path).session() as session:
        session.add(Account(id="acc_2", display_name="Again"))
    assert path.exists()


def test_foreign_keys_cascade_on_account_delete(tmp_path):
    from zv67.persistence.models import CredentialMetadata

    path = tmp_path / "zv67.sqlite3"
    run_migrations(path)
    database = Database(path)
    with database.session() as session:
        session.add(Account(id="acc_3", display_name="Cascade"))
        session.add(
            CredentialMetadata(
                id="cred_3",
                account_id="acc_3",
                secret_ref="account:acc_3",
                fingerprint="abc",
                ciphertext="zv67:v1:x",
            )
        )
    with database.session() as session:
        account = session.get(Account, "acc_3")
        session.delete(account)
    with database.session() as session:
        assert session.scalar(select(CredentialMetadata)) is None
    database.close()

