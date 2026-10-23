"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from zv67.config import Settings
from zv67.main import create_app


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        api_key=None,
        database_path=tmp_path / "zv67.sqlite3",
        data_dir=tmp_path,
        master_key_store="file",
    )
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def anyio_backend():
    return "asyncio"

