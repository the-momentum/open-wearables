from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import DataTypeCoverage
from app.schemas.data_type_coverage import CoverageSpan
from app.schemas.sync_status import DataTypeKind

type _SpanKey = tuple[UUID, str, str, DataTypeKind]
type EventKey = tuple[UUID, str, str]

_TRIM_BATCH_SIZE = 5_000

_KEYS = """
    SELECT * FROM unnest(CAST(:user_ids AS uuid[]), CAST(:providers AS text[]), CAST(:data_types AS text[]))
        AS k(user_id, provider, data_type)
"""
_SAME_KEY = "(c.user_id, c.provider, c.data_type) = (s.user_id, s.provider, s.data_type)"

# Locked first and in key order, as record() upserts, so a write committing meanwhile is
# either seen by the next statement or widens its result afterwards.
_LOCK_KEYS = text(f"""
    SELECT 1 FROM data_type_coverage c JOIN ({_KEYS}) k USING (user_id, provider, data_type)
    ORDER BY c.user_id, c.provider, c.data_type
    FOR UPDATE OF c
""")
_REFRESH_EVENTS = text(f"""
    WITH spans AS (
        SELECT k.user_id, k.provider, k.data_type,
               min(er.start_datetime) AS first_start, max(er.end_datetime) AS last_end
        FROM ({_KEYS}) k
        LEFT JOIN data_source ds ON ds.user_id = k.user_id AND ds.provider = k.provider
        LEFT JOIN event_record er ON er.data_source_id = ds.id AND er.category = k.data_type
        GROUP BY k.user_id, k.provider, k.data_type
    ), emptied AS (
        DELETE FROM data_type_coverage c USING spans s WHERE {_SAME_KEY} AND s.first_start IS NULL
    )
    UPDATE data_type_coverage c SET coverage_start = s.first_start, coverage_end = s.last_end
    FROM spans s
    WHERE {_SAME_KEY} AND s.first_start IS NOT NULL
""")

# Walks the primary key in ranges, so each batch is an index range scan and the trim one pass.
_NEXT_SERIES_KEYS = text("""
    SELECT user_id, provider, data_type FROM data_type_coverage
    WHERE (user_id, provider, data_type) > (:user_id, :provider, :data_type)
    ORDER BY user_id, provider, data_type
    LIMIT :batch_size
""")
_TRIM_SERIES = text(f"""
    WITH s AS (
        SELECT user_id, provider, data_type, coverage_end FROM data_type_coverage
        WHERE (user_id, provider, data_type) > (:after_user_id, :after_provider, :after_data_type)
          AND (user_id, provider, data_type) <= (:upto_user_id, :upto_provider, :upto_data_type)
          AND kind = :series AND coverage_start < :cutoff
        ORDER BY user_id, provider, data_type
        FOR UPDATE
    ), emptied AS (
        DELETE FROM data_type_coverage c USING s WHERE {_SAME_KEY} AND s.coverage_end < :cutoff
    )
    UPDATE data_type_coverage c SET coverage_start = :cutoff
    FROM s
    WHERE {_SAME_KEY} AND s.coverage_end >= :cutoff
""")


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
            for (user_id, provider, data_type, kind), (start, end) in sorted(_merge(spans).items())
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

    def refresh_events(self, db_session: DbSession, keys: Iterable[EventKey]) -> None:
        """Recompute these (user, provider, category) spans from the records left, after some were removed.

        A category with no records left loses its row. Reads one user's records of each
        category through ix_event_record_source_category. Does not commit.
        """
        unique = sorted(set(keys))
        if not unique:
            return
        params = _key_params(unique)
        db_session.execute(_LOCK_KEYS, params)
        db_session.execute(_REFRESH_EVENTS, params)

    def delete_for_provider(self, db_session: DbSession, user_id: UUID, provider: str) -> None:
        """Forget everything held for a user's provider, whose data is being deleted. Does not commit."""
        db_session.execute(
            delete(DataTypeCoverage).where(DataTypeCoverage.user_id == user_id, DataTypeCoverage.provider == provider)
        )

    def trim_series_before(self, db_session: DbSession, cutoff: datetime) -> None:
        """Move series spans up to a retention cutoff, once everything older is deleted.

        A span that ended before the cutoff is gone. Others start at the cutoff, which is at
        or before their first sample left. Commits per batch.
        """
        after: EventKey = (UUID(int=0), "", "")
        while keys := db_session.execute(
            _NEXT_SERIES_KEYS,
            {"user_id": after[0], "provider": after[1], "data_type": after[2], "batch_size": _TRIM_BATCH_SIZE},
        ).all():
            upto = keys[-1].tuple()
            db_session.execute(
                _TRIM_SERIES,
                {
                    "after_user_id": after[0],
                    "after_provider": after[1],
                    "after_data_type": after[2],
                    "upto_user_id": upto[0],
                    "upto_provider": upto[1],
                    "upto_data_type": upto[2],
                    "cutoff": cutoff,
                    "series": DataTypeKind.SERIES,
                },
            )
            db_session.commit()
            after = upto

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


def _key_params(keys: list[EventKey]) -> dict[str, list]:
    user_ids, providers, data_types = (list(column) for column in zip(*keys, strict=True))
    return {"user_ids": user_ids, "providers": providers, "data_types": data_types}


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
