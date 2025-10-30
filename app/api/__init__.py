from fastapi import APIRouter

from app.api.routes.v1 import v1_router
from app.config import settings

head_router = APIRouter()
head_router.include_router(v1_router, prefix=settings.api_v1)

__all__ = [
    "head_router",
]