from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.integrations.celery.tasks.process_message import process_message
from app.schemas.chat import ChatRequest, ChatTaskResponse
from app.services.chat_session import ChatSessionService
from app.utils.auth import CurrentUserId

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

ChatSessionServiceDep = Annotated[ChatSessionService, Depends(ChatSessionService)]


@router.post("/{session_id}")
async def send_message(
    session_id: UUID,
    body: ChatRequest,
    current_user: CurrentUserId,
    service: ChatSessionServiceDep,
) -> ChatTaskResponse:
    session, conversation = await service.get_active_session(session_id, current_user)

    task = process_message.delay(
        session_id=str(session.id),
        conversation_id=str(conversation.id),
        message=body.message,
        callback_url=str(body.callback_url),
    )

    logger.info(f"Queued task {task.id} for session {session.id}")
    return ChatTaskResponse(task_id=task.id)


