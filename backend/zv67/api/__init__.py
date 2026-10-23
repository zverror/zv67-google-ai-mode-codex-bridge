"""HTTP API layer."""

from fastapi import APIRouter

from zv67.api.chat import router as chat_router
from zv67.api.health import router as health_router
from zv67.api.responses import router as responses_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(responses_router)

__all__ = ["api_router"]

