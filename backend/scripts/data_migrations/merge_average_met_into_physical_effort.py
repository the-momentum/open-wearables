#!/usr/bin/env python3
"""Move average_met (87) rows onto physical_effort (85).

Both carry METs: physical_effort minute by minute, average_met one value per workout. The series
merged, so a workout's average MET is its physical_effort average. For series_sample,
data_point_series_archive, series_aggregate and event_record_aggregate:
- already has a physical_effort row at the same key: the average_met row is deleted
- everything else: relabeled to physical_effort, value unchanged

Runs once per instance (``data_migration``), one committed batch per data source.

Usage (inside Docker), with --dry-run to preview without changes:
    docker compose exec app uv run python scripts/data_migrations/merge_average_met_into_physical_effort.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.schemas.enums.series_types import SeriesType, get_series_type_id
from app.services.data_migration_service import data_migration_service

_PARAMS = {"average_met": 87, "physical_effort": get_series_type_id(SeriesType.physical_effort)}

_SOURCES = text("SELECT id FROM data_source ORDER BY id")

# table -> (alias, rows of this data source with the retired id, the same key held by physical_effort)
_TABLES = {
    "series_sample": (
        "s",
        "s.data_source_id = :source AND s.series_type_definition_id = :average_met",
        "e.data_source_id = s.data_source_id AND e.recorded_at = s.recorded_at",
    ),
    "data_point_series_archive": (
        "s",
        "s.data_source_id = :source AND s.series_type_definition_id = :average_met",
        "e.data_source_id = s.data_source_id AND e.bucket_start_at = s.bucket_start_at"
        " AND e.aggregation_type = s.aggregation_type",
    ),
    "series_aggregate": (
        "s",
        "s.data_source_id = :source AND s.series_type_definition_id = :average_met",
        "e.data_source_id = s.data_source_id AND e.period_kind = s.period_kind"
        " AND e.period_start = s.period_start AND e.computed_by = s.computed_by",
    ),
    "event_record_aggregate": (
        "s",
        "s.record_id IN (SELECT id FROM event_record WHERE data_source_id = :source)"
        " AND s.series_type_definition_id = :average_met",
        "e.record_id = s.record_id AND e.computed_by = s.computed_by",
    ),
}


def _statements(table: str) -> tuple:
    alias, scope, same_key = _TABLES[table]
    duplicate = f"EXISTS (SELECT 1 FROM {table} e WHERE {same_key} AND e.series_type_definition_id = :physical_effort)"
    return (
        text(f"SELECT count(*), count(*) FILTER (WHERE {duplicate}) FROM {table} {alias} WHERE {scope}"),
        # Deletes run before updates, so the updates only see rows that can be relabeled without
        # hitting the unique constraint.
        text(f"DELETE FROM {table} {alias} WHERE {scope} AND {duplicate}"),
        text(f"UPDATE {table} {alias} SET series_type_definition_id = :physical_effort WHERE {scope}"),
    )


def merge_average_met(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Commits per data source, so an interrupted run keeps what it relabeled."""
    statements = {table: _statements(table) for table in _TABLES}
    result = {f"{table}_{verb}": 0 for table in _TABLES for verb in ("updated", "deleted")}
    for source in db.execute(_SOURCES).scalars().all():
        params = {**_PARAMS, "source": source}
        for table, (count, delete, update) in statements.items():
            if dry_run:
                rows, duplicates = db.execute(count, params).one()
                result[f"{table}_updated"] += rows - duplicates
                result[f"{table}_deleted"] += duplicates
                continue
            result[f"{table}_deleted"] += db.execute(delete, params).rowcount  # ty: ignore[unresolved-attribute]
            result[f"{table}_updated"] += db.execute(update, params).rowcount  # ty: ignore[unresolved-attribute]
        if not dry_run:
            db.commit()

    verb = ("Would relabel", "remove") if dry_run else ("Relabeled", "removed")
    for table in _TABLES:
        print(f"{table}: {verb[0]} {result[f'{table}_updated']}, {verb[1]} {result[f'{table}_deleted']}")
    if dry_run:
        print("\nDry run — no changes made.")
    return result


def _migrate(db: Session, dry_run: bool) -> bool:
    merge_average_met(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(
            db, "merge_average_met_into_physical_effort", lambda: _migrate(db, dry_run), dry_run=dry_run
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
