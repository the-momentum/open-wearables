#!/usr/bin/env python3
"""Re-point stored Polar workouts at the UTC instant they actually happened.

Polar's exercise JSON gives a naive LOCAL ``start_time`` plus ``start_time_utc_offset``
in minutes, so UTC is local MINUS the offset. ``_extract_dates_with_offset`` used to add
it, which stored every exercise ``2 x offset`` in the future.

Run this together with that fix, not later. ``event_record`` dedupes on
``(data_source_id, start_datetime, end_datetime)``, not on ``external_id``, so once the
fix is live the next sync computes the corrected start, finds no row at that time and
inserts a second copy of every exercise Polar still returns. Correcting the stored rows
first makes the sync land on them instead. If a sync already ran, the second copy is
already there: the stale row is then dropped rather than moved onto it, since moving it
would collide with the copy's unique key.

A row is only at risk of that duplicate if the sync can still fetch it, so:

- users without an active Polar connection are skipped outright (the sync will not
  fetch their exercises, and every call would just 401);
- a 404 means Polar no longer serves the exercise, and a 401/403 means this token
  cannot fetch it; the sync cannot either, so both are skipped and reported;
- any other failure aborts. Leaving that row uncorrected would let the next
  successful sync duplicate it. Everything runs in one transaction, so an abort
  commits nothing, and the script is safe to re-run.

Idempotent: each start is recomputed from Polar's own JSON and written as an absolute
value, so a re-run changes nothing. It calls Polar once per stored workout, so it is a
one-off rather than something to run on every startup.

Usage:
    uv run python scripts/data_migrations/fix_polar_workout_utc_offset.py --dry-run
    uv run python scripts/data_migrations/fix_polar_workout_utc_offset.py
"""

import argparse
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory
from app.services.providers.polar.workouts import PolarWorkouts

PROVIDER = "polar"

# Statuses that mean "the sync cannot fetch this either", so skipping is safe.
_UNFETCHABLE = {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}

_SELECT_WORKOUTS = text("""
    SELECT er.id, er.external_id, er.data_source_id, ds.user_id, er.start_datetime
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE er.category = 'workout' AND ds.provider = :provider
      AND EXISTS (
        SELECT 1 FROM user_connection uc
        WHERE uc.user_id = ds.user_id AND uc.provider = :provider AND uc.status = 'active'
      )
    ORDER BY er.start_datetime DESC
""")

_COUNT_INACTIVE = text("""
    SELECT count(*)
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE er.category = 'workout' AND ds.provider = :provider
      AND NOT EXISTS (
        SELECT 1 FROM user_connection uc
        WHERE uc.user_id = ds.user_id AND uc.provider = :provider AND uc.status = 'active'
      )
""")

# Whatever already sits on the corrected unique key, if anything.
_OCCUPANT = text("""
    SELECT id, external_id FROM event_record
    WHERE data_source_id = :data_source_id AND start_datetime = :start AND end_datetime = :end
""")

_UPDATE_TIMES = text("UPDATE event_record SET start_datetime = :start, end_datetime = :end WHERE id = :id")
# Its detail and health scores go with it (ON DELETE CASCADE).
_DELETE_ROW = text("DELETE FROM event_record WHERE id = :id")


def fix_polar_workout_times(db: Session, workouts_api: PolarWorkouts, *, dry_run: bool) -> dict[str, int]:
    """Correct every reachable Polar workout. Does not commit; the caller owns the transaction."""
    counts = {"corrected": 0, "duplicate_dropped": 0, "already_correct": 0, "unfetchable": 0, "blocked": 0}

    inactive = db.execute(_COUNT_INACTIVE, {"provider": PROVIDER}).scalar() or 0
    rows = db.execute(_SELECT_WORKOUTS, {"provider": PROVIDER}).all()
    print(f"{len(rows)} {PROVIDER} workouts with an active connection ({inactive} without one, skipped)\n")

    for row in rows:
        corrected = _corrected_times(workouts_api, db, row)
        if corrected is None:
            counts["unfetchable"] += 1
            print(f"  {row.external_id}: Polar will not serve it to this token, left alone")
            continue

        start, end = corrected
        if start == row.start_datetime:
            counts["already_correct"] += 1
            continue

        occupant = db.execute(_OCCUPANT, {"data_source_id": row.data_source_id, "start": start, "end": end}).first()
        if occupant is not None and occupant.external_id == row.external_id:
            # A sync on the fixed code already inserted the corrected copy.
            print(f"  {row.external_id}: corrected copy already exists, dropping the stale row")
            if not dry_run:
                db.execute(_DELETE_ROW, {"id": row.id})
            counts["duplicate_dropped"] += 1
            continue
        if occupant is not None:
            # Never delete a different workout to make room.
            print(f"  {row.external_id}: {start} is taken by {occupant.external_id}, left alone")
            counts["blocked"] += 1
            continue

        print(f"  {row.external_id}: {row.start_datetime} -> {start}")
        if not dry_run:
            db.execute(_UPDATE_TIMES, {"id": row.id, "start": start, "end": end})
        counts["corrected"] += 1

    print("\n" + "  ".join(f"{k}={v}" for k, v in counts.items()))
    return counts


def main(*, dry_run: bool) -> None:
    workouts_api = ProviderFactory().get_provider(PROVIDER).workouts
    if not isinstance(workouts_api, PolarWorkouts):
        raise RuntimeError("Polar strategy has no PolarWorkouts template")
    with SessionLocal() as db:
        fix_polar_workout_times(db, workouts_api, dry_run=dry_run)
        if dry_run:
            print("Dry run, no changes made.")
            return
        db.commit()


def _corrected_times(workouts_api: PolarWorkouts, db: Session, row: Row[Any]) -> tuple | None:
    """Recompute start/end from Polar's own JSON; None if Polar will not serve it.

    Anything other than 401/403/404 propagates and aborts the run, see the module docstring.
    """
    try:
        raw = workouts_api.get_exercise_detail(db, UUID(str(row.user_id)), row.external_id)
    except HTTPException as exc:
        if exc.status_code in _UNFETCHABLE:
            return None
        raise
    if not raw or not raw.get("start_time"):
        return None
    start, end = workouts_api._extract_dates_with_offset(
        raw["start_time"],
        int(raw["start_time_utc_offset"]),
        raw["duration"],
    )
    tz = row.start_datetime.tzinfo
    return start.replace(tzinfo=tz), end.replace(tzinfo=tz)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    main(dry_run=parser.parse_args().dry_run)
