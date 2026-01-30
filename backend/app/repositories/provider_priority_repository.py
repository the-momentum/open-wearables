from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import asc, func
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import ProviderPriority
from app.repositories.repositories import CrudRepository
from app.schemas.oauth import ProviderName
from app.schemas.provider_priority import (
    DEFAULT_PROVIDER_PRIORITY,
    ProviderPriorityCreate,
    ProviderPriorityUpdate,
)


class ProviderPriorityRepository(
    CrudRepository[ProviderPriority, ProviderPriorityCreate, ProviderPriorityUpdate],
):
    def __init__(self, model: type[ProviderPriority] = ProviderPriority):
        super().__init__(model)

    def get_all_ordered(self, db_session: DbSession) -> list[ProviderPriority]:
        return db_session.query(self.model).order_by(asc(self.model.priority)).all()

    def get_by_provider(self, db_session: DbSession, provider: ProviderName) -> ProviderPriority | None:
        return db_session.query(self.model).filter(self.model.provider == provider).one_or_none()

    def get_priority_order(self, db_session: DbSession) -> dict[ProviderName, int]:
        priorities = self.get_all_ordered(db_session)
        return {p.provider: p.priority for p in priorities}

    def get_next_priority(self, db_session: DbSession) -> int:
        """Get the next available priority number."""
        max_priority = db_session.query(func.max(self.model.priority)).scalar()
        return (max_priority or 0) + 1

    def ensure_provider_exists(self, db_session: DbSession, provider: ProviderName) -> ProviderPriority:
        """Ensure provider has a priority entry, creating with default or next priority if not."""
        existing = self.get_by_provider(db_session, provider)
        if existing:
            return existing

        priority = DEFAULT_PROVIDER_PRIORITY.get(provider, self.get_next_priority(db_session))
        return self.upsert(db_session, provider, priority)

    def upsert(
        self,
        db_session: DbSession,
        provider: ProviderName,
        priority: int,
    ) -> ProviderPriority:
        now = datetime.now(timezone.utc)
        stmt = (
            insert(self.model)
            .values(
                id=uuid4(),
                provider=provider,
                priority=priority,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["provider"],
                set_={"priority": priority, "updated_at": now},
            )
        )
        db_session.execute(stmt)
        db_session.flush()
        return self.get_by_provider(db_session, provider)  # type: ignore

    def bulk_update(
        self,
        db_session: DbSession,
        priorities: list[tuple[ProviderName, int]],
    ) -> list[ProviderPriority]:
        now = datetime.now(timezone.utc)
        for provider, priority in priorities:
            stmt = (
                insert(self.model)
                .values(
                    id=uuid4(),
                    provider=provider,
                    priority=priority,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["provider"],
                    set_={"priority": priority, "updated_at": now},
                )
            )
            db_session.execute(stmt)
        db_session.flush()
        return self.get_all_ordered(db_session)
