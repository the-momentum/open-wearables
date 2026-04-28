from fastapi import APIRouter

from app.api.routes.v1.chat import router as chat_router
from app.api.routes.v1.conversation import router as conversation_router

v1_router = APIRouter()
v1_router.include_router(conversation_router)
v1_router.include_router(chat_router)

__all__ = ["v1_router"]
