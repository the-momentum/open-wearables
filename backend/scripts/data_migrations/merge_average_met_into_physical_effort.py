#!/usr/bin/env python3
"""Move average_met (87) rows onto physical_effort (85).

Both carry METs: physical_effort minute by minute, average_met one value per workout. The series
merged, so a workout's average MET is its physical_effort average. For series_sample,
data_point_series_archive, series_aggregate and event_record_aggregate:
- already has a physical_effort row at the same key: the average_met row is deleted; a sample's workout
  average goes onto that workout's session row first, so the value is kept where it is read from now
- everything else: relabeled to physical_effort, value unchanged

data_type_coverage rows keyed by a renamed series (average_met, walking_heart_rate_average) are re-keyed
to the current name, widening a row the new name already has.

Runs at every start until one finds nothing to move (``data_migration``), one committed batch per data source
that holds such rows.

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

# Only the sources that hold rows with the retired id: on most instances a handful, not every source.
_SOURCES = text("""
    SELECT DISTINCT data_source_id AS id FROM series_sample WHERE series_type_definition_id = :average_met
    UNION SELECT DISTINCT data_source_id FROM data_point_series_archive WHERE series_type_definition_id = :average_met
    UNION SELECT DISTINCT data_source_id FROM series_aggregate WHERE series_type_definition_id = :average_met
    UNION SELECT DISTINCT er.data_source_id FROM event_record_aggregate a
        JOIN event_record er ON er.id = a.record_id WHERE a.series_type_definition_id = :average_met
    ORDER BY id
""")
# A sync writing the same source holds its rows; behind one, a statement fails and the next start retries
# instead of holding the startup.
_LOCK_TIMEOUT = text("SET lock_timeout = '10s'")

# A sample's workout average that a physical_effort sample at the same instant would push out goes onto
# the workout the instant falls in, as the provider's session value, before the sample is deleted.
_KEEP_WORKOUT_AVERAGE = text("""
    INSERT INTO event_record_aggregate (id, record_id, series_type_definition_id, computed_by, avg, count)
    SELECT gen_random_uuid(), er.id, :physical_effort, 'provider', s.value, 1
    FROM series_sample s
    JOIN event_record er ON er.data_source_id = s.data_source_id AND er.category = 'workout'
        AND er.start_datetime <= s.recorded_at AND er.end_datetime >= s.recorded_at
    WHERE s.data_source_id = :source AND s.series_type_definition_id = :average_met
      AND EXISTS (
          SELECT 1 FROM series_sample e
          WHERE e.data_source_id = s.data_source_id AND e.recorded_at = s.recorded_at
            AND e.series_type_definition_id = :physical_effort
      )
    ON CONFLICT ON CONSTRAINT uq_event_record_aggregate_record_type_computed_by DO NOTHING
""")

# Coverage spans keyed by a renamed series follow the name; a span the new name already has is widened.
_RENAMED_DATA_TYPES = {"average_met": "physical_effort", "walking_heart_rate_average": "walking_heart_rate"}
_RENAME_COVERAGE = [
    text("""
        UPDATE data_type_coverage n SET
            coverage_start = LEAST(n.coverage_start, o.coverage_start),
            coverage_end = GREATEST(n.coverage_end, o.coverage_end),
            last_written_at = GREATEST(n.last_written_at, o.last_written_at)
        FROM data_type_coverage o
        WHERE o.user_id = n.user_id AND o.provider = n.provider AND o.kind = n.kind
          AND o.data_type = :old AND n.data_type = :new
    """),
    text("""
        DELETE FROM data_type_coverage o
        WHERE o.data_type = :old AND EXISTS (
            SELECT 1 FROM data_type_coverage n
            WHERE n.user_id = o.user_id AND n.provider = o.provider AND n.kind = o.kind AND n.data_type = :new
        )
    """),
    text("UPDATE data_type_coverage SET data_type = :new WHERE data_type = :old"),
]

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
    result["coverage_renamed"] = 0
    for source in db.execute(_SOURCES, _PARAMS).scalars().all():
        params = {**_PARAMS, "source": source}
        for table, (count, delete, update) in statements.items():
            if dry_run:
                rows, duplicates = db.execute(count, params).one()
                result[f"{table}_updated"] += rows - duplicates
                result[f"{table}_deleted"] += duplicates
                continue
            if table == "series_sample":
                db.execute(_KEEP_WORKOUT_AVERAGE, params)
            result[f"{table}_deleted"] += db.execute(delete, params).rowcount  # ty: ignore[unresolved-attribute]
            result[f"{table}_updated"] += db.execute(update, params).rowcount  # ty: ignore[unresolved-attribute]
        if not dry_run:
            db.commit()
    if not dry_run:
        for old, new in _RENAMED_DATA_TYPES.items():
            for statement in _RENAME_COVERAGE:
                renamed = db.execute(statement, {"old": old, "new": new}).rowcount  # ty: ignore[unresolved-attribute]
            result["coverage_renamed"] += renamed
        db.commit()

    verb = ("Would relabel", "remove") if dry_run else ("Relabeled", "removed")
    for table in _TABLES:
        print(f"{table}: {verb[0]} {result[f'{table}_updated']}, {verb[1]} {result[f'{table}_deleted']}")
    if not dry_run:
        print(f"data_type_coverage: re-keyed {result['coverage_renamed']}")
    if dry_run:
        print("\nDry run — no changes made.")
    return result


def _migrate(db: Session, dry_run: bool) -> bool:
    # Recorded only by a start that finds nothing: a pod on the previous release writes id 87 until the rollout ends.
    moved = merge_average_met(db, dry_run=dry_run)
    return not dry_run and not any(moved.values())


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        db.execute(_LOCK_TIMEOUT)
        data_migration_service.run(
            db, "merge_average_met_into_physical_effort", lambda: _migrate(db, dry_run), dry_run=dry_run
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
