"""OpenAI-style error responses."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from zv67.upstream.base import ProviderError, ProviderErrorKind

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Expected client-facing failure."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        error_type: str = "invalid_request_error",
        code: str | None = None,
        param: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        self.code = code
        self.param = param


def error_response(
    status_code: int,
    message: str,
    *,
    error_type: str = "invalid_request_error",
    code: str | None = None,
    param: str | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "message": message,
            "type": error_type,
            "param": param,
            "code": code,
        }
    }
    return JSONResponse(status_code=status_code, content=body)


_PROVIDER_STATUS: dict[ProviderErrorKind, tuple[int, str, str]] = {
    ProviderErrorKind.UNAUTHORIZED: (502, "upstream_authentication_error", "unauthorized"),
    ProviderErrorKind.RATE_LIMITED: (429, "rate_limit_error", "rate_limited"),
    ProviderErrorKind.TIMEOUT: (504, "upstream_timeout", "timeout"),
    ProviderErrorKind.UNAVAILABLE: (503, "upstream_unavailable", "unavailable"),
    ProviderErrorKind.INVALID_REQUEST: (400, "invalid_request_error", "invalid_request"),
    ProviderErrorKind.UNSUPPORTED: (400, "invalid_request_error", "unsupported_feature"),
}


def provider_http_status(kind: ProviderErrorKind) -> tuple[int, str, str]:
    return _PROVIDER_STATUS[kind]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(
            exc.status_code,
            exc.message,
            error_type=exc.error_type,
            code=exc.code,
            param=exc.param,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = first.get("msg", "request validation failed")
        return error_response(
            400,
            f"{message} ({location})" if location else message,
            code="invalid_request",
            param=location or None,
        )

    @app.exception_handler(ProviderError)
    async def _provider_error(_: Request, exc: ProviderError) -> JSONResponse:
        status, error_type, code = _PROVIDER_STATUS[exc.kind]
        headers = None
        if exc.retry_after is not None:
            headers = {"Retry-After": str(int(exc.retry_after))}
        response = error_response(
            status,
            exc.message,
            error_type=error_type,
            code=code,
        )
        if headers:
            response.headers.update(headers)
        return response

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled request failure", exc_info=exc)
        return error_response(
            500,
            "internal server error",
            error_type="server_error",
            code="internal_error",
        )

