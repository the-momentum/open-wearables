#!/usr/bin/env python3
"""Backfill data_type_coverage from the data already in the database.

Coverage is maintained going forward by the write paths (DataPointSeriesRepository and
EventRecordRepository queue spans that are upserted on commit). This fills in everything
written before that existed.

PERFORMANCE: the series pass never scans data_point_series. It enumerates the distinct
(data_source_id, series_type_definition_id) pairs with a loose index scan over
uq_data_point_series_source_type_time, then takes MIN/MAX per pair, which with both
leading columns fixed are index endpoint lookups with no heap fetches. Cost follows the
number of pairs, not the number of samples. The event pass is a plain aggregate --
event_record is small enough that it does not need the same treatment.

last_written_at is set to coverage_end. We do not know when historical rows were actually
written, and reading created_at would force a heap fetch per row; the approximation only
affects "when did we last hear about this type", which corrects itself on the next write.

SAFETY + IDEMPOTENCY: every write is an upsert that only ever widens the stored range and
moves last_written_at forward, so re-runs are no-ops and a concurrent live sync cannot be
clobbered by a stale value from this script.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_data_type_coverage.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_data_type_coverage.py
"""

import argparse
import os
import sys
from typing import LiteralString

import psycopg
from psycopg.conninfo import make_conninfo

# Loose index scan: one index probe per distinct pair, rather than a scan of every row.
SERIES_SPANS_SQL = """
WITH RECURSIVE pairs AS (
    (
        SELECT data_source_id, series_type_definition_id
        FROM data_point_series
        ORDER BY data_source_id, series_type_definition_id
        LIMIT 1
    )
    UNION ALL
    SELECT next.data_source_id, next.series_type_definition_id
    FROM pairs
    CROSS JOIN LATERAL (
        SELECT d.data_source_id, d.series_type_definition_id
        FROM data_point_series d
        WHERE (d.data_source_id, d.series_type_definition_id)
              > (pairs.data_source_id, pairs.series_type_definition_id)
        ORDER BY d.data_source_id, d.series_type_definition_id
        LIMIT 1
    ) AS next
)
SELECT
    ds.user_id,
    ds.provider,
    std.code,
    (
        SELECT MIN(d.recorded_at) FROM data_point_series d
        WHERE d.data_source_id = p.data_source_id
          AND d.series_type_definition_id = p.series_type_definition_id
    ) AS coverage_start,
    (
        SELECT MAX(d.recorded_at) FROM data_point_series d
        WHERE d.data_source_id = p.data_source_id
          AND d.series_type_definition_id = p.series_type_definition_id
    ) AS coverage_end
FROM pairs p
JOIN data_source ds ON ds.id = p.data_source_id
JOIN series_type_definition std ON std.id = p.series_type_definition_id
"""

EVENT_SPANS_SQL = """
SELECT ds.user_id, ds.provider, er.category,
       MIN(er.start_datetime) AS coverage_start,
       MAX(er.end_datetime) AS coverage_end
FROM event_record er
JOIN data_source ds ON ds.id = er.data_source_id
WHERE er.category IS NOT NULL AND er.category <> ''
GROUP BY ds.user_id, ds.provider, er.category
"""

UPSERT_SQL = """
INSERT INTO data_type_coverage
    (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)
VALUES (%(user_id)s, %(provider)s, %(data_type)s, %(kind)s, %(start)s, %(end)s, %(end)s)
ON CONFLICT (user_id, provider, data_type) DO UPDATE SET
    coverage_start  = LEAST(EXCLUDED.coverage_start, data_type_coverage.coverage_start),
    coverage_end    = GREATEST(EXCLUDED.coverage_end, data_type_coverage.coverage_end),
    last_written_at = GREATEST(EXCLUDED.last_written_at, data_type_coverage.last_written_at)
"""


def get_conninfo() -> str:
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return make_conninfo(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def backfill(conn: psycopg.Connection, select_sql: LiteralString, kind: str, *, dry_run: bool, batch: int) -> int:
    """Upsert one kind's spans, committing every ``batch`` rows.

    One row per (data source, type) pair, so the result set is bounded by how many types
    a user's devices produce and fits in memory comfortably.
    """
    with conn.cursor() as cur:
        cur.execute(select_sql)
        rows = [
            {
                "user_id": user_id,
                "provider": provider,
                "data_type": data_type,
                "kind": kind,
                "start": start,
                "end": end,
            }
            # A pair whose rows were deleted between the probe and the aggregate, or a
            # record with no end datetime.
            for user_id, provider, data_type, start, end in cur.fetchall()
            if start is not None and end is not None
        ]

    if not dry_run:
        with conn.cursor() as cur:
            for i in range(0, len(rows), batch):
                cur.executemany(UPSERT_SQL, rows[i : i + batch])
                conn.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill data_type_coverage from existing data.")
    parser.add_argument("--dry-run", action="store_true", help="Count rows that would be written; change nothing.")
    parser.add_argument("--batch", type=int, default=1000, help="Rows per commit (default 1000).")
    args = parser.parse_args()
    if args.batch <= 0:
        parser.error("--batch must be a positive integer")

    verb = "would write" if args.dry_run else "wrote"
    with psycopg.connect(get_conninfo()) as conn:
        grand = 0
        for label, select_sql, kind in (
            ("series", SERIES_SPANS_SQL, "series"),
            ("event", EVENT_SPANS_SQL, "event"),
        ):
            n = backfill(conn, select_sql, kind, dry_run=args.dry_run, batch=args.batch)
            print(f"{verb} {n:>10}  {label}")
            grand += n

        print(f"\n{'Would write' if args.dry_run else 'Wrote'} {grand} coverage row(s).")


if __name__ == "__main__":
    main()
