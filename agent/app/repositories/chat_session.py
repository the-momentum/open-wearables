from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.repositories.repositories import AsyncCrudRepository


class ChatSessionCreate(BaseModel):
    user_id: UUID


class ChatSessionDeactivate(BaseModel):
    active: bool = False


class ChatSessionRepository(AsyncCrudRepository[ChatSession, ChatSessionCreate, ChatSessionDeactivate]):
    def __init__(self) -> None:
        super().__init__(ChatSession)

    async def create(self, db: AsyncSession, user_id: UUID) -> ChatSession:
        return await super().create(db, ChatSessionCreate(user_id=user_id))

    async def get_by_id(self, db: AsyncSession, session_id: UUID) -> ChatSession | None:
        return await super().get(db, session_id)

    async def get_active_by_user_id(self, db: AsyncSession, user_id: UUID) -> ChatSession | None:
        result = await db.execute(
            select(ChatSession).where(ChatSession.user_id == user_id, ChatSession.active.is_(True))
        )
        return result.scalar_one_or_none()

    async def deactivate(self, db: AsyncSession, obj: ChatSession) -> ChatSession:
        return await super().update(db, obj, ChatSessionDeactivate())

    async def increment_request_count(self, db: AsyncSession, obj: ChatSession) -> None:
        obj.request_count += 1
        db.add(obj)
        await db.commit()

    async def deactivate_expired(self, db: AsyncSession, max_age: timedelta) -> int:
        threshold = datetime.now(tz=timezone.utc) - max_age
        result = await db.execute(
            update(ChatSession)
            .where(ChatSession.active.is_(True), ChatSession.created_at < threshold)
            .values(active=False)
        )
        await db.commit()
        return result.rowcount


chat_session_repository = ChatSessionRepository()
