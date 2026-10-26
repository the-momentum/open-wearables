#!/usr/bin/env python3
"""One-off: merge data sources split by unstable identity values, and drop duplicate events.

Phase 1 - identity values the extraction no longer writes. Rows whose device model is a
placeholder ("", "unknown" - Garmin edits), whose Google Health model is a platform name
(HEALTH_KIT, FITBIT, ...), or Polar rows without a source (sleep, before it set one) are
renamed to the identity live sync now resolves. When a row with that identity already exists,
everything is moved into it instead: events, samples, archive, day and session aggregates and health scores; records the
target already holds at the same key are dropped from the source first.

Phase 2 - the same event stored under two data sources of one user and provider (legacy
"apple" source vs the writer name, Garmin activities before and after the device was known).
The copy in the most specific source is kept (device id > app id > model > a real source name),
a score or sleep/workout/cycle details on a dropped copy move to the kept one when it lacks them,
and the rest are deleted (phase 1 does the same for the copies it drops). Samples are not
touched here: overlapping samples across sources are different writers, not duplicates.

Idempotent: renamed rows no longer match phase 1 and duplicates are gone, so re-runs are no-ops.
Phase 2 scans every event, so startup runs the script once: a clean run is recorded in data_migration
and skipped afterwards, while a run with failures is retried on the next startup.
Samples, archive rows and duplicate events are processed in committed batches, so a run that is
interrupted keeps its progress and the next one continues where it stopped.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/merge_duplicate_data_sources.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/merge_duplicate_data_sources.py
"""

import argparse
from logging import getLogger
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.constants.devices_map.device_types import DEVICE_MODEL_PLACEHOLDERS
from app.database import engine
from app.integrations.rollup_queue import requeue_dirty_days
from app.services.data_migration_service import data_migration_service
from app.utils.sentry_helpers import log_and_capture_error

logger = getLogger(__name__)

# Rows per committed batch when moving samples/archive and deleting duplicate events
_BATCH_SIZE = 50_000
# A live sync holding a lock fails the step instead of stalling startup; the next run retries it
_LOCK_TIMEOUT = text("SET lock_timeout = '10s'")

# Google Health dataSource.platform values the old extraction stored as the device model
GOOGLE_PLATFORMS = (
    "FITBIT",
    "HEALTH_CONNECT",
    "HEALTH_KIT",
    "FIT",
    "FITBIT_WEB_API",
    "NEST",
    "GOOGLE_WEB_API",
    "GOOGLE_PARTNER_INTEGRATION",
    "PLATFORM_UNSPECIFIED",
)

_RENAME_CANDIDATES = text("""
    SELECT id, user_id, provider,
           CASE WHEN lower(btrim(device_model)) = ANY(:placeholders)
                  OR (provider = 'google_health' AND device_model = ANY(:platforms))
                THEN NULL ELSE device_model END AS new_model,
           CASE WHEN provider = 'polar' AND source IS NULL THEN 'polar' ELSE source END AS new_source
    FROM data_source
    WHERE device_id IS NULL AND source_app_id IS NULL
      AND (lower(btrim(device_model)) = ANY(:placeholders)
           OR (provider = 'google_health' AND device_model = ANY(:platforms))
           OR (provider = 'polar' AND source IS NULL))
""")

_TARGET = text("""
    SELECT id FROM data_source
    WHERE user_id = :user_id AND provider = :provider AND id <> :src
      AND device_id IS NULL AND source_app_id IS NULL
      AND COALESCE(device_model, '') = COALESCE(:model, '') AND COALESCE(source, '') = COALESCE(:source, '')
""")

_RENAME = text("UPDATE data_source SET device_model = :model, source = :source WHERE id = :src")
# Local days a source holds samples on: once moved, the target's own rows for them are stale
_SAMPLE_DAYS = text("""
    SELECT DISTINCT ((recorded_at AT TIME ZONE 'UTC') + coalesce(zone_offset, '+00:00')::interval)::date AS day
    FROM series_sample WHERE data_source_id = :src
""")

# Per-event detail tables, keyed by record_id and cascade-deleted with their event
_DETAIL_TABLES = ("sleep_details", "workout_details", "menstrual_cycle_details")

# Per-source tables batched along their unique index (data_source_id, *key), so every batch is an index range
_BATCHED_TABLES = {
    "series_sample": ("series_type_definition_id", "recorded_at"),
    "data_point_series_archive": ("series_type_definition_id", "bucket_start_at", "aggregation_type"),
    "series_aggregate": ("series_type_definition_id", "period_kind", "period_start", "computed_by"),
}


class _BatchStatements(NamedTuple):
    nth_key: TextClause
    last_key: TextClause
    drop_copies: TextClause
    move: TextClause


def _batch_statements(table: str, key: tuple[str, ...]) -> _BatchStatements:
    """Key of the batch's last row, then within src up to it: drop copies the target holds, move the rest."""
    columns = ", ".join(key)
    # DESC binds to one column only: the last row of the key order needs it on every column.
    columns_desc = ", ".join(f"{c} DESC" for c in key)
    up_to_bound = (
        f"s.data_source_id = :src AND ({', '.join(f's.{c}' for c in key)}) <= ({', '.join(f':{c}' for c in key)})"
    )
    same_key = " AND ".join(f"t.{c} = s.{c}" for c in key)
    return _BatchStatements(
        text(f"SELECT {columns} FROM {table} WHERE data_source_id = :src ORDER BY {columns} OFFSET :offset LIMIT 1"),
        text(f"SELECT {columns} FROM {table} WHERE data_source_id = :src ORDER BY {columns_desc} LIMIT 1"),
        text(f"""
            DELETE FROM {table} s
            WHERE {up_to_bound}
              AND EXISTS (SELECT 1 FROM {table} t WHERE t.data_source_id = :tgt AND {same_key})
        """),
        text(f"UPDATE {table} s SET data_source_id = :tgt WHERE {up_to_bound}"),
    )


_BATCHES = [_batch_statements(table, key) for table, key in _BATCHED_TABLES.items()]

# Move a data source's events, scores and itself into another, after its samples and archive moved.
# Conflicting copies in the source are dropped first.
_MERGE_STEPS = [
    text("""
        UPDATE health_score h SET event_record_id = t.id
        FROM event_record s
        JOIN event_record t ON t.data_source_id = :tgt
            AND t.start_datetime = s.start_datetime AND t.end_datetime = s.end_datetime
        WHERE s.data_source_id = :src AND h.event_record_id = s.id
          AND NOT EXISTS (
              SELECT 1 FROM health_score h2
              WHERE h2.event_record_id = t.id AND h2.provider = h.provider AND h2.category = h.category
          )
    """),
    *(
        text(f"""
            UPDATE {table} d SET record_id = t.id
            FROM event_record s
            JOIN event_record t ON t.data_source_id = :tgt
                AND t.start_datetime = s.start_datetime AND t.end_datetime = s.end_datetime
            WHERE s.data_source_id = :src AND d.record_id = s.id
              AND NOT EXISTS (SELECT 1 FROM {table} k WHERE k.record_id = t.id)
        """)
        for table in _DETAIL_TABLES
    ),
    text("""
        UPDATE event_record_aggregate a SET record_id = t.id
        FROM event_record s
        JOIN event_record t ON t.data_source_id = :tgt
            AND t.start_datetime = s.start_datetime AND t.end_datetime = s.end_datetime
        WHERE s.data_source_id = :src AND a.record_id = s.id
          AND NOT EXISTS (
              SELECT 1 FROM event_record_aggregate k
              WHERE k.record_id = t.id AND k.series_type_definition_id = a.series_type_definition_id
                AND k.computed_by = a.computed_by
          )
    """),
    text("""
        DELETE FROM event_record s USING event_record t
        WHERE s.data_source_id = :src AND t.data_source_id = :tgt
          AND t.start_datetime = s.start_datetime AND t.end_datetime = s.end_datetime
    """),
    text("UPDATE event_record SET data_source_id = :tgt WHERE data_source_id = :src"),
    text("UPDATE health_score SET data_source_id = :tgt WHERE data_source_id = :src"),
    text("""
        UPDATE data_source t SET
            device_type = COALESCE(t.device_type, s.device_type),
            software_version = COALESCE(t.software_version, s.software_version),
            user_connection_id = COALESCE(t.user_connection_id, s.user_connection_id)
        FROM data_source s WHERE t.id = :tgt AND s.id = :src
    """),
    text("DELETE FROM data_source WHERE id = :src"),
]

# Duplicate events across a user's sources of one provider, ranked most specific source first.
# Only users with several sources of a provider can have them. Groups spanning several device ids
# are different devices' records, not copies, so they are left alone.
_RANKED_DUPLICATES = """
    WITH multi_source AS (
        SELECT user_id, provider FROM data_source GROUP BY user_id, provider HAVING count(*) > 1
    ),
    multi_device AS (
        SELECT ds.user_id, ds.provider, e.category, e.start_datetime, e.end_datetime
        FROM event_record e
        JOIN data_source ds ON ds.id = e.data_source_id
        WHERE ds.device_id IS NOT NULL
        GROUP BY ds.user_id, ds.provider, e.category, e.start_datetime, e.end_datetime
        HAVING count(DISTINCT ds.device_id) > 1
    ),
    ranked AS (
        SELECT e.id,
               first_value(e.id) OVER w AS keep_id,
               row_number() OVER w AS rn
        FROM event_record e
        JOIN data_source ds ON ds.id = e.data_source_id
        JOIN multi_source ms ON ms.user_id = ds.user_id AND ms.provider = ds.provider
        -- Meals are unique by external_id, so several can share one interval
        WHERE e.category <> 'meal' AND NOT EXISTS (
            SELECT 1 FROM multi_device m
            WHERE m.user_id = ds.user_id AND m.provider = ds.provider AND m.category = e.category
              AND m.start_datetime = e.start_datetime AND m.end_datetime = e.end_datetime
        )
        WINDOW w AS (
            PARTITION BY ds.user_id, ds.provider, e.category, e.start_datetime, e.end_datetime
            ORDER BY (ds.device_id IS NOT NULL) DESC, (ds.source_app_id IS NOT NULL) DESC,
                     (ds.device_model IS NOT NULL) DESC,
                     (ds.source IS NOT NULL AND ds.source <> ds.provider::text) DESC,
                     ds.id, e.id
        )
    )
"""
_DUPLICATE_COUNT = text(_RANKED_DUPLICATES + "SELECT count(*) FROM ranked WHERE rn > 1")

# The ranking scans every event, so it runs once into a session temp table that the steps below read
_DROP_DUPLICATES = text("DROP TABLE IF EXISTS merge_duplicate_events")
_COLLECT_DUPLICATES = [
    _DROP_DUPLICATES,
    text(
        "CREATE TEMP TABLE merge_duplicate_events AS "
        + _RANKED_DUPLICATES
        + "SELECT id, keep_id, rn FROM ranked WHERE rn > 1"
    ),
    text("CREATE INDEX ON merge_duplicate_events (keep_id, rn)"),
    text("CREATE INDEX ON merge_duplicate_events (id)"),
    text("ANALYZE merge_duplicate_events"),
]
# Batches take a kept event's copies in rank order, so its best-ranked copy is seen first
_NEXT_DUPLICATES = text("SELECT id FROM merge_duplicate_events ORDER BY keep_id, rn LIMIT :batch_size")
# A score or details of the best-ranked dropped copy move to a kept event that lacks them
_DUPLICATE_SCORES = text("""
    UPDATE health_score h SET event_record_id = c.keep_id
    FROM (
        SELECT DISTINCT ON (r.keep_id, x.provider, x.category) x.id, r.keep_id
        FROM merge_duplicate_events r JOIN health_score x ON x.event_record_id = r.id
        WHERE r.id = ANY(:ids) AND NOT EXISTS (
            SELECT 1 FROM health_score k
            WHERE k.event_record_id = r.keep_id AND k.provider = x.provider AND k.category = x.category
        )
        ORDER BY r.keep_id, x.provider, x.category, r.rn
    ) c
    WHERE h.id = c.id
""")
_DUPLICATE_DETAILS = [
    text(f"""
        UPDATE {table} d SET record_id = c.keep_id
        FROM (
            SELECT DISTINCT ON (r.keep_id) r.id, r.keep_id
            FROM merge_duplicate_events r JOIN {table} x ON x.record_id = r.id
            WHERE r.id = ANY(:ids) AND NOT EXISTS (SELECT 1 FROM {table} k WHERE k.record_id = r.keep_id)
            ORDER BY r.keep_id, r.rn
        ) c
        WHERE d.record_id = c.id
    """)
    for table in _DETAIL_TABLES
]
_DUPLICATE_AGGREGATES = text("""
    UPDATE event_record_aggregate a SET record_id = c.keep_id
    FROM (
        SELECT DISTINCT ON (r.keep_id, x.series_type_definition_id, x.computed_by) x.id, r.keep_id
        FROM merge_duplicate_events r JOIN event_record_aggregate x ON x.record_id = r.id
        WHERE r.id = ANY(:ids) AND NOT EXISTS (
            SELECT 1 FROM event_record_aggregate k
            WHERE k.record_id = r.keep_id AND k.series_type_definition_id = x.series_type_definition_id
              AND k.computed_by = x.computed_by
        )
        ORDER BY r.keep_id, x.series_type_definition_id, x.computed_by, r.rn
    ) c
    WHERE a.id = c.id
""")
# Dropped copies are deleted by primary key; a join against the temp table would scan event_record
_DELETE_EVENTS = text("DELETE FROM event_record WHERE id = ANY(:ids)")
_FORGET_DUPLICATES = text("DELETE FROM merge_duplicate_events WHERE id = ANY(:ids)")


def _queue_rollup(target: UUID, days: list) -> None:
    """The target's open_wearables rows for the moved days are recomputed by the next rollup run."""
    try:
        requeue_dirty_days((target, day) for day in days)
    except Exception:
        logger.warning("Could not queue %d days of data source %s for the rollup", len(days), target, exc_info=True)


def _rowcount(db: Session, query: TextClause, params: dict) -> int:
    return db.execute(query, params).rowcount  # ty: ignore[unresolved-attribute]


def _move_in_batches(db: Session, statements: _BatchStatements, src: UUID, tgt: UUID) -> None:
    while True:
        bound = db.execute(statements.nth_key, {"src": src, "offset": _BATCH_SIZE - 1}).mappings().first()
        last = bound is None
        if last:
            bound = db.execute(statements.last_key, {"src": src}).mappings().first()
        if bound is None:
            return
        params = {"src": src, "tgt": tgt, **bound}
        db.execute(statements.drop_copies, params)
        db.execute(statements.move, params)
        db.commit()
        if last:
            return


def _remove_duplicate_events(db: Session) -> int:
    for query in _COLLECT_DUPLICATES:
        db.execute(query)
    db.commit()
    removed = 0
    while ids := list(db.execute(_NEXT_DUPLICATES, {"batch_size": _BATCH_SIZE}).scalars()):
        for query in (_DUPLICATE_SCORES, *_DUPLICATE_DETAILS, _DUPLICATE_AGGREGATES):
            db.execute(query, {"ids": ids})
        removed += _rowcount(db, _DELETE_EVENTS, {"ids": ids})
        db.execute(_FORGET_DUPLICATES, {"ids": ids})
        db.commit()
    db.execute(_DROP_DUPLICATES)
    db.commit()
    return removed


def merge_duplicate_data_sources(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Run both phases, committing as it goes.

    The session must stay on one connection (see main): the lock timeout and the duplicates temp table
    are connection state.
    """
    db.execute(_LOCK_TIMEOUT)
    params = {"placeholders": sorted(DEVICE_MODEL_PLACEHOLDERS), "platforms": list(GOOGLE_PLATFORMS)}
    renamed = merged = failed = 0
    for row in db.execute(_RENAME_CANDIDATES, params).mappings().all():
        src: UUID = row["id"]
        target = db.execute(
            _TARGET,
            {
                "user_id": row["user_id"],
                "provider": row["provider"],
                "src": src,
                "model": row["new_model"],
                "source": row["new_source"],
            },
        ).scalar()
        if target is None:
            steps = [(_RENAME, {"src": src, "model": row["new_model"], "source": row["new_source"]})]
        else:
            steps = [(step, {"src": src, "tgt": target}) for step in _MERGE_STEPS]
        if not dry_run:
            # One bad source (e.g. a row a concurrent sync just wrote) must not stop the others;
            # its committed batches stay and the next run finishes it
            moved_days = []
            try:
                if target is not None:
                    moved_days = [row.day for row in db.execute(_SAMPLE_DAYS, {"src": src})]
                    for statements in _BATCHES:
                        _move_in_batches(db, statements, src, target)
                for query, query_params in steps:
                    db.execute(query, query_params)
                db.commit()
                if target is not None and moved_days:
                    _queue_rollup(target, moved_days)
            except SQLAlchemyError as e:
                db.rollback()
                failed += 1
                log_and_capture_error(
                    e, logger, f"Skipped merging data source {src}: {e}", extra={"data_source_id": str(src)}
                )
                if target is not None and moved_days:
                    _queue_rollup(target, moved_days)
                continue
        if target is None:
            renamed += 1
        else:
            merged += 1

    duplicates = 0
    if dry_run:
        duplicates = db.execute(_DUPLICATE_COUNT).scalar() or 0
    else:
        try:
            duplicates = _remove_duplicate_events(db)
        except SQLAlchemyError as e:
            db.rollback()
            failed += 1
            log_and_capture_error(e, logger, f"Skipped removing duplicate events: {e}")

    result = {
        "renamed_sources": renamed,
        "merged_sources": merged,
        "duplicate_events_removed": duplicates,
        "failed": failed,
    }
    verb = "Would" if dry_run else "Did"
    print(
        f"{verb}: rename {renamed} data source(s), merge {merged} into an existing one, "
        f"remove {duplicates} duplicate event(s)" + (f"; skipped {failed} that failed" if failed else "")
    )
    if dry_run:
        print("\nDry run — no changes made.")
    return result


def _migrate(db: Session, dry_run: bool) -> bool:
    result = merge_duplicate_data_sources(db, dry_run=dry_run)
    if dry_run:
        return False
    if not any(result.values()):
        print("Nothing to do — no split data sources or duplicate events found.")
    elif not result["failed"]:
        print("Done.")
    return not result["failed"]


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(db, "merge_duplicate_data_sources", lambda: _migrate(db, dry_run), dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
