#!/usr/bin/env python3
"""Move Whoop cycle energy from active_energy (81) to total_energy (89) (#1658).

Whoop's cycle kilojoule includes BMR, so it was never active energy. For Whoop rows in
data_point_series and data_point_series_archive:
- value 0 (strap not worn): deleted, ingestion no longer writes these
- already has a total_energy row at the same key (re-synced after deploy): deleted
- everything else: relabeled to total_energy, value unchanged

Idempotent; runs on startup.

Usage (inside Docker), with --dry-run to preview without changes:
    docker compose exec app uv run python scripts/data_migrations/relabel_whoop_active_energy_to_total_energy.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.database import SessionLocal

PROVIDER = "whoop"
ACTIVE_ENERGY_ID = 81
TOTAL_ENERGY_ID = 89

_PARAMS = {"provider": PROVIDER, "active_energy": ACTIVE_ENERGY_ID, "total_energy": TOTAL_ENERGY_ID}

# data_point_series: unique on (data_source_id, series_type_definition_id, recorded_at)
_SERIES_SCOPE = """
    FROM data_point_series dps
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider = :provider
      AND dps.series_type_definition_id = :active_energy
"""
_SERIES_HAS_TOTAL = """
    EXISTS (
        SELECT 1 FROM data_point_series e
        WHERE e.data_source_id = dps.data_source_id
          AND e.series_type_definition_id = :total_energy
          AND e.recorded_at = dps.recorded_at
    )
"""
# Rows deleted rather than relabeled: no-wear zeros, and duplicates of an existing total_energy row.
_SERIES_DROP = f"(dps.value = 0 OR {_SERIES_HAS_TOTAL})"

_SERIES_COUNT = text(f"SELECT COUNT(*) {_SERIES_SCOPE}")
_SERIES_DROP_COUNT = text(f"SELECT COUNT(*) {_SERIES_SCOPE} AND {_SERIES_DROP}")

_SERIES_DELETE = text(f"""
    DELETE FROM data_point_series dps
    USING data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider = :provider
      AND dps.series_type_definition_id = :active_energy
      AND {_SERIES_DROP}
""")

_SERIES_UPDATE = text("""
    UPDATE data_point_series dps
    SET series_type_definition_id = :total_energy
    FROM data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider = :provider
      AND dps.series_type_definition_id = :active_energy
""")

# data_point_series_archive: unique on (data_source_id, series_type_definition_id,
# bucket_start_at, aggregation_type)
_ARCHIVE_SCOPE = """
    FROM data_point_series_archive a
    JOIN data_source ds ON ds.id = a.data_source_id
    WHERE ds.provider = :provider
      AND a.series_type_definition_id = :active_energy
"""
_ARCHIVE_HAS_TOTAL = """
    EXISTS (
        SELECT 1 FROM data_point_series_archive e
        WHERE e.data_source_id = a.data_source_id
          AND e.series_type_definition_id = :total_energy
          AND e.bucket_start_at = a.bucket_start_at
          AND e.aggregation_type = a.aggregation_type
    )
"""
_ARCHIVE_DROP = f"(a.value = 0 OR {_ARCHIVE_HAS_TOTAL})"

_ARCHIVE_COUNT = text(f"SELECT COUNT(*) {_ARCHIVE_SCOPE}")
_ARCHIVE_DROP_COUNT = text(f"SELECT COUNT(*) {_ARCHIVE_SCOPE} AND {_ARCHIVE_DROP}")

_ARCHIVE_DELETE = text(f"""
    DELETE FROM data_point_series_archive a
    USING data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider = :provider
      AND a.series_type_definition_id = :active_energy
      AND {_ARCHIVE_DROP}
""")

_ARCHIVE_UPDATE = text("""
    UPDATE data_point_series_archive a
    SET series_type_definition_id = :total_energy
    FROM data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider = :provider
      AND a.series_type_definition_id = :active_energy
""")


def _scalar_count(db: Session, query: TextClause) -> int:
    return db.execute(query, _PARAMS).scalar() or 0


def relabel_whoop_active_energy(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Relabel Whoop active_energy rows to total_energy. Does not commit — caller owns the transaction.

    Deletes run before updates, so the updates only ever see rows that can be relabeled
    without hitting the unique constraint.
    """
    if dry_run:
        series_deleted = _scalar_count(db, _SERIES_DROP_COUNT)
        series_updated = _scalar_count(db, _SERIES_COUNT) - series_deleted
        archive_deleted = _scalar_count(db, _ARCHIVE_DROP_COUNT)
        archive_updated = _scalar_count(db, _ARCHIVE_COUNT) - archive_deleted
        print(f"data_point_series:         Would relabel {series_updated}, remove {series_deleted}")
        print(f"data_point_series_archive: Would relabel {archive_updated}, remove {archive_deleted}")
        print("\nDry run — no changes made.")
        return {
            "series_updated": series_updated,
            "series_deleted": series_deleted,
            "archive_updated": archive_updated,
            "archive_deleted": archive_deleted,
        }

    series_deleted = db.execute(_SERIES_DELETE, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]
    series_updated = db.execute(_SERIES_UPDATE, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]
    archive_deleted = db.execute(_ARCHIVE_DELETE, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]
    archive_updated = db.execute(_ARCHIVE_UPDATE, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]

    print(f"data_point_series:         Relabeled {series_updated}, removed {series_deleted}")
    print(f"data_point_series_archive: Relabeled {archive_updated}, removed {archive_deleted}")

    return {
        "series_updated": series_updated,
        "series_deleted": series_deleted,
        "archive_updated": archive_updated,
        "archive_deleted": archive_deleted,
    }


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        result = relabel_whoop_active_energy(db, dry_run=dry_run)
        if dry_run:
            return
        if not any(result.values()):
            print("Nothing to do — no Whoop active_energy rows found.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
