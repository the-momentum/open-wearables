#!/usr/bin/env python3
"""Relabel Oura HRV series stored as SDNN to RMSSD.

Oura reports RMSSD-based HRV, but the ingestion historically stored the values
under the SDNN series type (id=3) instead of RMSSD (id=7). The values themselves
are correct — only the label/unit is wrong — so this is a pure relabel, scoped
strictly to provider='oura' so other providers' genuine SDNN data (e.g. Apple) is
left untouched. The ingestion path was fixed separately (oura/data_247.py); this
script corrects pre-existing rows in data_point_series and data_point_series_archive.

Conflict handling: after the ingestion fix, a re-sync can write a correct RMSSD row
at the same (data_source, recorded_at) as an old SDNN row, which would collide with
the unique constraint on relabel. In that case the stale SDNN duplicate is deleted
(the RMSSD row already holds the same Oura value) rather than relabeled.

Idempotent: once relabeled, rows no longer match the SDNN filter, so re-runs are
no-ops. Safe to run on every startup until removed.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/relabel_oura_hrv_sdnn_to_rmssd.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/relabel_oura_hrv_sdnn_to_rmssd.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.database import SessionLocal

PROVIDER = "oura"
SDNN_ID = 3
RMSSD_ID = 7

_PARAMS = {"provider": PROVIDER, "sdnn": SDNN_ID, "rmssd": RMSSD_ID}

# data_point_series: unique on (data_source_id, series_type_definition_id, recorded_at)
_SERIES_COUNT = text("""
    SELECT COUNT(*)
    FROM data_point_series dps
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider = :provider
      AND dps.series_type_definition_id = :sdnn
""")

# SDNN rows that collide with an already-correct RMSSD row — these get deleted, not relabeled.
_SERIES_CONFLICT_COUNT = text("""
    SELECT COUNT(*)
    FROM data_point_series dps
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider = :provider
      AND dps.series_type_definition_id = :sdnn
      AND EXISTS (
          SELECT 1 FROM data_point_series e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :rmssd
            AND e.recorded_at = dps.recorded_at
      )
""")

_SERIES_UPDATE = text("""
    UPDATE data_point_series dps
    SET series_type_definition_id = :rmssd
    FROM data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider = :provider
      AND dps.series_type_definition_id = :sdnn
      AND NOT EXISTS (
          SELECT 1 FROM data_point_series e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :rmssd
            AND e.recorded_at = dps.recorded_at
      )
""")

# Any SDNN Oura rows still present collided with an existing RMSSD row above.
# The EXISTS guard ensures we only delete confirmed duplicates — rows without an RMSSD
# counterpart (e.g. written by an old pod during a rolling deploy) are left for the
# next startup run to pick up via _SERIES_UPDATE.
_SERIES_DELETE_DUPLICATES = text("""
    DELETE FROM data_point_series dps
    USING data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider = :provider
      AND dps.series_type_definition_id = :sdnn
      AND EXISTS (
          SELECT 1 FROM data_point_series e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :rmssd
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
      AND a.series_type_definition_id = :sdnn
""")

_ARCHIVE_CONFLICT_COUNT = text("""
    SELECT COUNT(*)
    FROM data_point_series_archive a
    JOIN data_source ds ON ds.id = a.data_source_id
    WHERE ds.provider = :provider
      AND a.series_type_definition_id = :sdnn
      AND EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :rmssd
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = a.aggregation_type
      )
""")

_ARCHIVE_UPDATE = text("""
    UPDATE data_point_series_archive a
    SET series_type_definition_id = :rmssd
    FROM data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider = :provider
      AND a.series_type_definition_id = :sdnn
      AND NOT EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :rmssd
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = a.aggregation_type
      )
""")

_ARCHIVE_DELETE_DUPLICATES = text("""
    DELETE FROM data_point_series_archive a
    USING data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider = :provider
      AND a.series_type_definition_id = :sdnn
      AND EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :rmssd
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = a.aggregation_type
      )
""")


def _scalar_count(db: Session, query: TextClause) -> int:
    return db.execute(query, _PARAMS).scalar() or 0


def relabel_oura_hrv(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Relabel Oura HRV SDNN rows to RMSSD. Does not commit — caller owns the transaction.

    In dry-run mode counts come from up-front SELECTs. In live mode counts come from
    the actual rowcount returned by each DML statement, so reported numbers reflect
    what was truly written. Rows that collide with an already-correct RMSSD row are
    deleted rather than relabeled.
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
        result = relabel_oura_hrv(db, dry_run=dry_run)
        if dry_run:
            return
        if not any(result.values()):
            print("Nothing to do — no Oura SDNN rows found.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
