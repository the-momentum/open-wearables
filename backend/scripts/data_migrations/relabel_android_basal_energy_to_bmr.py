#!/usr/bin/env python3
"""Relabel Android basal_energy rows to the basal_metabolic_rate series.

Health Connect's BasalMetabolicRateRecord (and the Samsung Health Data SDK equivalent)
is a kcal/day rate estimate, not energy burned over an interval, but the ingestion
historically stored it under basal_energy (id=82). On the Android SDK providers no
other record type writes basal_energy — Apple's genuine interval basal energy comes
from HKQuantityTypeIdentifierBasalEnergyBurned on provider='apple' — so every
health_connect/samsung basal_energy row is a BMR reading. The ingestion path now writes
the dedicated basal_metabolic_rate series (id=90); this script corrects pre-existing
rows in series_sample and data_point_series_archive.

Relabeled rows also get is_daily_total=NULL: a BMR reading is an instantaneous rate,
and the new series is AVG-aggregated, where the flag does not apply.

Conflict handling: after the ingestion fix, a re-sync can write a correct
basal_metabolic_rate row at the same (data_source, recorded_at) as an old basal_energy
row, which would collide with the unique constraint on relabel. In that case the stale
basal_energy duplicate is deleted rather than relabeled.

Idempotent: once relabeled, rows no longer match the basal_energy filter, so re-runs
are no-ops. Safe to run on every startup until removed.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/relabel_android_basal_energy_to_bmr.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/relabel_android_basal_energy_to_bmr.py
"""

import argparse

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.database import SessionLocal

PROVIDERS = ("health_connect", "samsung")
BASAL_ENERGY_ID = 82
BMR_ID = 90

_PARAMS = {"providers": list(PROVIDERS), "basal": BASAL_ENERGY_ID, "bmr": BMR_ID}


def _q(sql: str) -> TextClause:
    return text(sql).bindparams(bindparam("providers", expanding=True))


# series_sample: unique on (data_source_id, series_type_definition_id, recorded_at)
_SERIES_COUNT = _q("""
    SELECT COUNT(*)
    FROM series_sample dps
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider IN :providers
      AND dps.series_type_definition_id = :basal
""")

# basal_energy rows that collide with an already-correct basal_metabolic_rate row —
# these get deleted, not relabeled.
_SERIES_CONFLICT_COUNT = _q("""
    SELECT COUNT(*)
    FROM series_sample dps
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider IN :providers
      AND dps.series_type_definition_id = :basal
      AND EXISTS (
          SELECT 1 FROM series_sample e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.recorded_at = dps.recorded_at
      )
""")

_SERIES_UPDATE = _q("""
    UPDATE series_sample dps
    SET series_type_definition_id = :bmr, is_daily_total = NULL
    FROM data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider IN :providers
      AND dps.series_type_definition_id = :basal
      AND NOT EXISTS (
          SELECT 1 FROM series_sample e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.recorded_at = dps.recorded_at
      )
""")

# Any basal_energy Android rows still present collided with an existing
# basal_metabolic_rate row above. The EXISTS guard ensures we only delete confirmed
# duplicates — rows without a counterpart (e.g. written by an old pod during a rolling
# deploy) are left for the next startup run to pick up via _SERIES_UPDATE.
_SERIES_DELETE_DUPLICATES = _q("""
    DELETE FROM series_sample dps
    USING data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider IN :providers
      AND dps.series_type_definition_id = :basal
      AND EXISTS (
          SELECT 1 FROM series_sample e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.recorded_at = dps.recorded_at
      )
""")

# data_point_series_archive: unique on (data_source_id, series_type_definition_id,
# bucket_start_at, aggregation_type)
_ARCHIVE_COUNT = _q("""
    SELECT COUNT(*)
    FROM data_point_series_archive a
    JOIN data_source ds ON ds.id = a.data_source_id
    WHERE ds.provider IN :providers
      AND a.series_type_definition_id = :basal
""")

_ARCHIVE_CONFLICT_COUNT = _q("""
    SELECT COUNT(*)
    FROM data_point_series_archive a
    JOIN data_source ds ON ds.id = a.data_source_id
    WHERE ds.provider IN :providers
      AND a.series_type_definition_id = :basal
      AND EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = a.aggregation_type
      )
""")

_ARCHIVE_UPDATE = _q("""
    UPDATE data_point_series_archive a
    SET series_type_definition_id = :bmr
    FROM data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider IN :providers
      AND a.series_type_definition_id = :basal
      AND NOT EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = a.aggregation_type
      )
""")

_ARCHIVE_DELETE_DUPLICATES = _q("""
    DELETE FROM data_point_series_archive a
    USING data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider IN :providers
      AND a.series_type_definition_id = :basal
      AND EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = a.aggregation_type
      )
""")


def _scalar_count(db: Session, query: TextClause) -> int:
    return db.execute(query, _PARAMS).scalar() or 0


def relabel_android_basal_energy(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Relabel Android basal_energy rows to basal_metabolic_rate. Does not commit —
    caller owns the transaction.

    In dry-run mode counts come from up-front SELECTs. In live mode counts come from
    the actual rowcount returned by each DML statement, so reported numbers reflect
    what was truly written. Rows that collide with an already-correct
    basal_metabolic_rate row are deleted rather than relabeled.
    """
    if dry_run:
        series_deleted = _scalar_count(db, _SERIES_CONFLICT_COUNT)
        series_updated = _scalar_count(db, _SERIES_COUNT) - series_deleted
        archive_deleted = _scalar_count(db, _ARCHIVE_CONFLICT_COUNT)
        archive_updated = _scalar_count(db, _ARCHIVE_COUNT) - archive_deleted
        print(f"series_sample:         Would relabel {series_updated}, remove {series_deleted} duplicate(s)")
        print(f"data_point_series_archive: Would relabel {archive_updated}, remove {archive_deleted} duplicate(s)")
        print("\nDry run — no changes made.")
        return {
            "series_updated": series_updated,
            "series_deleted": series_deleted,
            "archive_updated": archive_updated,
            "archive_deleted": archive_deleted,
        }

    series_updated = db.execute(_SERIES_UPDATE, _PARAMS).rowcount  # ty: ignore[missing-attribute]
    series_deleted = db.execute(_SERIES_DELETE_DUPLICATES, _PARAMS).rowcount  # ty: ignore[missing-attribute]
    archive_updated = db.execute(_ARCHIVE_UPDATE, _PARAMS).rowcount  # ty: ignore[missing-attribute]
    archive_deleted = db.execute(_ARCHIVE_DELETE_DUPLICATES, _PARAMS).rowcount  # ty: ignore[missing-attribute]

    print(f"series_sample:         Relabeled {series_updated}, removed {series_deleted} duplicate(s)")
    print(f"data_point_series_archive: Relabeled {archive_updated}, removed {archive_deleted} duplicate(s)")

    return {
        "series_updated": series_updated,
        "series_deleted": series_deleted,
        "archive_updated": archive_updated,
        "archive_deleted": archive_deleted,
    }


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        result = relabel_android_basal_energy(db, dry_run=dry_run)
        if dry_run:
            return
        if not any(result.values()):
            print("Nothing to do — no Android basal_energy rows found.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
