#!/usr/bin/env python3
"""Raise each Garmin body battery score to the highest body battery sample of its day.

The daily ``body_battery`` score is the highest value of a stressDetails summary. Garmin sends a
day's summary again, with more data, after every sync, but the score was inserted with ON
CONFLICT DO NOTHING, so it kept the peak of the day's first push: usually the hours after
midnight, before the battery charged overnight. Ingestion now keeps the highest value of every
push, and this raises the scores already stored.

A score's day runs from its ``recorded_at``, the summary's start, to the start of the user's next
body battery score when that comes within 25 hours, so a 23- or 25-hour day (a daylight-saving
change, or travel) ends where the next one starts; otherwise it lasts 24 hours. Its samples are the
user's Garmin ``garmin_body_battery`` samples in that window. A sample keeps the latest value pushed
for its timestamp, so a peak Garmin later revised down is gone and the score is raised only to what
the samples still hold. A score is only ever raised. Days whose samples retention deleted keep their
score.

Runs once per instance (``data_migration``), one committed statement per Garmin user.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/raise_garmin_body_battery_peaks.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/raise_garmin_body_battery_peaks.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.schemas.enums import HealthScoreCategory, ProviderName, SeriesType, get_series_type_id
from app.services.data_migration_service import data_migration_service

_USERS = text("""
    SELECT user_id, array_agg(id) FROM data_source
    WHERE provider = :provider
    GROUP BY user_id ORDER BY user_id
""")
# Per user, with the user's Garmin sources bound, so each day is one range of the (source, type, time)
# index and every statement is short: no snapshot held across the whole history, no table-wide scan
_LOW_PEAKS = """
    WITH days AS (
        SELECT id, value, recorded_at AS day_start,
               lead(recorded_at) OVER (ORDER BY recorded_at) AS next_start
        FROM health_score
        WHERE user_id = :user_id AND provider = :provider AND category = :category
    )
    SELECT days.id, peak.value AS peak
    FROM days
    CROSS JOIN LATERAL (
        SELECT max(s.value) AS value
        FROM series_sample s
        WHERE s.data_source_id = ANY(:source_ids)
          AND s.series_type_definition_id = :series_type_id
          AND s.recorded_at >= days.day_start
          AND s.recorded_at < CASE
              WHEN days.next_start <= days.day_start + interval '25 hours' THEN days.next_start
              ELSE days.day_start + interval '24 hours'
          END
    ) peak
    WHERE peak.value > days.value
"""
_COUNT = text(f"SELECT count(*) FROM ({_LOW_PEAKS}) low_peaks")
# Only ever up: ingestion may have raised a score past its peak in the meantime
_RAISE = text(f"""
    UPDATE health_score hs SET value = low.peak
    FROM ({_LOW_PEAKS}) low
    WHERE hs.id = low.id AND low.peak > hs.value
""")
# A sync writing the same scores holds their rows; behind one, a statement fails and the next start
# retries instead of holding the startup
_LOCK_TIMEOUT = text("SET lock_timeout = '10s'")


def raise_garmin_body_battery_peaks(db: Session, *, dry_run: bool) -> int:
    """Commits per user, so an interrupted run keeps what it raised."""
    params = {
        "provider": ProviderName.GARMIN.value,
        "category": HealthScoreCategory.BODY_BATTERY.value,
        "series_type_id": get_series_type_id(SeriesType.garmin_body_battery),
    }
    statement = _COUNT if dry_run else _RAISE
    found = 0
    for user_id, source_ids in db.execute(_USERS, params).all():
        result = db.execute(statement, {**params, "user_id": user_id, "source_ids": source_ids})
        found += (result.scalar() or 0) if dry_run else result.rowcount  # ty: ignore[unresolved-attribute]
        if not dry_run:
            db.commit()
    if dry_run:
        print(f"Would raise {found} Garmin body battery score(s).\n\nDry run: no changes made.")
    else:
        print(f"Raised {found} Garmin body battery score(s).")
    return found


def _migrate(db: Session, dry_run: bool) -> bool:
    raise_garmin_body_battery_peaks(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        db.execute(_LOCK_TIMEOUT)
        data_migration_service.run(
            db, "raise_garmin_body_battery_peaks", lambda: _migrate(db, dry_run), dry_run=dry_run
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
