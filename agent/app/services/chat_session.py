import logging
from uuid import UUID

from fastapi import HTTPException, status

from app.database import AsyncDbSession
from app.models.chat_session import ChatSession
from app.models.conversation import Conversation
from app.repositories import (
    chat_session_repository,
    conversation_repository,
    message_repository,
)
from app.schemas.agent import MessageRole

logger = logging.getLogger(__name__)


class ChatSessionService:
    def __init__(self, db: AsyncDbSession) -> None:
        self._db = db

    async def upsert_session(
        self, user_id: UUID, session_id: UUID | None = None
    ) -> tuple[ChatSession, Conversation]:
        if session_id is not None:
            session = await chat_session_repository.get_by_id(self._db, session_id)
            if session is not None and session.user_id == user_id and session.active:
                conversation = await conversation_repository.get_by_session_id(self._db, session.id)
                if conversation is None:
                    conversation = await conversation_repository.create(self._db, session.id)
                logger.info(f"Reusing session {session.id} for user {user_id}")
                return session, conversation

        session = await chat_session_repository.get_active_by_user_id(self._db, user_id)
        if session is not None:
            conversation = await conversation_repository.get_by_session_id(self._db, session.id)
            if conversation is None:
                conversation = await conversation_repository.create(self._db, session.id)
            logger.info(f"Reusing session {session.id} for user {user_id}")
            return session, conversation

        session = await chat_session_repository.create(self._db, user_id)
        conversation = await conversation_repository.create(self._db, session.id)
        logger.info(f"Created session {session.id} for user {user_id}")
        return session, conversation

    async def deactivate_session(self, session_id: UUID, user_id: UUID) -> ChatSession:
        session = await chat_session_repository.get_by_id(self._db, session_id)

        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

        if session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        if not session.active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session already inactive.")

        return await chat_session_repository.deactivate(self._db, session)

    async def get_active_session(self, session_id: UUID, user_id: UUID) -> tuple[ChatSession, Conversation]:
        session = await chat_session_repository.get_by_id(self._db, session_id)

        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

        if session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        if not session.active:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is inactive.")

        conversation = await conversation_repository.get_by_session_id(self._db, session.id)
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

        return session, conversation

    async def save_messages(
        self,
        conversation_id: UUID,
        user_message: str,
        assistant_message: str,
        session: ChatSession,
    ) -> None:
        #TODO: consider ACID transaction
        await message_repository.create(self._db, conversation_id, MessageRole.USER, user_message)
        await message_repository.create(self._db, conversation_id, MessageRole.ASSISTANT, assistant_message)
        await chat_session_repository.increment_request_count(self._db, session)
