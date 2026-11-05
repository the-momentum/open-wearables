#!/usr/bin/env python3
"""Repair the HealthKit condensed series stored before the SDK import dropped them (#1983).

The why and the decision rules are in app/services/sdk/condensed_series.py; this applies them to stored rows.

Reads the rows with a window (stored since #1931) inside the user's Apple workouts older than MIN_CONDENSED_AGE.
A restored original loses its window, so a re-run skips it, and its external id, so the series sent again finds
it covered and is dropped at ingest. Each data source is committed on its own and its days are queued for the
rollup. Runs once per instance (data_migration); a re-run changes nothing.

data_type_coverage is not narrowed: a deleted row starts within one window of the 2+ samples it covers, so the
span is at most one window early.

Known limits: a series stays when the user's workouts never reached OW, when it covers only part of its stored
originals, or when an old pod stores it during a rolling deploy after the run; webhooks already sent are not
retracted.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/repair_condensed_series.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/repair_condensed_series.py
"""

import argparse
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants.devices_map.device_types import APPLE_SOURCE_APP_PREFIX
from app.database import engine
from app.integrations.rollup_queue import mark_dirty_days
from app.repositories.data_point_series_repository import StoredWindow
from app.schemas.enums import EventCategory, ProviderName, get_series_type_id
from app.schemas.enums.series_types import get_series_type_from_id
from app.services.data_migration_service import data_migration_service
from app.services.sdk.condensed_series import CONDENSED_TYPES, MIN_CONDENSED_AGE, repair_action
from app.services.timeseries_service import timeseries_service
from app.utils.dates import local_date

PROGRESS_SECONDS = 30
LOOKUP_CHUNK = 2000

# A sync writing the same samples holds their rows; behind one, a statement fails and the next start
# retries instead of holding the startup
_LOCK_TIMEOUT = text("SET lock_timeout = '10s'")
# The planner's cost estimates for the per-workout lookups are far too high, so JIT would compile every execution
_NO_JIT = text("SET jit = off")
_SOURCES = text("""
    SELECT ds.id, ds.user_id, ds.source_app_id
    FROM data_source ds
    WHERE ds.source_app_id LIKE :prefix
    ORDER BY ds.id
""")
# The source's windowed rows inside the user's Apple workouts, each span once (a workout is often stored twice).
# OFFSET 0 bounds each lookup by its span; flattened, the planner scans the source. 1-minute margin: a series may
# start just before its workout. The lookup excludes the row by external id, which every SDK series has.
_SERIES = text("""
    SELECT s.id, s.series_type_definition_id, s.recorded_at, s.zone_offset, s.value, s.window_seconds, s.external_id
    FROM (
        SELECT DISTINCT er.start_datetime, er.end_datetime
        FROM data_source wds
        JOIN event_record er ON er.data_source_id = wds.id
        WHERE wds.user_id = :user_id AND wds.provider = :provider
          AND er.category = :category AND er.start_datetime < :before
    ) w
    CROSS JOIN LATERAL (
        SELECT id, series_type_definition_id, recorded_at, zone_offset, value, window_seconds, external_id
        FROM series_sample
        WHERE data_source_id = :source_id
          AND series_type_definition_id = ANY(:types)
          AND recorded_at >= w.start_datetime - interval '1 minute'
          AND recorded_at < LEAST(w.end_datetime, :before)
          AND window_seconds IS NOT NULL
          AND external_id IS NOT NULL
        OFFSET 0
    ) s
""")
_RESTORE = text("UPDATE series_sample SET value = :value, window_seconds = NULL, external_id = NULL WHERE id = :id")
_DELETE = text("DELETE FROM series_sample WHERE id = ANY(:ids)")


def repair_condensed_series(db: Session, *, dry_run: bool, now: datetime | None = None) -> Counter[str]:
    """Repairs and commits one data source at a time (nothing on a dry run). Returns the rows by action."""
    params = {
        "types": sorted(get_series_type_id(series_type) for series_type in CONDENSED_TYPES),
        "before": (now or datetime.now(timezone.utc)) - MIN_CONDENSED_AGE,
        "provider": ProviderName.APPLE.value,
        "category": EventCategory.WORKOUT.value,
    }
    done: Counter[str] = Counter()
    by_type: Counter[tuple[str, str]] = Counter()
    sources = db.execute(_SOURCES, {"prefix": f"{APPLE_SOURCE_APP_PREFIX}%"}).all()
    last_progress = time.monotonic()
    for index, (source_id, user_id, app_id) in enumerate(sources, start=1):
        if time.monotonic() - last_progress >= PROGRESS_SECONDS:
            last_progress = time.monotonic()
            print(f"Repairing condensed series: {index}/{len(sources)} sources, {dict(done)} so far...")
        restored: list[dict[str, UUID | Decimal]] = []
        deleted: list[UUID] = []
        days: set[tuple[UUID, date]] = set()
        seen: set[UUID] = set()
        candidates: list[Any] = []
        for row in db.execute(_SERIES, {**params, "source_id": source_id, "user_id": user_id}).all():
            if row.id not in seen:  # a row inside two overlapping workouts
                seen.add(row.id)
                candidates.append(row)
        for start in range(0, len(candidates), LOOKUP_CHUNK):
            chunk = candidates[start : start + LOOKUP_CHUNK]
            windows = [
                StoredWindow(
                    user_id=user_id,
                    source_app_id=app_id,
                    series_type_definition_id=row.series_type_definition_id,
                    start=row.recorded_at,
                    end=row.recorded_at + timedelta(seconds=row.window_seconds),
                    external_id=row.external_id,
                )
                for row in chunk
            ]
            for row, coverage in zip(chunk, timeseries_service.stored_in_windows(db, windows), strict=True):
                series_type = get_series_type_from_id(row.series_type_definition_id)
                if (action := repair_action(series_type, row.value, coverage)) is None:
                    continue
                repair, value = action
                done[repair] += 1
                by_type[(series_type.value, repair)] += 1
                if repair == "kept":
                    continue
                if value is not None:
                    restored.append({"id": row.id, "value": value})
                else:
                    deleted.append(row.id)
                days.add((source_id, local_date(row.recorded_at, row.zone_offset)))
        if dry_run or not days:
            continue
        if restored:
            db.execute(_RESTORE, restored)
        if deleted:
            db.execute(_DELETE, {"ids": deleted})
        mark_dirty_days(db, days)
        db.commit()
    verb = "Would repair" if dry_run else "Repaired"
    for type_name in sorted({name for name, _ in by_type}):
        counts = ", ".join(f"{by_type[(type_name, action)]} {action}" for action in ("restored", "deleted", "kept"))
        print(f"  {type_name}: {counts}")
    print(f"{verb} condensed series: {done['restored']} restored, {done['deleted']} deleted, {done['kept']} kept.")
    return done


def _migrate(db: Session, dry_run: bool) -> bool:
    repair_condensed_series(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        db.execute(_LOCK_TIMEOUT)
        db.execute(_NO_JIT)
        data_migration_service.run(db, "repair_condensed_series", lambda: _migrate(db, dry_run), dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
