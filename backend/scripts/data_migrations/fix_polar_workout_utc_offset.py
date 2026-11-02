#!/usr/bin/env python3
"""Move stored Polar workouts to the UTC time they happened at.

Polar sends a workout's ``start_time`` as naive local time plus ``start_time_utc_offset`` in
minutes. Ingestion added the offset instead of subtracting it, so every stored workout sits
twice its offset in the future.

Each connected user's exercise list is read once, the list the sync reads (``/v3/exercises``),
which keeps the calls far below Polar's instance-wide rate limit. A workout on it gets its start
recomputed from Polar's JSON, so a row the fixed ingestion already wrote stays where it is. One
not on it, or whose user has no active connection or a token Polar refuses (401/403), can't have
been written by the fixed ingestion, since the sync only stores what that list returns: it is
moved back by twice its stored ``zone_offset``. One without a ``zone_offset`` (stored before
#608) is left alone and reported.

``event_record`` is unique on ``(data_source_id, start_datetime, end_datetime)``, not on
``external_id``, so a sync on the fixed code may already have stored the corrected copy. The
stale row is then deleted rather than moved onto it; a different workout on that slot is never
deleted, only reported.

Moved and deleted workouts have their old and new local days queued for the rollup, which
recomputes their session statistics, and their data type coverage refreshed.

Runs once per instance (``data_migration``), in one transaction with the record of the run:
moving by the offset is not idempotent, so a run that fails commits nothing and the next
startup tries again. Polar is read before anything is written, since a token refresh commits
the session. Any Polar failure other than 401/403 aborts the run.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/fix_polar_workout_utc_offset.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/fix_polar_workout_utc_offset.py
"""

import argparse
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.database import engine
from app.integrations.rollup_queue import mark_dirty_days
from app.repositories.data_type_coverage_repository import EventKey, data_type_coverage_repository
from app.repositories.event_record_repository import local_days
from app.schemas.enums import EventCategory
from app.services.data_migration_service import data_migration_service
from app.services.providers.factory import ProviderFactory
from app.services.providers.polar.workouts import PolarWorkouts
from app.utils.dates import iso_to_timezone

PROVIDER = "polar"

_EXERCISE_FIELDS = {"id", "start_time", "start_time_utc_offset", "duration"}

# A token Polar refuses: the sync gets these too, so it can't have stored the workouts on the fixed code
_REFUSED = {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}

_SELECT_WORKOUTS = text("""
    SELECT er.id, er.external_id, er.data_source_id, ds.user_id, er.start_datetime, er.end_datetime,
           er.zone_offset,
           EXISTS (
               SELECT 1 FROM user_connection uc
               WHERE uc.user_id = ds.user_id AND uc.provider = :provider AND uc.status = 'active'
           ) AS connected
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE er.category = :category AND ds.provider = :provider
    ORDER BY er.start_datetime DESC
""")

# Whatever already sits on the corrected unique key, if anything
_OCCUPANT = text("""
    SELECT id, external_id FROM event_record
    WHERE data_source_id = :data_source_id AND start_datetime = :start AND end_datetime = :end
""")

_UPDATE_TIMES = text("UPDATE event_record SET start_datetime = :start, end_datetime = :end WHERE id = :id")
# Its detail, health scores and aggregates go with it (ON DELETE CASCADE)
_DELETE_ROW = text("DELETE FROM event_record WHERE id = :id")


def fix_polar_workout_times(db: Session, workouts_api: PolarWorkouts, *, dry_run: bool) -> dict[str, int]:
    """Correct every stored Polar workout. Does not commit; the caller owns the transaction."""
    counts = {
        "corrected": 0,
        "corrected_from_offset": 0,
        "duplicate_dropped": 0,
        "already_correct": 0,
        "no_offset": 0,
        "blocked": 0,
    }
    rows = db.execute(_SELECT_WORKOUTS, {"provider": PROVIDER, "category": EventCategory.WORKOUT}).all()
    # Read before any write: a token refresh commits the session
    served = {
        user_id: _served_exercises(workouts_api, db, user_id) for user_id in {r.user_id for r in rows if r.connected}
    }

    days: list[tuple[UUID, date]] = []
    coverage: set[EventKey] = set()
    for row in rows:
        exercise = served.get(row.user_id, {}).get(row.external_id)
        corrected = _times_from_exercise(workouts_api, exercise) if exercise else None
        from_offset = corrected is None
        if from_offset:
            corrected = _times_from_offset(row)
        if corrected is None:
            counts["no_offset"] += 1
            continue

        start, end = corrected
        if start == row.start_datetime:
            counts["already_correct"] += 1
            continue

        occupant = db.execute(_OCCUPANT, {"data_source_id": row.data_source_id, "start": start, "end": end}).first()
        if occupant is not None and occupant.external_id != row.external_id:
            print(f"  {row.external_id}: {start} is taken by {occupant.external_id}, left alone")
            counts["blocked"] += 1
            continue

        if occupant is not None:
            # A sync on the fixed code already stored the corrected copy
            counts["duplicate_dropped"] += 1
            if not dry_run:
                db.execute(_DELETE_ROW, {"id": row.id})
        else:
            counts["corrected_from_offset" if from_offset else "corrected"] += 1
            if not dry_run:
                db.execute(_UPDATE_TIMES, {"id": row.id, "start": start, "end": end})
        days += local_days(row.data_source_id, row.start_datetime, row.end_datetime, row.zone_offset)
        days += local_days(row.data_source_id, start, end, row.zone_offset)
        coverage.add((row.user_id, PROVIDER, EventCategory.WORKOUT))

    if not dry_run:
        mark_dirty_days(db, days)
        data_type_coverage_repository.refresh_events(db, coverage)
    print(f"{len(rows)} {PROVIDER} workouts: " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    return counts


def _served_exercises(workouts_api: PolarWorkouts, db: Session, user_id: UUID) -> dict[str, dict]:
    """The exercises Polar still lists for the user, by id; none if it refuses the token."""
    try:
        exercises = workouts_api.get_workouts_from_api(db, user_id) or []
    except HTTPException as exc:
        if exc.status_code in _REFUSED:
            return {}
        raise
    # One the sync couldn't parse either counts as not listed
    return {str(exercise["id"]): exercise for exercise in exercises if exercise.keys() >= _EXERCISE_FIELDS}


def _times_from_exercise(workouts_api: PolarWorkouts, exercise: dict) -> tuple[datetime, datetime]:
    """Start and end recomputed from Polar's exercise JSON."""
    start, end = workouts_api._extract_dates_with_offset(
        exercise["start_time"],
        int(exercise["start_time_utc_offset"]),
        exercise["duration"],
    )
    return start.replace(tzinfo=timezone.utc), end.replace(tzinfo=timezone.utc)


def _times_from_offset(row: Row[Any]) -> tuple[datetime, datetime] | None:
    """Start and end moved back by twice the stored offset; None without one."""
    if row.zone_offset is None:
        return None
    shift = 2 * (iso_to_timezone(row.zone_offset).utcoffset(None) or timedelta(0))
    return row.start_datetime - shift, row.end_datetime - shift


def _migrate(db: Session, workouts_api: PolarWorkouts, dry_run: bool) -> bool:
    fix_polar_workout_times(db, workouts_api, dry_run=dry_run)
    if dry_run:
        print("Dry run, no changes made.")
    return not dry_run


def main(dry_run: bool) -> None:
    workouts_api = ProviderFactory().get_provider(PROVIDER).workouts
    if not isinstance(workouts_api, PolarWorkouts):
        raise RuntimeError("Polar strategy has no PolarWorkouts template")
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(
            db, "fix_polar_workout_utc_offset", lambda: _migrate(db, workouts_api, dry_run), dry_run=dry_run
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    main(dry_run=parser.parse_args().dry_run)
