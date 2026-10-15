#!/usr/bin/env python3
"""Backfill data_type_coverage from the data already in the database.

Coverage is maintained going forward by the write paths (DataPointSeriesRepository and
EventRecordRepository record spans in the same transaction as the data). This fills in
everything written before that existed. Without it, coverage starts at the first write after
the deploy, so a user with years of history reports it as starting that day.

Series coverage spans both the live table and the archive, where archival moves old samples
as daily aggregates: on an instance that archives, the oldest data is only there. An archive
bucket counts from the start of its day.

PERFORMANCE: the series pass never scans data_point_series or its archive. Per batch of data
sources it enumerates the distinct (data_source_id, series_type_definition_id) pairs with a
loose index scan over the unique index of each table, then takes MIN/MAX per pair, which
with both leading columns fixed are index endpoint lookups. Cost follows the number of
pairs, not the number of samples. The event pass aggregates one batch of data sources
through ix_event_record_source_category.

last_written_at is set to coverage_end. We do not know when historical rows were actually
written, and reading created_at would force a heap fetch per row; the approximation only
affects "when did we last hear about this type", which corrects itself on the next write.

SAFETY: every write is an upsert that only ever widens the stored range and moves
last_written_at forward, so a concurrent live sync cannot be clobbered by a stale value
from this script. Runs once per instance (``data_migration``), committing per batch of
data sources.

Usage (inside Docker), with --dry-run to count the rows it would write:
    docker compose exec app uv run python scripts/data_migrations/backfill_data_type_coverage.py
"""

import argparse
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.schemas.sync_status import DataTypeKind
from app.services.data_migration_service import data_migration_service

_BATCH_SIZE = 500

_NEXT_SOURCES = text("""
    SELECT id FROM data_source
    WHERE id > :after
    ORDER BY id
    LIMIT :batch_size
""")


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


_SERIES_SPANS = f"""
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

_EVENT_SPANS = """
    SELECT ds.user_id, ds.provider, er.category AS data_type, CAST(:event AS varchar) AS kind,
           min(er.start_datetime) AS coverage_start, max(er.end_datetime) AS coverage_end
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE er.data_source_id > :after AND er.data_source_id <= :upto
      AND er.category IS NOT NULL AND er.category <> ''
    GROUP BY ds.user_id, ds.provider, er.category
"""


def _upsert(spans: str) -> str:
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


_WRITES = {
    DataTypeKind.SERIES: text(_upsert(_SERIES_SPANS)),
    DataTypeKind.EVENT: text(_upsert(_EVENT_SPANS)),
}
_COUNTS = {
    DataTypeKind.SERIES: text(f"SELECT count(*) FROM ({_SERIES_SPANS}) spans"),
    DataTypeKind.EVENT: text(f"SELECT count(*) FROM ({_EVENT_SPANS}) spans"),
}


def backfill_data_type_coverage(db: Session, *, dry_run: bool) -> dict[DataTypeKind, int]:
    """Spans recorded (or, in a dry run, found) per kind, one per type and batch. Commits per batch."""
    found = dict.fromkeys(_WRITES, 0)
    after = UUID(int=0)
    while sources := db.execute(_NEXT_SOURCES, {"after": after, "batch_size": _BATCH_SIZE}).scalars().all():
        params = {"after": after, "upto": sources[-1], "series": DataTypeKind.SERIES, "event": DataTypeKind.EVENT}
        for kind in found:
            if dry_run:
                found[kind] += db.execute(_COUNTS[kind], params).scalar() or 0
            else:
                found[kind] += db.execute(_WRITES[kind], params).rowcount  # ty: ignore[unresolved-attribute]
        db.commit()
        after = sources[-1]

    verb = "Would record" if dry_run else "Recorded"
    for kind, spans in found.items():
        print(f"{verb} {spans} {kind} span(s).")
    if dry_run:
        print("\nDry run — no changes made.")
    return found


def _migrate(db: Session, dry_run: bool) -> bool:
    backfill_data_type_coverage(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(db, "backfill_data_type_coverage", lambda: _migrate(db, dry_run), dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count the rows it would write without writing them")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
