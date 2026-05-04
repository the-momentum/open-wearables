from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import Session
from app.repositories.repositories import AsyncCrudRepository


class SessionCreate(BaseModel):
    conversation_id: UUID


class SessionDeactivate(BaseModel):
    active: bool = False


class SessionRepository(AsyncCrudRepository[Session, SessionCreate, SessionDeactivate]):
    def __init__(self) -> None:
        super().__init__(Session)

    async def create(self, db: AsyncSession, conversation_id: UUID) -> Session:  # type: ignore
        return await super().create(db, SessionCreate(conversation_id=conversation_id))

    async def get_by_id(self, db: AsyncSession, session_id: UUID) -> Session | None:
        return await super().get(db, session_id)

    async def get_active_by_conversation_id(self, db: AsyncSession, conversation_id: UUID) -> Session | None:
        result = await db.execute(
            select(Session).where(
                Session.conversation_id == conversation_id,
                Session.active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def deactivate(self, db: AsyncSession, obj: Session) -> Session:
        return await super().update(db, obj, SessionDeactivate())

    async def increment_request_count(self, db: AsyncSession, obj: Session) -> None:
        await db.execute(update(Session).where(Session.id == obj.id).values(request_count=Session.request_count + 1))
        await db.commit()

    async def deactivate_expired(self, db: AsyncSession, max_age: timedelta) -> int:
        threshold = datetime.now(tz=timezone.utc) - max_age
        result = await db.execute(
            update(Session).where(Session.active.is_(True), Session.updated_at < threshold).values(active=False)
        )
        await db.commit()
        return result.rowcount  # type: ignore


session_repository = SessionRepository()
