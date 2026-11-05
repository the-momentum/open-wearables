#!/usr/bin/env python3
"""Repair the HealthKit condensed series stored over their originals before the SDK import dropped them (#1983).

HealthKit condenses the samples of first-party workouts a few months old into series and deletes the originals;
the SDK uploaded each series as a new sample. With data sources keyed by the Watch's hardware (#1781) a series
landed next to its originals, and one starting on an original replaced its value. The import now drops such
series; this repairs the ones stored before.

Only rows with a window are read: they were stored since samples kept one (#1931), and older rows can't be told
apart from originals. HealthKit condenses only the samples of first-party workouts, so only rows inside one of the
user's Apple workouts older than MIN_CONDENSED_AGE are read. A row is a series when it is an Apple device's sample
of a type HealthKit condenses, and its window covers at least MIN_COVERED other stored samples of its type
from the same writer app:

- energy and distance: its value is the sum of what it covers plus at most twice the largest of those. What it has
  over the sum is the original it replaced: the row gets that value back, without a window. With nothing over the
  sum (or a little below it, as at ingest: SUM_TOLERANCE), the row is deleted.
- heart rate: the row is deleted; the reading it replaced can't be recovered.

A restored row loses its external id too: a series sent again then finds the restored original covered and is
dropped at ingest. The data type coverage needs no narrowing: a deleted row sits next to 2+ stored samples of the
same user, provider and type, so the span moves by less than one window at most, and no reader relies on that.

Known limits: a series of a user whose workouts never reached OW stays, and two copies of one series in sibling
sources cover each other and are both kept.

Each data source is repaired and committed on its own, and its days are queued for the rollup. Runs once per
instance (data_migration); a repaired row has no window and a deleted one is gone, so a re-run changes nothing.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/repair_condensed_series.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/repair_condensed_series.py
"""

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants.devices_map.device_types import APPLE_SOURCE_APP_PREFIX
from app.database import engine
from app.integrations.rollup_queue import mark_dirty_days
from app.schemas.enums import AggregationMethod, EventCategory, ProviderName, get_series_type_id
from app.schemas.enums.aggregation_method import get_aggregation_method
from app.schemas.enums.series_types import get_series_type_from_id
from app.services.data_migration_service import data_migration_service
from app.services.sdk.condensed_series import CONDENSED_TYPES, MIN_CONDENSED_AGE, MIN_COVERED, SUM_TOLERANCE
from app.utils.dates import local_date

# Above this, what a series has over the samples it covers is an original it replaced. Below the sum, a series is
# kept only beyond SUM_TOLERANCE, as at ingest.
REPLACED_MIN = Decimal("0.001")
PROGRESS_EVERY = 100

Repair = Literal["restored", "deleted", "kept"]

# A sync writing the same samples holds their rows; behind one, a statement fails and the next start
# retries instead of holding the startup
_LOCK_TIMEOUT = text("SET lock_timeout = '10s'")
# The planner's cost estimates for the per-workout lookups are far too high, so JIT would compile every execution
_NO_JIT = text("SET jit = off")
# Each Apple device's source with the sources of the same writer app: a series can be filed under another model
_SOURCES = text("""
    SELECT ds.id, ds.user_id, array_agg(sibling.id) AS siblings
    FROM data_source ds
    JOIN data_source sibling ON sibling.user_id = ds.user_id AND sibling.source_app_id = ds.source_app_id
    WHERE ds.source_app_id LIKE :prefix
    GROUP BY ds.id, ds.user_id
    ORDER BY ds.id
""")
# The source's rows inside the user's Apple workouts, and what each covers among the siblings' samples. OFFSET 0 keeps
# each LATERAL from being flattened: flattened, the planner reads all of the source's rows (or all of event_record)
# and filters by workout afterwards, instead of bounding the index by each workout's span. A series may start just
# before its workout, hence the margin; the decision rule still guards what the wider span picks up.
_SERIES = text("""
    SELECT s.id, s.series_type_definition_id, s.recorded_at, s.zone_offset, s.value, c.total, c.largest
    FROM data_source wds
    CROSS JOIN LATERAL (
        SELECT start_datetime, end_datetime FROM event_record
        WHERE data_source_id = wds.id AND category = :category AND start_datetime < :before
        OFFSET 0
    ) w
    CROSS JOIN LATERAL (
        SELECT id, series_type_definition_id, recorded_at, zone_offset, value, window_seconds FROM series_sample
        WHERE data_source_id = :source_id
          AND series_type_definition_id = ANY(:types)
          AND recorded_at >= w.start_datetime - interval '1 minute'
          AND recorded_at < LEAST(w.end_datetime, :before)
          AND window_seconds IS NOT NULL
        OFFSET 0
    ) s
    CROSS JOIN LATERAL (
        SELECT count(*) AS inside, sum(o.value) AS total, max(o.value) AS largest
        FROM series_sample o
        WHERE o.data_source_id = ANY(CAST(:siblings AS uuid[]))
          AND o.series_type_definition_id = s.series_type_definition_id
          AND o.recorded_at >= s.recorded_at
          AND o.recorded_at < s.recorded_at + make_interval(secs => s.window_seconds)
          AND o.id <> s.id
    ) c
    WHERE wds.user_id = :user_id
      AND wds.provider = :provider
      AND c.inside >= :min_covered
""")
_RESTORE = text("UPDATE series_sample SET value = :value, window_seconds = NULL, external_id = NULL WHERE id = :id")
_DELETE = text("DELETE FROM series_sample WHERE id = ANY(:ids)")


def _repair(type_id: int, value: Decimal, total: Decimal, largest: Decimal) -> tuple[Repair, Decimal | None]:
    """What to do with a row that covers stored samples, and for a restored one the original's value."""
    if get_aggregation_method(get_series_type_from_id(type_id)) is not AggregationMethod.SUM:
        return "deleted", None
    replaced = value - total
    if replaced < -max(REPLACED_MIN, value * SUM_TOLERANCE) or replaced > 2 * largest:
        return "kept", None
    return ("restored", replaced) if replaced > REPLACED_MIN else ("deleted", None)


def repair_condensed_series(db: Session, *, dry_run: bool, now: datetime | None = None) -> Counter[str]:
    """Repairs and commits one data source at a time (nothing on a dry run). Returns the rows by action."""
    params = {
        "types": sorted(get_series_type_id(series_type) for series_type in CONDENSED_TYPES),
        "before": (now or datetime.now(timezone.utc)) - MIN_CONDENSED_AGE,
        "min_covered": MIN_COVERED,
        "provider": ProviderName.APPLE.value,
        "category": EventCategory.WORKOUT.value,
    }
    done: Counter[str] = Counter()
    by_type: Counter[tuple[str, str]] = Counter()
    sources = db.execute(_SOURCES, {"prefix": f"{APPLE_SOURCE_APP_PREFIX}%"}).all()
    for index, (source_id, user_id, siblings) in enumerate(sources, start=1):
        if index % PROGRESS_EVERY == 0:
            print(f"Repairing condensed series: {index}/{len(sources)} sources...")
        restored: list[dict[str, UUID | Decimal]] = []
        deleted: list[UUID] = []
        days: set[tuple[UUID, date]] = set()
        seen: set[UUID] = set()
        rows = db.execute(_SERIES, {**params, "source_id": source_id, "user_id": user_id, "siblings": siblings})
        for row in rows.all():
            if row.id in seen:  # inside two overlapping workouts
                continue
            seen.add(row.id)
            repair, value = _repair(row.series_type_definition_id, row.value, row.total, row.largest)
            done[repair] += 1
            by_type[(get_series_type_from_id(row.series_type_definition_id).value, repair)] += 1
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
