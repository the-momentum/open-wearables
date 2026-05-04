from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.repositories.repositories import AsyncCrudRepository
from app.schemas.agent import MessageRole
from app.schemas.message import MessageCreate


class MessageRepository(AsyncCrudRepository[Message, MessageCreate, MessageCreate]):
    def __init__(self) -> None:
        super().__init__(Message)

    async def create(  # type: ignore
        self,
        db: AsyncSession,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        session_id: UUID | None = None,
    ) -> Message:
        return await super().create(
            db,
            MessageCreate(
                conversation_id=conversation_id,
                session_id=session_id,
                role=role,
                content=content,
            ),
        )

    async def get_by_conversation_id(
        self, db: AsyncSession, conversation_id: UUID, limit: int | None = None
    ) -> list[Message]:
        query = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
        if limit is not None:
            query = query.limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())


message_repository = MessageRepository()
