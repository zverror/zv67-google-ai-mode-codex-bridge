"""Shared FastAPI dependencies and service accessors."""

from __future__ import annotations

import hmac

from fastapi import Request

from zv67.accounts.service import AccountService
from zv67.api.errors import ApiError
from zv67.config import Settings
from zv67.persistence.db import Database
from zv67.routing.router import AccountRouter
from zv67.sessions.manager import SessionManager
from zv67.statistics.collector import RequestStatistics
from zv67.upstream.base import UpstreamProvider


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_provider(request: Request) -> UpstreamProvider:
    return request.app.state.provider


def _service(request: Request, name: str):
    value = getattr(request.app.state, name, None)
    if value is None:
        raise ApiError(
            503,
            "service is not initialized",
            error_type="server_error",
            code="service_unavailable",
        )
    return value


def get_database(request: Request) -> Database:
    return _service(request, "database")


def get_sessions(request: Request) -> SessionManager:
    return _service(request, "sessions")


def get_accounts(request: Request) -> AccountService:
    return _service(request, "accounts")


def get_stats(request: Request) -> RequestStatistics:
    return _service(request, "stats")


def get_router(request: Request) -> AccountRouter:
    return _service(request, "router")


def require_api_key(request: Request) -> None:
    """Bearer auth for the client API. Unset key is localhost development mode."""

    expected = get_settings(request).api_key
    if expected is None:
        return
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token.strip(), expected):
        raise ApiError(
            401,
            "invalid or missing API key",
            error_type="authentication_error",
            code="invalid_api_key",
        )

