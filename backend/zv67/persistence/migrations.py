"""Programmatic Alembic upgrades for local startup and installers."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run_migrations(database_path: str | Path, root: Path | None = None) -> None:
    base = root or project_root()
    config = Config(str(base / "alembic.ini"))
    config.set_main_option("script_location", str(base / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(database_path)}")
    command.upgrade(config, "head")


def downgrade_to_base(database_path: str | Path, root: Path | None = None) -> None:
    base = root or project_root()
    config = Config(str(base / "alembic.ini"))
    config.set_main_option("script_location", str(base / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(database_path)}")
    command.downgrade(config, "base")

