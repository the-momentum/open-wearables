from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

import httpx

from app.database import AsyncSessionLocal
from app.repositories import chat_session_repository
from app.services.chat_session import ChatSessionService
from celery import shared_task

logger = logging.getLogger(__name__)


async def _run(
    task_id: str,
    session_id: str,
    conversation_id: str,
    message: str,
    response_text: str,
    callback_url: str,
) -> None:
    async with AsyncSessionLocal() as db:
        session = await chat_session_repository.get_by_id(db, UUID(session_id))
        if session:
            await ChatSessionService(db).save_messages(UUID(conversation_id), message, response_text, session)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                callback_url,
                json={"task_id": task_id, "status": "done", "result": response_text},
            )
    except httpx.HTTPError as e:
        logger.warning(f"Callback failed for task {task_id}: {e}")


@shared_task(bind=True, max_retries=3)
def process_message(self: Any, session_id: str, conversation_id: str, message: str, callback_url: str) -> None:
    # --- placeholder ---
    response_text = f"[STUB] Echo: {message}"
    # TODO: replace by WorkflowAgent
    # --- placeholder ---

    asyncio.run(_run(self.request.id, session_id, conversation_id, message, response_text, callback_url))
