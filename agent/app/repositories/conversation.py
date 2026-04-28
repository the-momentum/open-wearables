from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.repositories.repositories import AsyncCrudRepository
from app.schemas.agent import ConversationStatus


class ConversationCreate(BaseModel):
    user_id: UUID
    status: ConversationStatus = ConversationStatus.ACTIVE
    language: str | None = None
    agent_mode: str | None = None


class ConversationStatusUpdate(BaseModel):
    status: ConversationStatus


class ConversationSummaryUpdate(BaseModel):
    summary: str


class ConversationRepository(AsyncCrudRepository[Conversation, ConversationCreate, ConversationStatusUpdate]):
    def __init__(self) -> None:
        super().__init__(Conversation)

    async def create(  # type: ignore
        self,
        db: AsyncSession,
        user_id: UUID,
        language: str | None = None,
        agent_mode: str | None = None,
    ) -> Conversation:
        return await super().create(db, ConversationCreate(user_id=user_id, language=language, agent_mode=agent_mode))

    async def get_by_id(self, db: AsyncSession, conversation_id: UUID) -> Conversation | None:
        return await super().get(db, conversation_id)

    async def get_active_by_user_id(self, db: AsyncSession, user_id: UUID) -> Conversation | None:
        result = await db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.status == ConversationStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(self, db: AsyncSession, obj: Conversation, status: ConversationStatus) -> Conversation:
        return await super().update(db, obj, ConversationStatusUpdate(status=status))

    async def update_summary(self, db: AsyncSession, obj: Conversation, summary: str) -> Conversation:
        return await super().update(db, obj, ConversationSummaryUpdate(summary=summary))  # type: ignore

    async def mark_inactive_stale(self, db: AsyncSession, max_age: timedelta) -> int:
        """Mark ACTIVE conversations as INACTIVE when updated_at is older than max_age."""
        threshold = datetime.now(tz=timezone.utc) - max_age
        result = await db.execute(
            update(Conversation)
            .where(
                Conversation.status == ConversationStatus.ACTIVE,
                Conversation.updated_at < threshold,
            )
            .values(status=ConversationStatus.INACTIVE)
        )
        await db.commit()
        return result.rowcount  # type: ignore

    async def close_stale(self, db: AsyncSession, inactive_since: timedelta) -> int:
        """Close INACTIVE conversations that have been idle long enough."""
        threshold = datetime.now(tz=timezone.utc) - inactive_since
        result = await db.execute(
            update(Conversation)
            .where(
                Conversation.status == ConversationStatus.INACTIVE,
                Conversation.updated_at < threshold,
            )
            .values(status=ConversationStatus.CLOSED)
        )
        await db.commit()
        return result.rowcount  # type: ignore


conversation_repository = ConversationRepository()
