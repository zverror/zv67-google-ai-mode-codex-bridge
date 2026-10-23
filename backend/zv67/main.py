"""FastAPI application factory."""

from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from zv67 import __version__
from zv67.api import api_router
from zv67.api.errors import register_error_handlers
from zv67.management.auth import AdminAuth
from zv67.management.routes import router as management_router
from zv67.management.service import AuditLog, SettingsStore
from zv67.management.static import router as static_router
from zv67.config import Settings
from zv67.persistence.db import Database
from zv67.persistence.migrations import run_migrations
from zv67.accounts.service import AccountService
from zv67.routing.router import AccountRouter
from zv67.security.credentials import CredentialService
from zv67.security.crypto import SecretBox, resolve_master_key_store
from zv67.sessions.manager import SessionManager
from zv67.statistics.collector import RequestStatistics
from zv67.upstream.base import UpstreamProvider
from zv67.upstream.mock import MockProvider
from zv67.upstream.composite import CompositeProvider
from zv67.upstream.google import GoogleAIModeProvider


def create_app(
    settings: Settings | None = None,
    provider: UpstreamProvider | None = None,
    database: Database | None = None,
) -> FastAPI:
    """Build an application with injected configuration and provider."""

    resolved_settings = settings or Settings.from_env()
    resolved_provider = provider or MockProvider()
    resolved_database = database or Database(
        resolved_settings.resolved_database_path
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if resolved_settings.auto_migrate and resolved_database.path != ":memory:":
            run_migrations(resolved_database.path)
        else:
            resolved_database.create_schema()
        key = resolve_master_key_store(
            resolved_settings.data_dir,
            resolved_settings.master_key_store,
        ).get_or_create()
        box = SecretBox(key)
        credentials = CredentialService(box)
        app.state.database = resolved_database
        app.state.secret_box = box
        app.state.credentials = credentials
        app.state.accounts = AccountService(resolved_database, credentials)
        app.state.sessions = SessionManager(
            resolved_database,
            box,
            default_ttl=timedelta(hours=resolved_settings.session_ttl_hours),
        )
        app.state.stats = RequestStatistics(resolved_database)
        app.state.stats.mark_stale_started()
        app.state.router = AccountRouter()
        app.state.settings_store = SettingsStore(resolved_database)
        app.state.audit = AuditLog(resolved_database)
        app.state.admin_auth = AdminAuth(
            resolved_database,
            hmac.new(key, b"zv67-admin-session", hashlib.sha256).digest(),
        )
        app.state.routing_strategy = app.state.settings_store.get(
            "routing_strategy", resolved_settings.routing_strategy
        )
        if resolved_settings.google_ai_mode_enabled:
            def load_credentials(account_id: str) -> dict:
                with resolved_database.session() as db_session:
                    return credentials.load(db_session, account_id) or {}

            google = GoogleAIModeProvider(
                load_credentials,
                max_sessions=resolved_settings.google_browser_max_sessions,
                timeout=resolved_settings.google_browser_timeout_seconds,
                headless=resolved_settings.google_browser_headless,
            )
            app.state.provider = CompositeProvider([resolved_provider, google])
        try:
            yield
        finally:
            await app.state.provider.aclose()
            resolved_database.close()

    app = FastAPI(
        title="ZV67",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.provider = resolved_provider
    app.state.database = None
    app.state.credentials = None
    app.state.accounts = None
    app.state.sessions = None
    app.state.stats = None
    app.state.router = None
    app.state.settings_store = None
    app.state.audit = None
    app.state.admin_auth = None
    app.state.routing_strategy = resolved_settings.routing_strategy
    app.include_router(api_router)
    app.include_router(management_router)
    app.include_router(static_router)
    register_error_handlers(app)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/admin"):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; "
                "script-src 'self'; object-src 'none'; base-uri 'none'",
            )
        return response

    return app


app = create_app()

