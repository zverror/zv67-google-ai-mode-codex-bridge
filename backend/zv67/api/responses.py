"""OpenAI Responses API subset backed by the same normalized provider."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from zv67.accounts.service import AccountStatus
from zv67.api.chat import _bind, _chunks, _elapsed, _lease_for, _release
from zv67.api.deps import (
    get_accounts,
    get_provider,
    get_sessions,
    get_settings,
    get_stats,
    require_api_key,
)
from zv67.api.errors import ApiError, provider_http_status
from zv67.domain import (
    MockContentError,
    ResponseObject,
    ResponseOutputMessage,
    ResponseRequest,
    ResponseTextPart,
    normalize_response_request,
)
from zv67.upstream.base import ProviderError, ProviderErrorKind, UpstreamProvider

router = APIRouter()


@router.post(
    "/v1/responses",
    dependencies=[Depends(require_api_key)],
    response_model=None,
)
async def create_response(
    payload: ResponseRequest,
    request: Request,
    provider: UpstreamProvider = Depends(get_provider),
) -> ResponseObject | StreamingResponse:
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
    lease = None
    try:
        descriptors = await provider.list_models()
        if payload.model not in {descriptor.id for descriptor in descriptors}:
            raise ApiError(
                404,
                f"model '{payload.model}' does not exist",
                code="model_not_found",
                param="model",
            )
        if payload.tools and not payload.model.startswith("google-ai-mode"):
            raise ApiError(
                400,
                "tool calling is not implemented for this model",
                code="unsupported_feature",
                param="tools",
            )
        if payload.previous_response_id is not None:
            raise ApiError(
                400,
                "previous_response_id is not supported",
                code="unsupported_feature",
                param="previous_response_id",
            )
        if isinstance(payload.input, list) and len(payload.input) > settings.max_messages:
            raise ApiError(
                400,
                f"too many input items (limit {settings.max_messages})",
                code="invalid_request",
                param="input",
            )
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
            normalized = normalize_response_request(
                payload,
                request_id=request_id,
                max_message_chars=settings.max_message_chars,
            )
        except MockContentError as exc:
            raise ApiError(
                400,
                str(exc),
                code="unsupported_content",
                param="input",
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
    response_id = f"resp_{uuid.uuid4().hex}"
    message_id = f"msg_{uuid.uuid4().hex}"

    try:
        result = await provider.complete(normalized)
    except ProviderError as exc:
        status, _, code = provider_http_status(exc.kind)
        stats.finish(
            normalized.request_id,
            status="ERROR",
            http_status=status,
            error_code=code,
            latency_ms=_elapsed(started),
        )
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

    zv67 = {
        "request_id": normalized.request_id,
        "session_id": session.id,
        "account_id": lease.account_id if lease else None,
        "upstream_session_id": result.upstream_session_id,
    }

    if payload.stream:
        return StreamingResponse(
            _response_stream(
                request=request,
                text=result.text,
                response_id=response_id,
                message_id=message_id,
                model=result.model_id,
                normalized=normalized,
                session=session,
                lease=lease,
                started=started,
                instructions=payload.instructions,
                metadata=payload.metadata or {},
                zv67=zv67,
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
        get_accounts(request).record_success(lease.account_id)
    await _release(request, lease, None)
    return _response_object(
        response_id=response_id,
        message_id=message_id,
        model=result.model_id,
        text=result.text,
        instructions=payload.instructions,
        metadata=payload.metadata or {},
        zv67=zv67,
    )


def _response_object(
    *,
    response_id: str,
    message_id: str,
    model: str,
    text: str,
    instructions: str | None,
    metadata: dict[str, Any],
    zv67: dict[str, Any],
) -> ResponseObject:
    return ResponseObject(
        id=response_id,
        created_at=int(time.time()),
        model=model,
        output=[
            ResponseOutputMessage(
                id=message_id,
                content=[ResponseTextPart(text=text)],
            )
        ],
        instructions=instructions,
        metadata=metadata,
        zv67=zv67,
    )


async def _response_stream(
    *,
    request: Request,
    text: str,
    response_id: str,
    message_id: str,
    model: str,
    normalized,
    session,
    lease,
    started: float,
    instructions: str | None,
    metadata: dict[str, Any],
    zv67: dict[str, Any],
) -> AsyncIterator[str]:
    stats = get_stats(request)
    sequence = 0
    created_at = int(time.time())

    def event(name: str, payload: dict[str, Any]) -> str:
        nonlocal sequence
        payload = {"type": name, "sequence_number": sequence, **payload}
        sequence += 1
        return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    skeleton = {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "model": model,
        "output": [],
        "usage": None,
        "error": None,
        "instructions": instructions,
        "metadata": metadata,
        "zv67": zv67,
    }
    try:
        yield event("response.created", {"response": {**skeleton, "status": "in_progress"}})
        yield event("response.in_progress", {"response": {**skeleton, "status": "in_progress"}})
        item = {
            "id": message_id,
            "type": "message",
            "status": "in_progress",
            "role": "assistant",
            "content": [],
        }
        yield event("response.output_item.added", {"output_index": 0, "item": item})
        yield event(
            "response.content_part.added",
            {
                "item_id": message_id,
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": "", "annotations": []},
            },
        )
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
            yield event(
                "response.output_text.delta",
                {
                    "item_id": message_id,
                    "output_index": 0,
                    "content_index": 0,
                    "delta": piece,
                },
            )
            await asyncio.sleep(0)
        yield event(
            "response.output_text.done",
            {
                "item_id": message_id,
                "output_index": 0,
                "content_index": 0,
                "text": text,
            },
        )
        part = {"type": "output_text", "text": text, "annotations": []}
        yield event(
            "response.content_part.done",
            {
                "item_id": message_id,
                "output_index": 0,
                "content_index": 0,
                "part": part,
            },
        )
        completed_item = {
            "id": message_id,
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [part],
        }
        yield event(
            "response.output_item.done",
            {"output_index": 0, "item": completed_item},
        )
        completed = {
            **skeleton,
            "status": "completed",
            "output": [completed_item],
        }
        yield event("response.completed", {"response": completed})
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
        yield event(
            "error",
            {
                "error": {
                    "message": "stream failed",
                    "type": "server_error",
                    "code": "stream_failed",
                }
            },
        )
    finally:
        await _release(request, lease, None)

