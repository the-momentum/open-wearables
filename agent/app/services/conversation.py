import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update

from app.database import AsyncDbSession
from app.models.chat_session import Session
from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories import (
    conversation_repository,
    message_repository,
    session_repository,
)
from app.schemas.agent import ConversationStatus, MessageRole
from app.utils.exceptions import (
    AccessDeniedError,
    ConflictError,
    GoneError,
    ResourceNotFoundError,
    handle_exceptions,
)

logger = logging.getLogger(__name__)


class ConversationService:
    name = "conversation"

    def __init__(self, db: AsyncDbSession) -> None:
        self._db = db

    @handle_exceptions
    async def upsert(
        self,
        user_id: UUID,
        conversation_id: UUID | None = None,
        language: str | None = None,
        agent_mode: str | None = None,
    ) -> tuple[Conversation, Session]:
        """Get or create a conversation+session pair for the user.

        If conversation_id is provided and valid (active conversation owned by this user),
        reuse its active session or open a new one. Otherwise find or create an active
        conversation and open a new session on it.
        """
        if conversation_id is not None:
            conversation = await conversation_repository.get_by_id(self._db, conversation_id)
            if (
                conversation is not None
                and conversation.user_id == user_id
                and conversation.status == ConversationStatus.ACTIVE
            ):
                existing_session = await session_repository.get_active_by_conversation_id(self._db, conversation.id)
                if existing_session is not None:
                    logger.info(f"Reusing session {existing_session.id} on conversation {conversation.id}")
                    return conversation, existing_session

                new_session = await session_repository.create(self._db, conversation.id)
                logger.info(f"Created session {new_session.id} on conversation {conversation.id}")
                return conversation, new_session

        conversation = await conversation_repository.get_active_by_user_id(self._db, user_id)
        if conversation is not None:
            existing_session = await session_repository.get_active_by_conversation_id(self._db, conversation.id)
            if existing_session is not None:
                logger.info(f"Reusing session {existing_session.id} for user {user_id}")
                return conversation, existing_session

            new_session = await session_repository.create(self._db, conversation.id)
            logger.info(f"Created session {new_session.id} on existing conversation {conversation.id}")
            return conversation, new_session

        conversation = await conversation_repository.create(self._db, user_id, language=language, agent_mode=agent_mode)
        new_session = await session_repository.create(self._db, conversation.id)
        logger.info(f"Created conversation {conversation.id} and session {new_session.id} for user {user_id}")
        return conversation, new_session

    @handle_exceptions
    async def get_active(self, conversation_id: UUID, user_id: UUID) -> tuple[Conversation, Session]:
        """Validate and return the active conversation + session."""
        conversation = await conversation_repository.get_by_id(self._db, conversation_id)

        if conversation is None:
            raise ResourceNotFoundError("conversation", conversation_id)

        if conversation.user_id != user_id:
            raise AccessDeniedError("conversation")

        if conversation.status == ConversationStatus.CLOSED:
            raise GoneError("Conversation is closed.")

        session = await session_repository.get_active_by_conversation_id(self._db, conversation_id)

        if session is None:
            raise GoneError("No active session.")

        return conversation, session

    @handle_exceptions
    async def deactivate(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        conversation = await conversation_repository.get_by_id(self._db, conversation_id)

        if conversation is None:
            raise ResourceNotFoundError("conversation", conversation_id)

        if conversation.user_id != user_id:
            raise AccessDeniedError("conversation")

        session = await session_repository.get_active_by_conversation_id(self._db, conversation_id)

        if session is None:
            raise ConflictError("No active session to deactivate.")

        await session_repository.deactivate(self._db, session)
        return conversation

    @handle_exceptions
    async def save_messages(
        self,
        conversation_id: UUID,
        session_id: UUID,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Persist user + assistant message pair and update conversation timestamp atomically."""
        session = await session_repository.get_by_id(self._db, session_id)
        if session is None:
            logger.warning("Session %s not found; messages saved without incrementing request count", session_id)

        # Add both messages without intermediate commits
        self._db.add(
            Message(
                conversation_id=conversation_id,
                session_id=session_id,
                role=MessageRole.USER,
                content=user_message,
            )
        )
        self._db.add(
            Message(
                conversation_id=conversation_id,
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=assistant_message,
            )
        )

        if session is not None:
            await self._db.execute(
                update(Session).where(Session.id == session.id).values(request_count=Session.request_count + 1)
            )

        await self._db.execute(
            update(Conversation).where(Conversation.id == conversation_id).values(updated_at=datetime.now(timezone.utc))
        )

        await self._db.commit()

    @handle_exceptions
    async def build_history(self, conversation: Conversation) -> list[dict[str, str]]:
        """Return message history for the LLM, summarizing if over threshold.

        Imported lazily to avoid circular imports with workflow_engine.
        """
        from app.config import settings

        messages = await message_repository.get_by_conversation_id(self._db, conversation.id)

        if not messages:
            return []

        threshold = settings.history_summary_threshold

        if len(messages) <= threshold:
            return [{"role": m.role.value, "content": m.content} for m in messages]

        old = messages[: len(messages) - threshold]
        recent = messages[-threshold:]

        if conversation.summary is None:
            from app.agent.workflows.agent_workflow import workflow_engine

            old_history = [{"role": m.role.value, "content": m.content} for m in old]
            summary = await workflow_engine.summarize(old_history)
            await conversation_repository.update_summary(self._db, conversation, summary)
            conversation.summary = summary

        recent_history = [{"role": m.role.value, "content": m.content} for m in recent]
        return [{"role": "system", "content": f"Earlier conversation summary: {conversation.summary}"}] + recent_history
