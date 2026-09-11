from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import DataTypeCoverage
from app.schemas.data_type_coverage import CoverageSpan
from app.schemas.sync_status import DataTypeKind

type _SpanKey = tuple[UUID, str, str, DataTypeKind]


class DataTypeCoverageRepository:
    """The span of data we hold per user, provider and data type.

    Written from the write paths rather than derived on read: MIN/MAX for one user and
    type is an index endpoint lookup, but there is no cheap way to enumerate which pairs
    exist, and the answer is wanted for every type of every user at once.
    """

    def record(self, db_session: DbSession, spans: Iterable[CoverageSpan]) -> None:
        """Widen coverage to include these spans, in the caller's transaction.

        Ranges only ever widen, so batches of one type arriving out of order still add up
        to a single span. Runs in the caller's transaction and does not commit, so a
        rollback takes the coverage with the rows it described.
        """
        rows = [
            {
                "user_id": user_id,
                "provider": provider,
                "data_type": data_type,
                "kind": kind,
                "coverage_start": start,
                "coverage_end": end,
                "last_written_at": datetime.now(timezone.utc),
            }
            for (user_id, provider, data_type, kind), (start, end) in _merge(spans).items()
        ]
        if not rows:
            return

        stmt = insert(DataTypeCoverage).values(rows)
        db_session.execute(
            stmt.on_conflict_do_update(
                index_elements=["user_id", "provider", "data_type"],
                set_={
                    "coverage_start": func.least(stmt.excluded.coverage_start, DataTypeCoverage.coverage_start),
                    "coverage_end": func.greatest(stmt.excluded.coverage_end, DataTypeCoverage.coverage_end),
                    "last_written_at": stmt.excluded.last_written_at,
                },
            )
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


def _merge(spans: Iterable[CoverageSpan]) -> dict[_SpanKey, tuple[datetime, datetime]]:
    """Collapse spans to one per key: Postgres cannot upsert the same key twice per statement."""
    merged: dict[_SpanKey, tuple[datetime, datetime]] = {}
    for span in spans:
        key = (span.user_id, span.provider, span.data_type, span.kind)
        current = merged.get(key)
        merged[key] = (
            (span.start, span.end) if current is None else (min(current[0], span.start), max(current[1], span.end))
        )
    return merged


data_type_coverage_repository = DataTypeCoverageRepository()
