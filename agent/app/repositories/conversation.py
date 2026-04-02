from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.repositories.repositories import AsyncCrudRepository


class ConversationCreate(BaseModel):
    session_id: UUID


class ConversationRepository(AsyncCrudRepository[Conversation, ConversationCreate, BaseModel]):
    def __init__(self) -> None:
        super().__init__(Conversation)

    async def create(self, db: AsyncSession, session_id: UUID) -> Conversation:
        return await super().create(db, ConversationCreate(session_id=session_id))

    async def get_by_session_id(self, db: AsyncSession, session_id: UUID) -> Conversation | None:
        result = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
        return result.scalar_one_or_none()


conversation_repository = ConversationRepository()
