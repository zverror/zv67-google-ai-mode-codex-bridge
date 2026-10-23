"""Deterministic local provider used for development and tests."""

from __future__ import annotations

from zv67.domain import CapabilityStatus, ModelDescriptor, NormalizedRequest
from zv67.upstream.base import (
    ProviderError,
    ProviderErrorKind,
    ProviderHealth,
    UpstreamProvider,
    UpstreamResult,
)

MOCK_MODEL_ID = "zv67-mock"


def default_mock_models() -> list[ModelDescriptor]:
    return [
        ModelDescriptor(
            id=MOCK_MODEL_ID,
            display_name="ZV67 Mock (not Google)",
            provider="ZV67",
            upstream="mock",
            capabilities={
                "chat": CapabilityStatus.VERIFIED,
                "streaming": CapabilityStatus.VERIFIED,
                "responses": CapabilityStatus.VERIFIED,
                "tool_calling": CapabilityStatus.UNSUPPORTED,
                "session_persistence": CapabilityStatus.VERIFIED,
                "images": CapabilityStatus.UNSUPPORTED,
            },
        )
    ]


class MockProvider(UpstreamProvider):
    """Produces a stable reply derived only from the last user message."""

    provider_id = "mock"

    def __init__(self, models: list[ModelDescriptor] | None = None) -> None:
        self._models = list(models) if models is not None else default_mock_models()

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="ok",
            provider=self.provider_id,
            detail="local deterministic provider",
        )

    async def list_models(self) -> list[ModelDescriptor]:
        return list(self._models)

    async def complete(self, request: NormalizedRequest) -> UpstreamResult:
        if request.model_id not in {model.id for model in self._models}:
            raise ProviderError(
                ProviderErrorKind.INVALID_REQUEST,
                f"model '{request.model_id}' is not served by the mock provider",
            )
        user_text = request.last_user_text
        if user_text is None:
            raise ProviderError(
                ProviderErrorKind.INVALID_REQUEST,
                "at least one user message is required",
            )
        reply = f"Mock response from {MOCK_MODEL_ID}: {user_text.strip()}"
        return UpstreamResult(text=reply, model_id=request.model_id)

