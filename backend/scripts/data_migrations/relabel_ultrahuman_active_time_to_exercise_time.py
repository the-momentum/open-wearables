#!/usr/bin/env python3
"""Relabel Ultrahuman active minutes stored as active_time to exercise_time.

Ultrahuman documents active minutes as moderate to vigorous activity, which
matches exercise_time (id=84), but the ingestion mapped them to active_time (id=88),
the series for all non-sedentary time. The values are correct — only the label is
wrong — so this is a pure relabel, scoped strictly to provider='ultrahuman' so other
providers' active_time is left untouched. The mapping was fixed in
ultrahuman/coverage.py in the same change; this script corrects pre-existing rows in
data_point_series and data_point_series_archive.

Conflict handling: after the mapping fix, a re-sync can write an exercise_time row at
the same (data_source, recorded_at) as an old active_time row, which would collide with
the unique constraint on relabel. In that case the stale active_time duplicate is
deleted (the exercise_time row already holds the same Ultrahuman value) rather than
relabeled.

Idempotent: once relabeled, rows no longer match the active_time filter, so re-runs
are no-ops. Safe to run on every startup until removed.

Usage (inside Docker), with --dry-run to preview without changes:
    docker compose exec app uv run python scripts/data_migrations/relabel_ultrahuman_active_time_to_exercise_time.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.database import SessionLocal

PROVIDER = "ultrahuman"
ACTIVE_TIME_ID = 88
EXERCISE_TIME_ID = 84

_PARAMS = {"provider": PROVIDER, "active_time": ACTIVE_TIME_ID, "exercise_time": EXERCISE_TIME_ID}

# data_point_series: unique on (data_source_id, series_type_definition_id, recorded_at)
_SERIES_COUNT = text("""
    SELECT COUNT(*)
    FROM data_point_series dps
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider = :provider
      AND dps.series_type_definition_id = :active_time
""")

# active_time rows that collide with an already-correct exercise_time row — deleted, not relabeled.
_SERIES_CONFLICT_COUNT = text("""
    SELECT COUNT(*)
    FROM data_point_series dps
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider = :provider
      AND dps.series_type_definition_id = :active_time
      AND EXISTS (
          SELECT 1 FROM data_point_series e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :exercise_time
            AND e.recorded_at = dps.recorded_at
      )
""")

_SERIES_UPDATE = text("""
    UPDATE data_point_series dps
    SET series_type_definition_id = :exercise_time
    FROM data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider = :provider
      AND dps.series_type_definition_id = :active_time
      AND NOT EXISTS (
          SELECT 1 FROM data_point_series e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :exercise_time
            AND e.recorded_at = dps.recorded_at
      )
""")

# The EXISTS guard deletes only confirmed duplicates — rows without an exercise_time
# counterpart (e.g. written by an old pod during a rolling deploy) are left for the
# next startup run to pick up via _SERIES_UPDATE.
_SERIES_DELETE_DUPLICATES = text("""
    DELETE FROM data_point_series dps
    USING data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider = :provider
      AND dps.series_type_definition_id = :active_time
      AND EXISTS (
          SELECT 1 FROM data_point_series e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :exercise_time
            AND e.recorded_at = dps.recorded_at
      )
""")

# data_point_series_archive: unique on (data_source_id, series_type_definition_id,
# bucket_start_at, aggregation_type)
_ARCHIVE_COUNT = text("""
    SELECT COUNT(*)
    FROM data_point_series_archive a
    JOIN data_source ds ON ds.id = a.data_source_id
    WHERE ds.provider = :provider
      AND a.series_type_definition_id = :active_time
""")

_ARCHIVE_CONFLICT_COUNT = text("""
    SELECT COUNT(*)
    FROM data_point_series_archive a
    JOIN data_source ds ON ds.id = a.data_source_id
    WHERE ds.provider = :provider
      AND a.series_type_definition_id = :active_time
      AND EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :exercise_time
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = a.aggregation_type
      )
""")

_ARCHIVE_UPDATE = text("""
    UPDATE data_point_series_archive a
    SET series_type_definition_id = :exercise_time
    FROM data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider = :provider
      AND a.series_type_definition_id = :active_time
      AND NOT EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :exercise_time
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = a.aggregation_type
      )
""")

_ARCHIVE_DELETE_DUPLICATES = text("""
    DELETE FROM data_point_series_archive a
    USING data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider = :provider
      AND a.series_type_definition_id = :active_time
      AND EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :exercise_time
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = a.aggregation_type
      )
""")


def _scalar_count(db: Session, query: TextClause) -> int:
    return db.execute(query, _PARAMS).scalar() or 0


def relabel_ultrahuman_active_time(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Relabel Ultrahuman active_time rows to exercise_time. Does not commit — caller owns the transaction.

    In dry-run mode counts come from up-front SELECTs. In live mode counts come from
    the actual rowcount returned by each DML statement. Rows that collide with an
    already-correct exercise_time row are deleted rather than relabeled.
    """
    if dry_run:
        series_deleted = _scalar_count(db, _SERIES_CONFLICT_COUNT)
        series_updated = _scalar_count(db, _SERIES_COUNT) - series_deleted
        archive_deleted = _scalar_count(db, _ARCHIVE_CONFLICT_COUNT)
        archive_updated = _scalar_count(db, _ARCHIVE_COUNT) - archive_deleted
        print(f"data_point_series:         Would relabel {series_updated}, remove {series_deleted} duplicate(s)")
        print(f"data_point_series_archive: Would relabel {archive_updated}, remove {archive_deleted} duplicate(s)")
        print("\nDry run — no changes made.")
        return {
            "series_updated": series_updated,
            "series_deleted": series_deleted,
            "archive_updated": archive_updated,
            "archive_deleted": archive_deleted,
        }

    series_updated = db.execute(_SERIES_UPDATE, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]
    series_deleted = db.execute(_SERIES_DELETE_DUPLICATES, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]
    archive_updated = db.execute(_ARCHIVE_UPDATE, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]
    archive_deleted = db.execute(_ARCHIVE_DELETE_DUPLICATES, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]

    print(f"data_point_series:         Relabeled {series_updated}, removed {series_deleted} duplicate(s)")
    print(f"data_point_series_archive: Relabeled {archive_updated}, removed {archive_deleted} duplicate(s)")

    return {
        "series_updated": series_updated,
        "series_deleted": series_deleted,
        "archive_updated": archive_updated,
        "archive_deleted": archive_deleted,
    }


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        result = relabel_ultrahuman_active_time(db, dry_run=dry_run)
        if dry_run:
            return
        if not any(result.values()):
            print("Nothing to do — no Ultrahuman active_time rows found.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
