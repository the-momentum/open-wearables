from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.integrations.celery.tasks.process_message import process_message
from app.schemas.chat import ChatRequest, ChatTaskResponse
from app.services.conversation import ConversationService
from app.utils.auth import CurrentUserId

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

ConversationServiceDep = Annotated[ConversationService, Depends(ConversationService)]


@router.post("/{conversation_id}")
async def send_message(
    conversation_id: UUID,
    body: ChatRequest,
    current_user: CurrentUserId,
    service: ConversationServiceDep,
) -> ChatTaskResponse:
    conversation, session = await service.get_active(conversation_id, current_user)

    task = process_message.delay(
        session_id=str(session.id),
        conversation_id=str(conversation.id),
        user_id=str(current_user),
        message=body.message,
        callback_url=str(body.callback_url),
    )

    logger.info(f"Queued task {task.id} for conversation {conversation.id}")
    return ChatTaskResponse(task_id=task.id)
