"""Service health and model registry routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from zv67 import __version__
from zv67.api.deps import get_provider, require_api_key
from zv67.domain import ModelList, PublicModel
from zv67.upstream.base import UpstreamProvider

router = APIRouter()


@router.get("/health")
async def health(
    provider: UpstreamProvider = Depends(get_provider),
) -> dict[str, object]:
    provider_health = await provider.health()
    return {
        "status": "ok" if provider_health.status == "ok" else "degraded",
        "service": "zv67",
        "version": __version__,
        "provider": provider_health.provider,
        "provider_status": provider_health.status,
        "mock": provider.provider_id == "mock",
    }


@router.get("/v1/models", dependencies=[Depends(require_api_key)])
async def list_models(
    provider: UpstreamProvider = Depends(get_provider),
) -> ModelList:
    created = int(time.time())
    descriptors = await provider.list_models()
    return ModelList(
        data=[
            PublicModel(
                id=descriptor.id,
                created=created,
                owned_by=descriptor.provider,
                zv67={
                    "display_name": descriptor.display_name,
                    "upstream": descriptor.upstream,
                    "capabilities": {
                        name: status.value
                        for name, status in descriptor.capabilities.items()
                    },
                },
            )
            for descriptor in descriptors
        ]
    )

