from collections.abc import Iterable
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import DataTypeCoverage
from app.schemas.data_type_coverage import CoverageSpan
from app.schemas.sync_status import DataTypeKind

type _SpanKey = tuple[UUID, str, str, DataTypeKind]
type EventKey = tuple[UUID, str, str]
type _CoverageKey = tuple[UUID, str, str, str]

_TRIM_BATCH_SIZE = 5_000

_KEYS = """
    SELECT * FROM unnest(CAST(:user_ids AS uuid[]), CAST(:providers AS text[]), CAST(:data_types AS text[]))
        AS k(user_id, provider, data_type)
"""
_SAME_KEY = "(c.user_id, c.provider, c.data_type, c.kind) = (s.user_id, s.provider, s.data_type, s.kind)"

# Locked first and in key order, as record() upserts, so a write committing meanwhile is
# either seen by the next statement or widens its result afterwards.
_LOCK_KEYS = text(f"""
    SELECT 1 FROM data_type_coverage c JOIN ({_KEYS}) k USING (user_id, provider, data_type)
    WHERE c.kind = :event
    ORDER BY c.user_id, c.provider, c.data_type, c.kind
    FOR UPDATE OF c
""")
_REFRESH_EVENTS = text(f"""
    WITH spans AS (
        SELECT k.user_id, k.provider, k.data_type, CAST(:event AS varchar) AS kind,
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
# The cutoff day starts in the session's time zone, where retention compares recorded_at::date.
_NEXT_SERIES_KEYS = text("""
    SELECT user_id, provider, data_type, kind FROM data_type_coverage
    WHERE (user_id, provider, data_type, kind) > (:user_id, :provider, :data_type, :kind)
    ORDER BY user_id, provider, data_type, kind
    LIMIT :batch_size
""")
_TRIM_SERIES = text(f"""
    WITH bound AS (SELECT CAST(:cutoff AS date)::timestamptz AS cutoff),
    s AS (
        SELECT user_id, provider, data_type, kind, coverage_end, bound.cutoff
        FROM data_type_coverage, bound
        WHERE (user_id, provider, data_type, kind) > (:after_user_id, :after_provider, :after_data_type, :after_kind)
          AND (user_id, provider, data_type, kind) <= (:upto_user_id, :upto_provider, :upto_data_type, :upto_kind)
          AND kind = :series AND coverage_start < bound.cutoff
        ORDER BY user_id, provider, data_type, kind
        FOR UPDATE OF data_type_coverage
    ), emptied AS (
        DELETE FROM data_type_coverage c USING s WHERE {_SAME_KEY} AND s.coverage_end < s.cutoff
    )
    UPDATE data_type_coverage c SET coverage_start = s.cutoff
    FROM s
    WHERE {_SAME_KEY} AND s.coverage_end >= s.cutoff
""")


_BACKFILL_BATCH_SIZE = 500

_NEXT_SOURCES = text("""
    SELECT id FROM data_source
    WHERE id > :after
    ORDER BY id
    LIMIT :batch_size
""")
# Everything that narrows coverage takes this lock exclusively, the backfill shared per batch.
# A narrowing then waits for any batch that read the data before it was removed, and a batch
# starting later reads it already gone, so the backfill cannot widen back what was removed.
_NARROWING = "hashtextextended('data_type_coverage:narrowing', 0)"
_LOCK_FOR_NARROWING = text(f"SELECT pg_advisory_xact_lock({_NARROWING})")
_LOCK_FOR_BACKFILL = text(f"SELECT pg_advisory_xact_lock_shared({_NARROWING})")


def _pair_spans(table: str, at: str) -> str:
    """Span per (data source, series type) in one table, for the sources in (:after, :upto]."""
    return f"""
        SELECT p.data_source_id, p.series_type_definition_id,
            (SELECT min(t.{at}) FROM {table} t
             WHERE t.data_source_id = p.data_source_id
               AND t.series_type_definition_id = p.series_type_definition_id) AS first_at,
            (SELECT max(t.{at}) FROM {table} t
             WHERE t.data_source_id = p.data_source_id
               AND t.series_type_definition_id = p.series_type_definition_id) AS last_at
        FROM (
            WITH RECURSIVE pairs AS (
                (
                    SELECT data_source_id, series_type_definition_id FROM {table}
                    WHERE data_source_id > :after AND data_source_id <= :upto
                    ORDER BY data_source_id, series_type_definition_id
                    LIMIT 1
                )
                UNION ALL
                SELECT next.data_source_id, next.series_type_definition_id
                FROM pairs
                CROSS JOIN LATERAL (
                    SELECT t.data_source_id, t.series_type_definition_id FROM {table} t
                    WHERE (t.data_source_id, t.series_type_definition_id)
                          > (pairs.data_source_id, pairs.series_type_definition_id)
                      AND t.data_source_id <= :upto
                    ORDER BY t.data_source_id, t.series_type_definition_id
                    LIMIT 1
                ) AS next
            )
            SELECT * FROM pairs
        ) p
    """


_HELD_SERIES_SPANS = f"""
    SELECT ds.user_id, ds.provider, std.code AS data_type, CAST(:series AS varchar) AS kind,
           min(s.first_at) AS coverage_start, max(s.last_at) AS coverage_end
    FROM (
        {_pair_spans("data_point_series", "recorded_at")}
        UNION ALL
        {_pair_spans("data_point_series_archive", "bucket_start_at")}
    ) s
    JOIN data_source ds ON ds.id = s.data_source_id
    JOIN series_type_definition std ON std.id = s.series_type_definition_id
    GROUP BY ds.user_id, ds.provider, std.code
"""

_HELD_EVENT_SPANS = """
    SELECT ds.user_id, ds.provider, er.category AS data_type, CAST(:event AS varchar) AS kind,
           min(er.start_datetime) AS coverage_start, max(er.end_datetime) AS coverage_end
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE er.data_source_id > :after AND er.data_source_id <= :upto
      AND er.category IS NOT NULL AND er.category <> ''
    GROUP BY ds.user_id, ds.provider, er.category
"""


def _widen_with(spans: str) -> str:
    return f"""
        INSERT INTO data_type_coverage
            (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)
        SELECT user_id, provider, data_type, kind, coverage_start, coverage_end, coverage_end
        FROM ({spans}) spans
        ORDER BY user_id, provider, data_type, kind
        ON CONFLICT (user_id, provider, data_type, kind) DO UPDATE SET
            coverage_start = LEAST(EXCLUDED.coverage_start, data_type_coverage.coverage_start),
            coverage_end = GREATEST(EXCLUDED.coverage_end, data_type_coverage.coverage_end),
            last_written_at = GREATEST(EXCLUDED.last_written_at, data_type_coverage.last_written_at)
    """


_BACKFILL_WRITES = {
    DataTypeKind.SERIES: text(_widen_with(_HELD_SERIES_SPANS)),
    DataTypeKind.EVENT: text(_widen_with(_HELD_EVENT_SPANS)),
}
_BACKFILL_COUNTS = {
    DataTypeKind.SERIES: text(f"SELECT count(*) FROM ({_HELD_SERIES_SPANS}) spans"),
    DataTypeKind.EVENT: text(f"SELECT count(*) FROM ({_HELD_EVENT_SPANS}) spans"),
}


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
                index_elements=["user_id", "provider", "data_type", "kind"],
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
        params = {**_key_params(unique), "event": DataTypeKind.EVENT}
        db_session.execute(_LOCK_FOR_NARROWING)
        db_session.execute(_LOCK_KEYS, params)
        db_session.execute(_REFRESH_EVENTS, params)

    def delete_for_provider(self, db_session: DbSession, user_id: UUID, provider: str) -> None:
        """Forget everything held for a user's provider, whose data is being deleted. Does not commit."""
        db_session.execute(_LOCK_FOR_NARROWING)
        db_session.execute(
            delete(DataTypeCoverage).where(DataTypeCoverage.user_id == user_id, DataTypeCoverage.provider == provider)
        )

    def trim_series_before(self, db_session: DbSession, cutoff: date) -> None:
        """Move series spans up to a retention cutoff, once everything older is deleted.

        A span that ended before the cutoff is gone. Others start at the cutoff, which is at
        or before their first sample left. Commits per batch.
        """
        after: _CoverageKey = (UUID(int=0), "", "", "")
        while keys := db_session.execute(
            _NEXT_SERIES_KEYS,
            {
                "user_id": after[0],
                "provider": after[1],
                "data_type": after[2],
                "kind": after[3],
                "batch_size": _TRIM_BATCH_SIZE,
            },
        ).all():
            upto = keys[-1].tuple()
            db_session.execute(_LOCK_FOR_NARROWING)
            db_session.execute(
                _TRIM_SERIES,
                {
                    "after_user_id": after[0],
                    "after_provider": after[1],
                    "after_data_type": after[2],
                    "after_kind": after[3],
                    "upto_user_id": upto[0],
                    "upto_provider": upto[1],
                    "upto_data_type": upto[2],
                    "upto_kind": upto[3],
                    "cutoff": cutoff,
                    "series": DataTypeKind.SERIES,
                },
            )
            db_session.commit()
            after = upto

    def backfill_from_held_data(self, db_session: DbSession, *, dry_run: bool) -> dict[DataTypeKind, int]:
        """Widen coverage to the series, archive and event rows already held, per batch of data sources.

        For data written before coverage existed. Only widens, so it never undoes what the
        write paths recorded meanwhile. Returns the spans recorded (or, in a dry run, found)
        per kind, one per type and batch. Commits per batch.
        """
        found = {DataTypeKind.SERIES: 0, DataTypeKind.EVENT: 0}
        after = UUID(int=0)
        while sources := (
            db_session.execute(_NEXT_SOURCES, {"after": after, "batch_size": _BACKFILL_BATCH_SIZE}).scalars().all()
        ):
            params = {"after": after, "upto": sources[-1], "series": DataTypeKind.SERIES, "event": DataTypeKind.EVENT}
            db_session.execute(_LOCK_FOR_BACKFILL)
            for kind in found:
                if dry_run:
                    found[kind] += db_session.execute(_BACKFILL_COUNTS[kind], params).scalar() or 0
                else:
                    found[kind] += db_session.execute(_BACKFILL_WRITES[kind], params).rowcount  # ty: ignore[unresolved-attribute]
            db_session.commit()
            after = sources[-1]
        return found

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
            .order_by(DataTypeCoverage.provider, DataTypeCoverage.data_type, DataTypeCoverage.kind)
        )
        if provider is not None:
            stmt = stmt.where(DataTypeCoverage.provider == provider)
        if data_types is not None:
            stmt = stmt.where(DataTypeCoverage.data_type.in_(list(data_types)))
        return list(db_session.execute(stmt).scalars().all())

    def get(
        self, db_session: DbSession, user_id: UUID, provider: str, data_type: str, kind: DataTypeKind
    ) -> DataTypeCoverage | None:
        return db_session.get(DataTypeCoverage, (user_id, provider, data_type, kind))


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
