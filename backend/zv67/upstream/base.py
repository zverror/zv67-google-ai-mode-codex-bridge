"""Interface every upstream backend must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Literal

from pydantic import BaseModel

from zv67.domain import ModelDescriptor, NormalizedRequest


class ProviderErrorKind(str, Enum):
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED = "unsupported"


class ProviderError(RuntimeError):
    """Normalized provider failure with an optional retry delay."""

    def __init__(
        self,
        kind: ProviderErrorKind,
        message: str,
        *,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retry_after = retry_after


class ProviderHealth(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    provider: str
    detail: str | None = None


class UpstreamResult(BaseModel):
    """Provider response text plus its external session identity."""

    text: str
    model_id: str
    upstream_session_id: str | None = None


class UpstreamProvider(ABC):
    """Async boundary between ZV67 and any chat backend."""

    provider_id: str

    @abstractmethod
    async def health(self) -> ProviderHealth:
        """Report provider availability without generating content."""

    @abstractmethod
    async def list_models(self) -> list[ModelDescriptor]:
        """Return models this provider can actually serve."""

    @abstractmethod
    async def complete(self, request: NormalizedRequest) -> UpstreamResult:
        """Produce one non-streaming completion."""

    async def aclose(self) -> None:
        """Release provider resources."""

