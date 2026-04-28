from fastapi import APIRouter

from app.api.routes.v1 import v1_router

head_router = APIRouter()
head_router.include_router(v1_router)

__all__ = ["head_router"]
