from collections.abc import Iterable
from datetime import datetime, timezone
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import event as sa_event
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import DbSession
from app.models import DataTypeCoverage
from app.schemas.sync_status import DataTypeKind

# Spans queued on the session, merged and written by _flush_pending on commit.
_PENDING_KEY = "data_type_coverage_pending"

type _SpanKey = tuple[UUID, str, str, DataTypeKind]


class CoverageSpan(NamedTuple):
    """One data type's span within a single write, before it is merged into coverage."""

    user_id: UUID
    provider: str
    data_type: str
    kind: DataTypeKind
    start: datetime
    end: datetime


class DataTypeCoverageRepository:
    """The span of data we hold per user, provider and data type.

    Written from the write paths rather than derived on read: MIN/MAX for one user and
    type is an index endpoint lookup, but there is no cheap way to enumerate which pairs
    exist, and the answer is wanted for every type of every user at once.
    """

    def record(self, db_session: DbSession, spans: Iterable[CoverageSpan]) -> None:
        """Queue spans to widen coverage when the caller's transaction commits.

        Merged on the way in, so the single-record write paths (one workout, one sleep
        session) cost no round trip each and a whole import ends up as one statement.
        Coverage is a min/max, so nothing is lost by deferring it.
        """
        pending: dict[_SpanKey, tuple[datetime, datetime]] = db_session.info.setdefault(_PENDING_KEY, {})
        for span in spans:
            key = (span.user_id, span.provider, span.data_type, span.kind)
            current = pending.get(key)
            pending[key] = (
                (span.start, span.end) if current is None else (min(current[0], span.start), max(current[1], span.end))
            )

    def list_for_user(
        self,
        db_session: DbSession,
        user_id: UUID,
        *,
        provider: str | None = None,
        data_types: Iterable[str] | None = None,
    ) -> list[DataTypeCoverage]:
        stmt = (
            select(DataTypeCoverage)
            .where(DataTypeCoverage.user_id == user_id)
            .order_by(DataTypeCoverage.provider, DataTypeCoverage.data_type)
        )
        if provider is not None:
            stmt = stmt.where(DataTypeCoverage.provider == provider)
        if data_types is not None:
            stmt = stmt.where(DataTypeCoverage.data_type.in_(list(data_types)))
        return list(db_session.execute(stmt).scalars().all())

    def get(self, db_session: DbSession, user_id: UUID, provider: str, data_type: str) -> DataTypeCoverage | None:
        return db_session.get(DataTypeCoverage, (user_id, provider, data_type))


@sa_event.listens_for(Session, "before_commit")
def _flush_pending(session: Session) -> None:
    """Write the queued spans in the committing transaction, so they cannot outlive it."""
    pending: dict[_SpanKey, tuple[datetime, datetime]] = session.info.pop(_PENDING_KEY, {})
    if not pending:
        return

    written_at = datetime.now(timezone.utc)
    stmt = insert(DataTypeCoverage).values(
        [
            {
                "user_id": user_id,
                "provider": provider,
                "data_type": data_type,
                "kind": kind,
                "coverage_start": start,
                "coverage_end": end,
                "last_written_at": written_at,
            }
            for (user_id, provider, data_type, kind), (start, end) in pending.items()
        ]
    )
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "provider", "data_type"],
            set_={
                "coverage_start": func.least(stmt.excluded.coverage_start, DataTypeCoverage.coverage_start),
                "coverage_end": func.greatest(stmt.excluded.coverage_end, DataTypeCoverage.coverage_end),
                "last_written_at": stmt.excluded.last_written_at,
            },
        )
    )


@sa_event.listens_for(Session, "after_rollback")
def _discard_pending(session: Session) -> None:
    """Drop spans whose rows were rolled back. Savepoint rollbacks do not reach here."""
    session.info.pop(_PENDING_KEY, None)


data_type_coverage_repository = DataTypeCoverageRepository()
