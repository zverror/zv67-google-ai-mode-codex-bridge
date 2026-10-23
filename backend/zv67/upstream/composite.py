"""Serve mock and Google models from one provider instance."""

from __future__ import annotations

from zv67.domain import ModelDescriptor, NormalizedRequest
from zv67.upstream.base import (
    ProviderError,
    ProviderErrorKind,
    ProviderHealth,
    UpstreamProvider,
    UpstreamResult,
)


class CompositeProvider(UpstreamProvider):
    provider_id = "composite"

    def __init__(self, providers: list[UpstreamProvider]) -> None:
        self._providers = providers

    def backend_for(self, model_id: str) -> str:
        for provider in self._providers:
            if any(model.id == model_id for model in getattr(provider, "_models", [])):
                return provider.provider_id
        return self.provider_id

    async def health(self) -> ProviderHealth:
        statuses = [await provider.health() for provider in self._providers]
        healthy = [item for item in statuses if item.status == "ok"]
        return ProviderHealth(
            status="ok" if healthy else statuses[0].status,
            provider=self.provider_id,
            detail=", ".join(item.provider for item in healthy) or "no healthy providers",
        )

    async def list_models(self) -> list[ModelDescriptor]:
        models: list[ModelDescriptor] = []
        for provider in self._providers:
            models.extend(await provider.list_models())
        return models

    async def complete(self, request: NormalizedRequest) -> UpstreamResult:
        for provider in self._providers:
            models = await provider.list_models()
            if any(model.id == request.model_id for model in models):
                return await provider.complete(request)
        raise ProviderError(
            ProviderErrorKind.INVALID_REQUEST,
            f"model '{request.model_id}' is not served",
        )

    async def aclose(self) -> None:
        for provider in self._providers:
            await provider.aclose()

