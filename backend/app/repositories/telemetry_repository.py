from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import distinct, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.database import DbSession
from app.models import (
    DataPointSeries,
    DataSource,
    EventRecord,
    ProviderSetting,
    TelemetryState,
    User,
    UserConnection,
)
from app.schemas.auth import ConnectionStatus

_ACTIVE = UserConnection.status == ConnectionStatus.ACTIVE


class TelemetryRepository:
    """Data access for anonymous usage telemetry: the singleton state row and aggregate counts."""

    def get_or_create_state(self, db: DbSession) -> TelemetryState:
        state = db.get(TelemetryState, 1)
        if state is not None:
            return state

        state = TelemetryState(
            id=1,
            instance_id=uuid4(),
            created_at=datetime.now(timezone.utc),
            last_sent_at=None,
        )
        db.add(state)
        try:
            db.commit()
        except IntegrityError:
            # Another worker created the row concurrently - use theirs.
            db.rollback()
            state = db.get(TelemetryState, 1)
            if state is None:  # pragma: no cover - only on DB failure
                raise
        return state

    def claim_send(self, db: DbSession, interval: timedelta) -> datetime | None:
        """Reserve the next delivery, or return None when the last one is within `interval`.

        A conditional UPDATE, committed before the request goes out, so that
        concurrent callers (several workers enqueueing the startup ping, or a
        startup ping racing the hourly beat) cannot all pass the check: the
        row lock makes the second UPDATE re-check against the first one's
        timestamp and match nothing.
        """
        now = datetime.now(timezone.utc)
        claimed = db.execute(
            update(TelemetryState)
            .where(
                TelemetryState.id == 1,
                or_(TelemetryState.last_sent_at.is_(None), TelemetryState.last_sent_at <= now - interval),
            )
            .values(last_sent_at=now)
            .returning(TelemetryState.id)
        ).scalar_one_or_none()
        db.commit()
        return now if claimed is not None else None

    def release_claim(self, db: DbSession, claimed_at: datetime, previous_sent_at: datetime | None) -> None:
        """Undo a claim, restoring the previous value only if no other caller has claimed since."""
        db.rollback()
        db.execute(
            update(TelemetryState)
            .where(TelemetryState.id == 1, TelemetryState.last_sent_at == claimed_at)
            .values(last_sent_at=previous_sent_at)
        )
        db.commit()

    def count_users(self, db: DbSession) -> int:
        return db.scalar(select(func.count()).select_from(User)) or 0

    def count_users_with_active_connection(self, db: DbSession) -> int:
        return db.scalar(select(func.count(distinct(UserConnection.user_id))).where(_ACTIVE)) or 0

    def count_inactive_connections(self, db: DbSession) -> int:
        return db.scalar(select(func.count()).select_from(UserConnection).where(~_ACTIVE)) or 0

    def count_active_connections_by_provider(self, db: DbSession) -> dict[str, int]:
        rows = db.execute(
            select(UserConnection.provider, func.count()).where(_ACTIVE).group_by(UserConnection.provider)
        )
        return {provider: count for provider, count in rows}

    def count_data_points_by_provider(self, db: DbSession) -> dict[str, int]:
        return self._count_by_provider(db, DataPointSeries)

    def count_events_by_provider(self, db: DbSession, category: str) -> dict[str, int]:
        return self._count_by_provider(db, EventRecord, category=category)

    def get_provider_settings(self, db: DbSession) -> list[ProviderSetting]:
        return list(db.scalars(select(ProviderSetting)).all())

    @staticmethod
    def _count_by_provider(
        db: DbSession,
        model: type[DataPointSeries] | type[EventRecord],
        category: str | None = None,
    ) -> dict[str, int]:
        query = (
            select(DataSource.provider, func.count())
            .select_from(model)
            .join(DataSource, model.data_source_id == DataSource.id)
            .group_by(DataSource.provider)
        )
        if category is not None:
            query = query.where(EventRecord.category == category)
        return {
            provider.value if hasattr(provider, "value") else provider: count
            for provider, count in db.execute(query).all()
        }
