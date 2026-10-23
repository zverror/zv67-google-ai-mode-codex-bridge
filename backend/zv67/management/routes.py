"""Administrative API protected by a signed session cookie and CSRF token."""

from __future__ import annotations

import platform
import sys
import time
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from zv67 import __version__
from zv67.accounts.service import AccountStatus
from zv67.api.deps import (
    get_accounts,
    get_database,
    get_provider,
    get_router,
    get_sessions,
    get_settings,
    get_stats,
)
from zv67.api.errors import ApiError
from zv67.management.auth import (
    COOKIE_NAME,
    AdminAuth,
    AdminAuthError,
    AdminClaims,
)
from zv67.security.cookie_import import (
    CredentialParseError,
    normalize_credentials,
    parse_credentials_text,
)
from zv67.routing.router import RoutingStrategy

router = APIRouter(prefix="/admin/api")


class PasswordBody(BaseModel):
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


class AccountCreateBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    subscription_status: str = "unknown"
    concurrency_limit: int = Field(default=1, ge=1, le=100)
    routing_weight: int = Field(default=100, ge=1, le=1000)
    credentials: dict | None = None


class AccountPatchBody(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    concurrency_limit: int | None = Field(default=None, ge=1, le=100)
    routing_weight: int | None = Field(default=None, ge=1, le=1000)


class CredentialsBody(BaseModel):
    credentials: dict | list | None = None
    credentials_text: str | None = None


class SettingsBody(BaseModel):
    routing_strategy: Literal[
        "round_robin", "weighted_round_robin", "least_busy", "manual"
    ]


def _auth(request: Request) -> AdminAuth:
    auth = getattr(request.app.state, "admin_auth", None)
    if auth is None:
        raise ApiError(503, "admin API is not initialized", code="service_unavailable")
    return auth


def _allowed_origin(origin: str) -> bool:
    return origin.startswith("http://127.0.0.1:") or origin.startswith(
        "http://localhost:"
    ) or origin in ("http://127.0.0.1", "http://localhost")


def require_admin(request: Request) -> AdminClaims:
    auth = _auth(request)
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        header = request.headers.get("authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() == "bearer":
            token = value.strip()
    claims = auth.verify_session(token)
    if claims is None:
        raise ApiError(
            401,
            "administrator authentication required",
            error_type="authentication_error",
            code="not_authenticated",
        )
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and not _allowed_origin(origin):
            raise ApiError(403, "origin is not allowed", code="origin_rejected")
        if not auth.check_csrf(claims, request.headers.get("x-zv67-csrf")):
            raise ApiError(403, "invalid CSRF token", code="csrf_failed")
    return claims


def _set_session_cookie(response: Response, token: str, expires_at: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max(1, expires_at - int(time.time())),
        httponly=True,
        samesite="strict",
        path="/admin",
    )


def _login_response(auth: AdminAuth, client_key: str, password: str) -> Response:
    result = auth.login(client_key, password)
    if result is None:
        raise ApiError(
            401,
            "invalid administrator password",
            error_type="authentication_error",
            code="invalid_credentials",
        )
    token, csrf, expires_at = result
    response = _json_response({"csrf_token": csrf, "expires_at": expires_at})
    _set_session_cookie(response, token, expires_at)
    return response


def _json_response(payload: dict) -> Response:
    from fastapi.responses import JSONResponse

    return JSONResponse(payload)


@router.get("/auth/status")
async def auth_status(request: Request) -> dict[str, object]:
    auth = _auth(request)
    token = request.cookies.get(COOKIE_NAME)
    claims = auth.verify_session(token)
    return {
        "configured": auth.configured(),
        "authenticated": claims is not None,
        "csrf_token": auth.csrf_for(claims.jti) if claims else None,
    }


@router.post("/auth/setup")
async def auth_setup(body: PasswordBody, request: Request) -> Response:
    auth = _auth(request)
    try:
        auth.setup(body.password)
    except AdminAuthError as exc:
        raise ApiError(400, str(exc), code="invalid_password") from exc
    request.app.state.audit.record("admin.setup")
    return _login_response(auth, _client_key(request), body.password)


@router.post("/auth/login")
async def auth_login(body: PasswordBody, request: Request) -> Response:
    try:
        return _login_response(_auth(request), _client_key(request), body.password)
    except AdminAuthError as exc:
        raise ApiError(429, str(exc), code="rate_limited") from exc


@router.post("/auth/logout")
async def auth_logout() -> Response:
    response = _json_response({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/admin")
    return response


@router.post("/auth/password", dependencies=[Depends(require_admin)])
async def change_password(body: ChangePasswordBody, request: Request) -> dict[str, bool]:
    try:
        _auth(request).change_password(body.current_password, body.new_password)
    except AdminAuthError as exc:
        raise ApiError(400, str(exc), code="invalid_password") from exc
    request.app.state.audit.record("admin.password_changed")
    return {"ok": True}


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/overview", dependencies=[Depends(require_admin)])
async def overview(request: Request) -> dict[str, object]:
    provider = get_provider(request)
    health = await provider.health()
    summary = get_stats(request).summary(hours=24)
    accounts = get_accounts(request).list()
    return {
        "service": {
            "status": "ok" if health.status == "ok" else "degraded",
            "version": __version__,
            "provider": health.provider,
            "provider_status": health.status,
            "mock": provider.provider_id == "mock",
        },
        "accounts": {
            "total": len(accounts),
            "enabled": sum(1 for account in accounts if account.enabled),
        },
        "summary": summary.model_dump(mode="json"),
        "routing_strategy": request.app.state.routing_strategy,
    }


@router.get("/accounts", dependencies=[Depends(require_admin)])
async def list_accounts(request: Request) -> list[dict[str, object]]:
    service = get_accounts(request)
    router_state = get_router(request)
    return [
        {
            **view.model_dump(mode="json"),
            "statistics": service.statistics(view.id),
            "active_requests": router_state.active_requests(view.id),
            "in_cooldown": router_state.in_cooldown(view.id),
        }
        for view in service.list()
    ]


@router.post("/accounts", dependencies=[Depends(require_admin)])
async def create_account(body: AccountCreateBody, request: Request) -> dict[str, object]:
    try:
        view = get_accounts(request).add(
            body.display_name,
            subscription_status=body.subscription_status,
            concurrency_limit=body.concurrency_limit,
            routing_weight=body.routing_weight,
            credentials=body.credentials,
        )
    except ValueError as exc:
        raise ApiError(400, str(exc), code="invalid_request") from exc
    request.app.state.audit.record(
        "account.created", target=view.id, detail=view.display_name
    )
    return view.model_dump(mode="json")


@router.patch("/accounts/{account_id}", dependencies=[Depends(require_admin)])
async def patch_account(
    account_id: str, body: AccountPatchBody, request: Request
) -> dict[str, object]:
    service = get_accounts(request)
    existing = service.get(account_id)
    if existing is None:
        raise ApiError(404, "account not found", code="not_found")
    try:
        service.update(
            account_id,
            display_name=body.display_name,
            concurrency_limit=body.concurrency_limit,
            routing_weight=body.routing_weight,
        )
    except ValueError as exc:
        raise ApiError(400, str(exc), code="invalid_request") from exc
    if body.enabled is not None:
        service.set_enabled(account_id, body.enabled)
    request.app.state.audit.record("account.updated", target=account_id)
    updated = service.get(account_id)
    return updated.model_dump(mode="json") if updated else {}


@router.delete("/accounts/{account_id}", dependencies=[Depends(require_admin)])
async def delete_account(account_id: str, request: Request) -> dict[str, bool]:
    removed = get_accounts(request).remove(account_id)
    if not removed:
        raise ApiError(404, "account not found", code="not_found")
    request.app.state.audit.record("account.deleted", target=account_id)
    return {"ok": True}


@router.post("/accounts/{account_id}/check", dependencies=[Depends(require_admin)])
async def check_account(account_id: str, request: Request) -> dict[str, object]:
    service = get_accounts(request)
    account = service.get(account_id)
    if account is None:
        raise ApiError(404, "account not found", code="not_found")
    provider = get_provider(request)
    if provider.provider_id == "mock":
        service.set_status(account_id, AccountStatus.ACTIVE)
        request.app.state.audit.record("account.checked", target=account_id)
        return {
            "status": "ACTIVE",
            "real_upstream": False,
            "detail": "mock provider does not perform a remote check",
        }
    service.set_status(account_id, AccountStatus.UNKNOWN)
    return {
        "status": "NOT TESTED",
        "real_upstream": True,
        "detail": "a real upstream adapter is not available",
    }


@router.put("/accounts/{account_id}/credentials", dependencies=[Depends(require_admin)])
async def set_credentials(
    account_id: str, body: CredentialsBody, request: Request
) -> dict[str, object]:
    service = get_accounts(request)
    if service.get(account_id) is None:
        raise ApiError(404, "account not found", code="not_found")
    credentials = request.app.state.credentials
    database = get_database(request)
    try:
        if body.credentials_text is not None:
            payload = parse_credentials_text(body.credentials_text)
        elif body.credentials is not None:
            payload = normalize_credentials(body.credentials)
        else:
            raise CredentialParseError("credentials payload is empty")
    except CredentialParseError as exc:
        raise ApiError(400, str(exc), code="invalid_credentials") from exc
    with database.session() as session:
        metadata = credentials.store(session, account_id, payload)
    request.app.state.audit.record("credentials.updated", target=account_id)
    return {
        "ok": True,
        "fingerprint": metadata.fingerprint,
        "scheme": metadata.scheme,
    }


@router.get("/models", dependencies=[Depends(require_admin)])
async def admin_models(request: Request) -> list[dict[str, object]]:
    provider = get_provider(request)
    return [
        {
            "id": descriptor.id,
            "display_name": descriptor.display_name,
            "provider": descriptor.provider,
            "upstream": descriptor.upstream,
            "capabilities": {
                name: status.value for name, status in descriptor.capabilities.items()
            },
        }
        for descriptor in await provider.list_models()
    ]


@router.get("/stats", dependencies=[Depends(require_admin)])
async def stats(request: Request, hours: int = 24) -> dict[str, object]:
    if hours < 1 or hours > 24 * 365:
        raise ApiError(400, "hours must be between 1 and 8760", code="invalid_request")
    return get_stats(request).summary(hours=hours).model_dump(mode="json")


@router.get("/stats/timeseries", dependencies=[Depends(require_admin)])
async def stats_timeseries(
    request: Request, hours: int = 24, bucket_minutes: int = 60
) -> list[dict[str, object]]:
    if hours < 1 or hours > 24 * 365:
        raise ApiError(400, "hours must be between 1 and 8760", code="invalid_request")
    try:
        series = get_stats(request).timeseries(hours=hours, bucket_minutes=bucket_minutes)
    except ValueError as exc:
        raise ApiError(400, str(exc), code="invalid_request") from exc
    return [item.model_dump(mode="json") for item in series]


@router.get("/requests", dependencies=[Depends(require_admin)])
async def requests_log(request: Request, limit: int = 100) -> list[dict[str, object]]:
    return [
        row.model_dump(mode="json") for row in get_stats(request).recent(limit=limit)
    ]


@router.get("/sessions", dependencies=[Depends(require_admin)])
async def sessions(request: Request, limit: int = 100) -> list[dict[str, object]]:
    return [
        view.model_dump(mode="json")
        for view in get_sessions(request).list_sessions(limit=limit)
    ]


@router.delete("/sessions/{session_id}", dependencies=[Depends(require_admin)])
async def delete_session(session_id: str, request: Request) -> dict[str, bool]:
    removed = get_sessions(request).delete(session_id)
    if not removed:
        raise ApiError(404, "session not found", code="not_found")
    request.app.state.audit.record("session.deleted", target=session_id)
    return {"ok": True}


@router.get("/settings", dependencies=[Depends(require_admin)])
async def admin_settings(request: Request) -> dict[str, object]:
    settings = get_settings(request)
    return {
        "routing_strategy": request.app.state.routing_strategy,
        "session_ttl_hours": settings.session_ttl_hours,
        "max_messages": settings.max_messages,
        "max_message_chars": settings.max_message_chars,
        "host": settings.host,
        "port": settings.port,
        "api_key_configured": settings.api_key is not None,
    }


@router.put("/settings", dependencies=[Depends(require_admin)])
async def update_settings(body: SettingsBody, request: Request) -> dict[str, object]:
    request.app.state.settings_store.set("routing_strategy", body.routing_strategy)
    request.app.state.routing_strategy = body.routing_strategy
    request.app.state.audit.record(
        "settings.updated", detail=f"routing_strategy={body.routing_strategy}"
    )
    return {"routing_strategy": request.app.state.routing_strategy}


@router.get("/system", dependencies=[Depends(require_admin)])
async def system(request: Request) -> dict[str, object]:
    settings = get_settings(request)
    provider = get_provider(request)
    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "database_path": str(settings.resolved_database_path),
        "data_dir": str(settings.data_dir),
        "provider": provider.provider_id,
        "mock": provider.provider_id == "mock",
        "master_key_store": settings.master_key_store,
        "routing_strategy": request.app.state.routing_strategy,
    }


@router.get("/audit", dependencies=[Depends(require_admin)])
async def audit_log(request: Request, limit: int = 100) -> list[dict[str, object]]:
    return [
        entry.model_dump(mode="json")
        for entry in request.app.state.audit.recent(limit=limit)
    ]

