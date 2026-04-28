from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from app.schemas.conversation import ConversationCreateResponse, ConversationDeactivateResponse, ConversationRequest
from app.services.conversation import ConversationService
from app.utils.auth import CurrentUserId

router = APIRouter(prefix="/conversation", tags=["conversation"])
logger = logging.getLogger(__name__)

ConversationServiceDep = Annotated[ConversationService, Depends(ConversationService)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_or_get_conversation(
    body: ConversationRequest,
    current_user: CurrentUserId,
    service: ConversationServiceDep,
) -> ConversationCreateResponse:
    conversation, _ = await service.upsert(
        current_user,
        body.conversation_id,
        language=body.language.value if body.language else None,
        agent_mode=body.agent_mode.value if body.agent_mode else None,
    )
    return ConversationCreateResponse(
        conversation_id=conversation.id,
        created_at=conversation.created_at,
    )


@router.patch("/{conversation_id}")
async def deactivate_conversation(
    conversation_id: UUID,
    current_user: CurrentUserId,
    service: ConversationServiceDep,
) -> ConversationDeactivateResponse:
    conversation = await service.deactivate(conversation_id, current_user)
    return ConversationDeactivateResponse(conversation_id=conversation.id)
