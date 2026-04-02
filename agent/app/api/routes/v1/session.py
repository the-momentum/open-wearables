from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from app.schemas.session import SessionCreateResponse, SessionDeactivateResponse, SessionRequest
from app.services.chat_session import ChatSessionService
from app.utils.auth import CurrentUserId

router = APIRouter(prefix="/session", tags=["session"])
logger = logging.getLogger(__name__)

ChatSessionServiceDep = Annotated[ChatSessionService, Depends(ChatSessionService)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_or_get_session(
    body: SessionRequest,
    current_user: CurrentUserId,
    service: ChatSessionServiceDep,
) -> SessionCreateResponse:
    session, conversation = await service.upsert_session(current_user, body.session_id)
    return SessionCreateResponse(
        session_id=session.id,
        conversation_id=conversation.id,
        created_at=session.created_at,
    )


@router.patch("/{session_id}")
async def deactivate_session(
    session_id: UUID,
    current_user: CurrentUserId,
    service: ChatSessionServiceDep,
) -> SessionDeactivateResponse:
    session = await service.deactivate_session(session_id, current_user)
    return SessionDeactivateResponse(session_id=session.id)
