from fastapi import APIRouter

from app.api.routes.v1 import v1_router
from app.config import settings
from app.extensions import collect_routers

head_router = APIRouter()
head_router.include_router(v1_router, prefix=settings.api_v1)

# Routers contributed by installed extensions, under the same API v1 prefix.
for _router in collect_routers():
    head_router.include_router(_router, prefix=settings.api_v1)

__all__ = [
    "head_router",
]
