from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.repositories.repositories import AsyncCrudRepository
from app.schemas.agent import MessageRole
from app.schemas.message import MessageCreate


class MessageRepository(AsyncCrudRepository[Message, MessageCreate, MessageCreate]):
    def __init__(self) -> None:
        super().__init__(Message)

    async def create(self, db: AsyncSession, conversation_id: UUID, role: MessageRole, content: str) -> Message:
        return await super().create(
            db,
            MessageCreate(conversation_id=conversation_id, role=role, content=content),
        )


message_repository = MessageRepository()
