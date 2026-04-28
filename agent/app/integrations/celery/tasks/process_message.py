from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import httpx

from app.agent.static.default_msgs import get_workflow_error_msg
from app.agent.workflows.agent_workflow import workflow_engine
from app.database import AsyncSessionLocal
from app.models.conversation import Conversation
from app.repositories import conversation_repository, session_repository
from app.schemas.agent import AgentMode
from app.schemas.language import Language
from app.services.conversation import ConversationService
from celery import current_task, shared_task

logger = logging.getLogger(__name__)


def _resolve_conversation_params(
    conversation: Conversation | None,
) -> tuple[Language | None, AgentMode]:
    if conversation is None:
        return None, AgentMode.GENERAL
    language = Language(conversation.language) if conversation.language else None
    agent_mode = AgentMode(conversation.agent_mode) if conversation.agent_mode else AgentMode.GENERAL
    return language, agent_mode


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

        language, agent_mode = _resolve_conversation_params(conversation)

        history: list[dict] = []
        if conversation is not None:
            try:
                history = await service.build_history(conversation)
            except Exception:
                logger.exception("Failed to build history — proceeding with empty history")

        try:
            response_text = await workflow_engine.run(
                user_id=UUID(user_id),
                message=message,
                history=history,
                mode=agent_mode,
                language=language,
            )
        except Exception:
            logger.exception("Workflow failed for task %s", task_id)
            response_text = get_workflow_error_msg(language)

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

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                callback_url,
                json={"task_id": task_id, "status": "done", "result": response_text},
            )
    except httpx.HTTPError as exc:
        logger.warning("Callback failed for task %s: %s", task_id, exc)


@shared_task
def process_message(
    session_id: str,
    conversation_id: str,
    user_id: str,
    message: str,
    callback_url: str,
) -> None:
    # asyncio.run() creates a fresh event loop per task, which is safe for prefork
    # (sync) Celery workers. Do not switch to gevent/eventlet without replacing this.
    asyncio.run(
        _run(
            task_id=current_task.request.id or "",
            session_id=session_id,
            conversation_id=conversation_id,
            user_id=user_id,
            message=message,
            callback_url=callback_url,
        )
    )
