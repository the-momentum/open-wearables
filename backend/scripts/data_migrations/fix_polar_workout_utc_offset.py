#!/usr/bin/env python3
"""Re-point stored Polar workouts at the UTC instant they actually happened.

Polar's exercise JSON gives a naive LOCAL ``start_time`` plus ``start_time_utc_offset``
in minutes, so UTC is local MINUS the offset. ``_extract_dates_with_offset`` used to add
it, which stored every exercise ``2 x offset`` in the future.

Run this together with that fix, not later. ``event_record`` dedupes on
``(data_source_id, start_datetime, end_datetime)``, not on ``external_id``, so once the
fix is live the next sync computes the corrected start, finds no row at that time and
inserts a second copy of every exercise Polar still returns. Correcting the stored rows
first makes the sync land on them instead.

Idempotent: each start is recomputed from Polar's own JSON and written as an absolute
value, so a re-run changes nothing. Exercises Polar no longer serves are reported and
left alone; the sync cannot re-fetch them either, so they will not be duplicated.

It calls Polar once per stored workout, so it is a one-off rather than something to run
on every startup.

Usage:
    uv run python scripts/data_migrations/fix_polar_workout_utc_offset.py --dry-run
    uv run python scripts/data_migrations/fix_polar_workout_utc_offset.py
"""

import argparse
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory
from app.services.providers.polar.workouts import PolarWorkouts

PROVIDER = "polar"

_SELECT_WORKOUTS = text("""
    SELECT er.id, er.external_id, ds.user_id, er.start_datetime
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE er.category = 'workout' AND ds.provider = :provider
    ORDER BY er.start_datetime DESC
""")

_UPDATE_TIMES = text("UPDATE event_record SET start_datetime = :start, end_datetime = :end WHERE id = :id")


def run(*, dry_run: bool) -> dict[str, int]:
    workouts_api = ProviderFactory().get_provider(PROVIDER).workouts
    if not isinstance(workouts_api, PolarWorkouts):
        raise RuntimeError("Polar strategy has no PolarWorkouts template")
    counts = {"corrected": 0, "already_correct": 0, "unfetchable": 0}

    with SessionLocal() as db:
        rows = db.execute(_SELECT_WORKOUTS, {"provider": PROVIDER}).all()
        print(f"{len(rows)} {PROVIDER} workouts\n")

        for row in rows:
            corrected = _corrected_times(workouts_api, db, row)
            if corrected is None:
                counts["unfetchable"] += 1
                print(f"  {row.external_id}: Polar no longer serves it, left alone")
                continue

            start, end = corrected
            if start == row.start_datetime:
                counts["already_correct"] += 1
                continue

            print(f"  {row.external_id}: {row.start_datetime} -> {start}")
            if not dry_run:
                db.execute(_UPDATE_TIMES, {"id": row.id, "start": start, "end": end})
            counts["corrected"] += 1

        if dry_run:
            print("\nDry run, no changes made.")
        else:
            db.commit()

    print("\n" + "  ".join(f"{k}={v}" for k, v in counts.items()))
    return counts


def _corrected_times(workouts_api: PolarWorkouts, db: Session, row: Row[Any]) -> tuple | None:
    """Recompute start/end from Polar's own JSON, or None if it no longer serves it."""
    try:
        raw = workouts_api.get_exercise_detail(db, UUID(str(row.user_id)), row.external_id)
    except Exception:
        return None
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
    run(dry_run=parser.parse_args().dry_run)
