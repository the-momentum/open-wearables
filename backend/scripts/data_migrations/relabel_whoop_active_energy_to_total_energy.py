#!/usr/bin/env python3
"""Move Whoop cycle energy from active_energy (81) to total_energy (89) (#1658).

Whoop's cycle kilojoule includes BMR, so it was never active energy. For Whoop rows in
data_point_series and data_point_series_archive:
- value 0 (strap not worn): deleted, ingestion no longer writes these
- already has a total_energy row at the same key (re-synced after deploy): deleted
- everything else: relabeled to total_energy, value unchanged

Runs once per instance (``data_migration``), one committed batch per Whoop data source.

Usage (inside Docker), with --dry-run to preview without changes:
    docker compose exec app uv run python scripts/data_migrations/relabel_whoop_active_energy_to_total_energy.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.schemas.enums import ProviderName
from app.schemas.enums.series_types import SeriesType, get_series_type_id
from app.services.data_migration_service import data_migration_service

_PARAMS = {
    "active_energy": get_series_type_id(SeriesType.active_energy),
    "total_energy": get_series_type_id(SeriesType.total_energy),
}

_SOURCES = text("SELECT id FROM data_source WHERE provider = :provider ORDER BY id")

# data_point_series: unique on (data_source_id, series_type_definition_id, recorded_at)
_SERIES_SCOPE = "dps.data_source_id = :source AND dps.series_type_definition_id = :active_energy"
# Rows deleted rather than relabeled: no-wear zeros, and duplicates of an existing total_energy row.
_SERIES_DROP = """(dps.value = 0 OR EXISTS (
    SELECT 1 FROM data_point_series e
    WHERE e.data_source_id = dps.data_source_id
      AND e.series_type_definition_id = :total_energy
      AND e.recorded_at = dps.recorded_at
))"""

# data_point_series_archive: unique on (data_source_id, series_type_definition_id, bucket_start_at, aggregation_type)
_ARCHIVE_SCOPE = "a.data_source_id = :source AND a.series_type_definition_id = :active_energy"
_ARCHIVE_DROP = """(a.value = 0 OR EXISTS (
    SELECT 1 FROM data_point_series_archive e
    WHERE e.data_source_id = a.data_source_id
      AND e.series_type_definition_id = :total_energy
      AND e.bucket_start_at = a.bucket_start_at
      AND e.aggregation_type = a.aggregation_type
))"""

_COUNTS = text(f"""
    SELECT
        (SELECT count(*) FROM data_point_series dps WHERE {_SERIES_SCOPE}),
        (SELECT count(*) FROM data_point_series dps WHERE {_SERIES_SCOPE} AND {_SERIES_DROP}),
        (SELECT count(*) FROM data_point_series_archive a WHERE {_ARCHIVE_SCOPE}),
        (SELECT count(*) FROM data_point_series_archive a WHERE {_ARCHIVE_SCOPE} AND {_ARCHIVE_DROP})
""")
# Deletes run before updates, so the updates only see rows that can be relabeled without
# hitting the unique constraint
_SERIES_DELETE = text(f"DELETE FROM data_point_series dps WHERE {_SERIES_SCOPE} AND {_SERIES_DROP}")
_SERIES_UPDATE = text(
    f"UPDATE data_point_series dps SET series_type_definition_id = :total_energy WHERE {_SERIES_SCOPE}"
)
_ARCHIVE_DELETE = text(f"DELETE FROM data_point_series_archive a WHERE {_ARCHIVE_SCOPE} AND {_ARCHIVE_DROP}")
_ARCHIVE_UPDATE = text(
    f"UPDATE data_point_series_archive a SET series_type_definition_id = :total_energy WHERE {_ARCHIVE_SCOPE}"
)


def relabel_whoop_active_energy(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Commits per data source, so an interrupted run keeps what it relabeled."""
    result = dict.fromkeys(("series_updated", "series_deleted", "archive_updated", "archive_deleted"), 0)
    sources = db.execute(_SOURCES, {"provider": ProviderName.WHOOP.value}).scalars().all()
    for source in sources:
        params = {**_PARAMS, "source": source}
        if dry_run:
            series, series_dropped, archive, archive_dropped = db.execute(_COUNTS, params).one()
            result["series_updated"] += series - series_dropped
            result["series_deleted"] += series_dropped
            result["archive_updated"] += archive - archive_dropped
            result["archive_deleted"] += archive_dropped
            continue
        result["series_deleted"] += db.execute(_SERIES_DELETE, params).rowcount  # ty: ignore[unresolved-attribute]
        result["series_updated"] += db.execute(_SERIES_UPDATE, params).rowcount  # ty: ignore[unresolved-attribute]
        result["archive_deleted"] += db.execute(_ARCHIVE_DELETE, params).rowcount  # ty: ignore[unresolved-attribute]
        result["archive_updated"] += db.execute(_ARCHIVE_UPDATE, params).rowcount  # ty: ignore[unresolved-attribute]
        db.commit()

    verb = ("Would relabel", "remove") if dry_run else ("Relabeled", "removed")
    print(f"data_point_series:         {verb[0]} {result['series_updated']}, {verb[1]} {result['series_deleted']}")
    print(f"data_point_series_archive: {verb[0]} {result['archive_updated']}, {verb[1]} {result['archive_deleted']}")
    if dry_run:
        print("\nDry run — no changes made.")
    return result


def _migrate(db: Session, dry_run: bool) -> bool:
    relabel_whoop_active_energy(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(
            db, "relabel_whoop_active_energy_to_total_energy", lambda: _migrate(db, dry_run), dry_run=dry_run
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
