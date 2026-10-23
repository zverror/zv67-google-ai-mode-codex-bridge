"""Chat Completions endpoint with SSE streaming."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from zv67.accounts.service import AccountService, AccountStatus
from zv67.api.deps import (
    get_accounts,
    get_provider,
    get_router,
    get_sessions,
    get_settings,
    get_stats,
    require_api_key,
)
from zv67.api.errors import ApiError, provider_http_status
from zv67.domain import (
    AssistantMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    MockContentError,
    normalize_chat_request,
)
from zv67.routing.router import (
    AccountLease,
    AccountRouter,
    NoAccountAvailable,
    RoutingCandidate,
    RoutingStrategy,
)
from zv67.sessions.manager import SessionManager, SessionView
from zv67.statistics.collector import RequestStatistics
from zv67.upstream.base import ProviderError, ProviderErrorKind, UpstreamProvider

router = APIRouter()


def _candidates(accounts: AccountService) -> list[RoutingCandidate]:
    return [
        RoutingCandidate(
            account_id=view.id,
            weight=view.routing_weight,
            concurrency_limit=view.concurrency_limit,
            enabled=view.enabled,
            status=view.connection_status,
        )
        for view in accounts.list()
    ]


async def _lease_for(
    request: Request,
    *,
    session: SessionView,
    manual_account_id: str | None,
) -> AccountLease | None:
    accounts = get_accounts(request)
    candidates = _candidates(accounts)
    if not candidates:
        return None
    settings = get_settings(request)
    try:
        return await get_router(request).acquire(
            candidates,
            strategy=RoutingStrategy(
                getattr(request.app.state, "routing_strategy", settings.routing_strategy)
            ),
            sticky_account_id=session.account_id,
            manual_account_id=manual_account_id,
        )
    except NoAccountAvailable as exc:
        raise ApiError(
            503,
            str(exc),
            error_type="server_error",
            code="no_account_available",
        ) from exc


def _bind(sessions: SessionManager, session: SessionView, lease: AccountLease | None) -> SessionView:
    if lease is not None and session.account_id is None:
        sessions.bind_account(session.id, lease.account_id)
        refreshed = sessions.get(session.id)
        if refreshed is not None:
            return refreshed
    return session


def _validate(payload: ChatCompletionRequest, provider_models: set[str], settings) -> None:
    if payload.model not in provider_models:
        raise ApiError(
            404,
            f"model '{payload.model}' does not exist",
            code="model_not_found",
            param="model",
        )
    if payload.tools and payload.model != "google-ai-mode":
        raise ApiError(
            400,
            "tool calling is not implemented for this model",
            code="unsupported_feature",
            param="tools",
        )
    if payload.tool_choice is not None and payload.model != "google-ai-mode":
        raise ApiError(
            400,
            "tool choice is not implemented for this model",
            code="unsupported_feature",
            param="tool_choice",
        )
    if payload.n != 1:
        raise ApiError(
            400,
            "only n=1 is supported",
            code="unsupported_feature",
            param="n",
        )
    if len(payload.messages) > settings.max_messages:
        raise ApiError(
            400,
            f"too many messages (limit {settings.max_messages})",
            code="invalid_request",
            param="messages",
        )


def _chunks(text: str, size: int) -> list[str]:
    if not text:
        return [""]
    return [text[index : index + size] for index in range(0, len(text), size)]


@router.post(
    "/v1/chat/completions",
    dependencies=[Depends(require_api_key)],
    response_model=None,
)
async def chat_completions(
    payload: ChatCompletionRequest,
    request: Request,
    provider: UpstreamProvider = Depends(get_provider),
) -> ChatCompletionResponse | StreamingResponse:
    settings = get_settings(request)
    stats = get_stats(request)
    request_id = f"req_{uuid.uuid4().hex}"
    started = time.monotonic()
    stats.start(
        request_id=request_id,
        model_id=payload.model,
        backend=(
            provider.backend_for(payload.model)
            if hasattr(provider, "backend_for")
            else provider.provider_id
        ),
    )
    lease: AccountLease | None = None
    try:
        descriptors = await provider.list_models()
        _validate(payload, {descriptor.id for descriptor in descriptors}, settings)
        sessions = get_sessions(request)
        session_id = payload.session_id or request.headers.get("x-zv67-session-id")
        session = sessions.ensure(session_id)
        lease = await _lease_for(
            request,
            session=session,
            manual_account_id=payload.account_id,
        )
        session = _bind(sessions, session, lease)
        try:
            normalized = normalize_chat_request(
                payload,
                request_id=request_id,
                max_message_chars=settings.max_message_chars,
            )
        except MockContentError as exc:
            raise ApiError(
                400,
                str(exc),
                code="unsupported_content",
                param="messages",
            ) from exc
        if lease is not None:
            normalized = normalized.model_copy(update={"account_id": lease.account_id})
    except ApiError as exc:
        stats.finish(
            request_id,
            status="ERROR",
            http_status=exc.status_code,
            error_code=exc.code,
            latency_ms=_elapsed(started),
        )
        await _release(request, lease, None)
        raise
    stats.attach(
        request_id,
        session_id=session.id,
        account_id=lease.account_id if lease else None,
    )
    completion_id = f"chatcmpl-{normalized.request_id.removeprefix('req_')}"

    try:
        result = await provider.complete(normalized)
    except ProviderError as exc:
        await _finish_error(request, normalized.request_id, exc, started)
        await _release(request, lease, exc)
        raise
    except Exception:
        stats.finish(
            normalized.request_id,
            status="ERROR",
            http_status=500,
            error_code="internal_error",
            latency_ms=_elapsed(started),
        )
        await _release(request, lease, None)
        raise

    if payload.stream:
        return StreamingResponse(
            _chat_stream(
                request=request,
                text=result.text,
                completion_id=completion_id,
                model=result.model_id,
                normalized=normalized,
                session=session,
                lease=lease,
                started=started,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "x-zv67-session-id": session.id,
                "x-zv67-request-id": normalized.request_id,
            },
        )

    sessions.append_turn(session.id, "user", normalized.last_user_text or "")
    sessions.append_turn(session.id, "assistant", result.text)
    stats.finish(
        normalized.request_id,
        status="SUCCESS",
        http_status=200,
        latency_ms=_elapsed(started),
    )
    if lease is not None:
        accounts = get_accounts(request)
        accounts.record_success(lease.account_id)
    await _release(request, lease, None)
    return ChatCompletionResponse(
        id=completion_id,
        created=int(time.time()),
        model=result.model_id,
        choices=[Choice(message=AssistantMessage(content=result.text))],
        zv67={
            "request_id": normalized.request_id,
            "session_id": session.id,
            "account_id": lease.account_id if lease else None,
            "upstream_session_id": result.upstream_session_id,
        },
    )


async def _finish_error(
    request: Request,
    request_id: str,
    exc: ProviderError,
    started: float,
) -> None:
    status, _, code = provider_http_status(exc.kind)
    get_stats(request).finish(
        request_id,
        status="ERROR",
        http_status=status,
        error_code=code,
        latency_ms=_elapsed(started),
    )


async def _release(
    request: Request,
    lease: AccountLease | None,
    error: ProviderError | None,
) -> None:
    if lease is None:
        return
    cooldown = None
    if error is not None:
        if error.kind is ProviderErrorKind.RATE_LIMITED:
            cooldown = error.retry_after or 60.0
            get_accounts(request).record_error(
                lease.account_id,
                "rate limited by upstream",
                AccountStatus.COOLDOWN,
            )
        elif error.kind is ProviderErrorKind.UNAUTHORIZED:
            get_accounts(request).record_error(
                lease.account_id, "upstream authorization failed", AccountStatus.UNAUTHORIZED
            )
    await get_router(request).release(lease, cooldown_seconds=cooldown)


def _elapsed(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


async def _chat_stream(
    *,
    request: Request,
    text: str,
    completion_id: str,
    model: str,
    normalized,
    session: SessionView,
    lease: AccountLease | None,
    started: float,
) -> AsyncIterator[str]:
    stats = get_stats(request)
    created = int(time.time())
    try:
        first = True
        for piece in _chunks(text, get_settings(request).stream_chunk_chars):
            if await request.is_disconnected():
                stats.finish(
                    normalized.request_id,
                    status="CANCELLED",
                    http_status=499,
                    error_code="client_disconnected",
                    latency_ms=_elapsed(started),
                )
                return
            delta = {"content": piece}
            if first:
                delta["role"] = "assistant"
                first = False
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {"index": 0, "delta": delta, "finish_reason": None, "logprobs": None}
                ],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)
        final = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop", "logprobs": None}],
        }
        yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        get_sessions(request).append_turn(session.id, "user", normalized.last_user_text or "")
        get_sessions(request).append_turn(session.id, "assistant", text)
        stats.finish(
            normalized.request_id,
            status="SUCCESS",
            http_status=200,
            latency_ms=_elapsed(started),
        )
        if lease is not None:
            get_accounts(request).record_success(lease.account_id)
    except Exception:
        stats.finish(
            normalized.request_id,
            status="ERROR",
            http_status=500,
            error_code="stream_failed",
            latency_ms=_elapsed(started),
        )
        error = {"error": {"message": "stream failed", "type": "server_error", "code": "stream_failed"}}
        yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"
    finally:
        await _release(request, lease, None)

