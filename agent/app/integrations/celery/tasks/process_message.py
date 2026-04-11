from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

import httpx
from celery import shared_task

from app.agent.static.default_msgs import WORKFLOW_ERROR_MSG
from app.agent.workflows.agent_workflow import workflow_engine
from app.config import settings
from app.database import AsyncSessionLocal
from app.repositories import conversation_repository, session_repository
from app.services.conversation import ConversationService

logger = logging.getLogger(__name__)


async def _run(
    task_id: str,
    session_id: str,
    conversation_id: str,
    user_id: str,
    message: str,
    callback_url: str,
) -> None:
    async with AsyncSessionLocal() as db:
        service = ConversationService(db)
        conversation = await conversation_repository.get_by_id(db, UUID(conversation_id))
        session = await session_repository.get_by_id(db, UUID(session_id))

        history: list[dict] = []
        if conversation is not None:
            try:
                history = await service.build_history(conversation, db)
            except Exception:
                logger.exception("Failed to build history — proceeding with empty history")

        # Run the agent workflow
        try:
            response_text = await workflow_engine.run(
                user_id=UUID(user_id),
                message=message,
                history=history,
            )
        except Exception:
            logger.exception("Workflow failed for task %s", task_id)
            response_text = WORKFLOW_ERROR_MSG

        # Persist both messages
        if conversation is not None and session is not None:
            try:
                await service.save_messages(
                    conversation_id=UUID(conversation_id),
                    session_id=UUID(session_id),
                    user_message=message,
                    assistant_message=response_text,
                )
            except Exception:
                logger.exception("Failed to save messages for task %s", task_id)

    # POST result to callback URL
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                callback_url,
                json={"task_id": task_id, "status": "done", "result": response_text},
            )
    except httpx.HTTPError as exc:
        logger.warning("Callback failed for task %s: %s", task_id, exc)


@shared_task(bind=True, max_retries=settings.max_retries, default_retry_delay=5)
def process_message(
    self: Any,
    session_id: str,
    conversation_id: str,
    user_id: str,
    message: str,
    callback_url: str,
) -> None:
    asyncio.run(
        _run(
            task_id=self.request.id,
            session_id=session_id,
            conversation_id=conversation_id,
            user_id=user_id,
            message=message,
            callback_url=callback_url,
        )
    )
