#!/usr/bin/env python3
"""One-off: merge data sources split by unstable identity values, and drop duplicate events.

Phase 1 - identity values the extraction no longer writes. Rows whose device model is a
placeholder ("", "unknown" - Garmin edits), whose Google Health model is a platform name
(HEALTH_KIT, FITBIT, ...), or Polar rows without a source (sleep, before it set one) are
renamed to the identity live sync now resolves. When a row with that identity already exists,
everything is moved into it instead: events, samples, archive and health scores; records the
target already holds at the same key are dropped from the source first.

Phase 2 - the same event stored under two data sources of one user and provider (legacy
"apple" source vs the writer name, Garmin activities before and after the device was known).
The copy in the most specific source is kept (device id > app id > model > a real source name),
a score or sleep/workout/cycle details on a dropped copy move to the kept one when it lacks them,
and the rest are deleted (phase 1 does the same for the copies it drops). Samples are not
touched here: overlapping samples across sources are different writers, not duplicates.

Idempotent: renamed rows no longer match phase 1 and duplicates are gone, so re-runs are no-ops.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/merge_duplicate_data_sources.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/merge_duplicate_data_sources.py
"""

import argparse
from logging import getLogger
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.constants.devices_map.device_types import DEVICE_MODEL_PLACEHOLDERS
from app.database import SessionLocal
from app.utils.sentry_helpers import log_and_capture_error

logger = getLogger(__name__)

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

# Per-event detail tables, keyed by record_id and cascade-deleted with their event
_DETAIL_TABLES = ("sleep_details", "workout_details", "menstrual_cycle_details")

# Move a data source's records into another; conflicting copies in the source are dropped first.
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
        DELETE FROM event_record s USING event_record t
        WHERE s.data_source_id = :src AND t.data_source_id = :tgt
          AND t.start_datetime = s.start_datetime AND t.end_datetime = s.end_datetime
    """),
    text("UPDATE event_record SET data_source_id = :tgt WHERE data_source_id = :src"),
    text("""
        DELETE FROM data_point_series s USING data_point_series t
        WHERE s.data_source_id = :src AND t.data_source_id = :tgt
          AND t.series_type_definition_id = s.series_type_definition_id AND t.recorded_at = s.recorded_at
    """),
    text("UPDATE data_point_series SET data_source_id = :tgt WHERE data_source_id = :src"),
    text("""
        DELETE FROM data_point_series_archive s USING data_point_series_archive t
        WHERE s.data_source_id = :src AND t.data_source_id = :tgt
          AND t.series_type_definition_id = s.series_type_definition_id
          AND t.bucket_start_at = s.bucket_start_at AND t.aggregation_type = s.aggregation_type
    """),
    text("UPDATE data_point_series_archive SET data_source_id = :tgt WHERE data_source_id = :src"),
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
# Groups spanning several device ids are different devices' records, not copies, so they are left alone.
_RANKED_DUPLICATES = """
    WITH multi_device AS (
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
        WHERE NOT EXISTS (
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
_DUPLICATE_SCORES = text(
    _RANKED_DUPLICATES
    + """
    UPDATE health_score h SET event_record_id = r.keep_id
    FROM ranked r
    WHERE r.rn > 1 AND h.event_record_id = r.id
      AND NOT EXISTS (
          SELECT 1 FROM health_score h2
          WHERE h2.event_record_id = r.keep_id AND h2.provider = h.provider AND h2.category = h.category
      )
"""
)
# Details of the best-ranked dropped copy move to a kept event that has none
_DUPLICATE_DETAILS = [
    text(
        _RANKED_DUPLICATES
        + f"""
        UPDATE {table} d SET record_id = c.keep_id
        FROM (
            SELECT DISTINCT ON (r.keep_id) r.id, r.keep_id
            FROM ranked r JOIN {table} x ON x.record_id = r.id
            WHERE r.rn > 1 AND NOT EXISTS (SELECT 1 FROM {table} k WHERE k.record_id = r.keep_id)
            ORDER BY r.keep_id, r.rn
        ) c
        WHERE d.record_id = c.id
        """
    )
    for table in _DETAIL_TABLES
]
_DUPLICATE_DELETE = text(
    _RANKED_DUPLICATES + "DELETE FROM event_record e USING ranked r WHERE r.rn > 1 AND e.id = r.id"
)


def _rowcount(db: Session, query: TextClause, params: dict | None = None) -> int:
    return db.execute(query, params or {}).rowcount  # ty: ignore[unresolved-attribute]


def merge_duplicate_data_sources(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Run both phases. Does not commit — the caller owns the transaction."""
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
            # One bad source (e.g. a row a concurrent sync just wrote) must not roll back the others
            try:
                with db.begin_nested():
                    for query, query_params in steps:
                        db.execute(query, query_params)
            except SQLAlchemyError as e:
                failed += 1
                log_and_capture_error(
                    e, logger, f"Skipped merging data source {src}: {e}", extra={"data_source_id": str(src)}
                )
                continue
        if target is None:
            renamed += 1
        else:
            merged += 1

    duplicates = db.execute(_DUPLICATE_COUNT).scalar() or 0
    if not dry_run and duplicates:
        db.execute(_DUPLICATE_SCORES)
        for query in _DUPLICATE_DETAILS:
            db.execute(query)
        duplicates = _rowcount(db, _DUPLICATE_DELETE)

    result = {"renamed_sources": renamed, "merged_sources": merged, "duplicate_events_removed": duplicates}
    verb = "Would" if dry_run else "Did"
    print(
        f"{verb}: rename {renamed} data source(s), merge {merged} into an existing one, "
        f"remove {duplicates} duplicate event(s)" + (f"; skipped {failed} that failed" if failed else "")
    )
    if dry_run:
        print("\nDry run — no changes made.")
    return result


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        result = merge_duplicate_data_sources(db, dry_run=dry_run)
        if dry_run:
            return
        if not any(result.values()):
            print("Nothing to do — no split data sources or duplicate events found.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
