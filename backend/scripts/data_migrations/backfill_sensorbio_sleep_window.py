#!/usr/bin/env python3
"""Set stored Sensor Bio sleep sessions' duration and time in bed to the start-to-end window.

Sensor Bio stored time asleep (often 0) as ``event_record.duration_seconds`` and
``sleep_details.sleep_time_in_bed_minutes``, while every other provider stores the window there
and time asleep in ``sleep_total_duration_minutes``. Ingest now stores the window; this sets it
on sessions stored before. A re-sync cannot do it: the same window returns the existing record
without refreshing it.

An instance without a Sensor Bio ``data_source`` row stops after one lookup on that table and
never touches ``event_record``. Cheap and unrecorded: it also fixes sessions an old pod writes
during a rolling deploy.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_sensorbio_sleep_window.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_sensorbio_sleep_window.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.schemas.enums import ProviderName

_HAS_SOURCE = text("SELECT EXISTS (SELECT 1 FROM data_source WHERE provider = :provider)")
_WINDOW = "EXTRACT(EPOCH FROM er.end_datetime - er.start_datetime)::int"
_SESSIONS = f"""
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    LEFT JOIN sleep_details sd ON sd.record_id = er.id
    WHERE ds.provider = :provider
      AND er.category = 'sleep'
      AND er.end_datetime > er.start_datetime
      AND (
        er.duration_seconds IS DISTINCT FROM {_WINDOW}
        OR (sd.record_id IS NOT NULL AND sd.sleep_time_in_bed_minutes IS DISTINCT FROM {_WINDOW} / 60)
      )
"""
_COUNT = text(f"SELECT count(*) {_SESSIONS}")
_UPDATE_DURATION = text(
    f"""
    UPDATE event_record er
    SET duration_seconds = {_WINDOW}
    FROM data_source ds
    WHERE ds.id = er.data_source_id
      AND ds.provider = :provider
      AND er.category = 'sleep'
      AND er.end_datetime > er.start_datetime
      AND er.duration_seconds IS DISTINCT FROM {_WINDOW}
    """
)
_UPDATE_TIME_IN_BED = text(
    f"""
    UPDATE sleep_details sd
    SET sleep_time_in_bed_minutes = {_WINDOW} / 60
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE sd.record_id = er.id
      AND ds.provider = :provider
      AND er.category = 'sleep'
      AND er.end_datetime > er.start_datetime
      AND sd.sleep_time_in_bed_minutes IS DISTINCT FROM {_WINDOW} / 60
    """
)


def backfill_sensorbio_sleep_window(db: Session, *, dry_run: bool) -> int:
    """Does not commit; the caller owns the transaction. Returns the number of sessions changed."""
    params = {"provider": ProviderName.SENSORBIO.value}
    if not db.execute(_HAS_SOURCE, params).scalar():
        print("No Sensor Bio data source — nothing to do.")
        return 0
    found = db.execute(_COUNT, params).scalar() or 0
    if dry_run:
        print(f"Would set the window on {found} Sensor Bio sleep session(s).\n\nDry run — no changes made.")
        return found
    db.execute(_UPDATE_DURATION, params)
    db.execute(_UPDATE_TIME_IN_BED, params)
    print(f"Set the window on {found} Sensor Bio sleep session(s).")
    return found


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        backfill_sensorbio_sleep_window(db, dry_run=dry_run)
        if not dry_run:
            db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
