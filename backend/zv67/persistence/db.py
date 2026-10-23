"""SQLite engine, sessions and connection-level safety settings."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


class Database:
    """Owns the SQLite engine and transaction boundaries."""

    def __init__(self, path: str | Path) -> None:
        raw = str(path)
        self.path = raw
        kwargs: dict[str, object] = {"future": True, "connect_args": {"check_same_thread": False}}
        if raw == ":memory:":
            kwargs["poolclass"] = StaticPool
            url = "sqlite://"
        else:
            file_path = Path(raw).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{file_path}"
        self.engine: Engine = create_engine(url, **kwargs)
        event.listen(self.engine, "connect", _configure_sqlite_connection)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_schema(self) -> None:
        """Create tables directly. Alembic remains the production path."""

        from zv67.persistence.models import Base

        Base.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

