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
user's Garmin ``garmin_body_battery`` samples in that window, which hold every push. A score is
only ever raised. Days whose samples retention deleted keep their score.

Runs once per instance (``data_migration``): one pass collects the scores to raise, then
committed batches raise them.

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

_BATCH_SIZE = 10_000

_LOW_PEAKS = """
    WITH days AS (
        SELECT id, user_id, value, recorded_at AS day_start,
               lead(recorded_at) OVER (PARTITION BY user_id ORDER BY recorded_at) AS next_start
        FROM health_score
        WHERE provider = :provider AND category = :category
    )
    SELECT days.id, peak.value AS peak
    FROM days
    CROSS JOIN LATERAL (
        SELECT max(s.value) AS value
        FROM series_sample s
        JOIN data_source ds ON ds.id = s.data_source_id
        WHERE ds.user_id = days.user_id
          AND ds.provider = :provider
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
# Collected in one pass into a session temp table, so batches cost a key lookup each and not a
# rescan of the samples; the session must stay on one connection (see main)
_DROP = text("DROP TABLE IF EXISTS low_body_battery_peaks")
_COLLECT = text(f"CREATE TEMP TABLE low_body_battery_peaks AS {_LOW_PEAKS}")
_INDEX = text("CREATE INDEX ON low_body_battery_peaks (id)")
_NEXT = text("SELECT id FROM low_body_battery_peaks ORDER BY id LIMIT :batch_size")
# Only ever up: ingestion may have raised a score past its collected peak in the meantime
_RAISE = text("""
    UPDATE health_score hs SET value = low.peak
    FROM low_body_battery_peaks low
    WHERE hs.id = low.id AND low.id = ANY(:ids) AND low.peak > hs.value
""")
_FORGET = text("DELETE FROM low_body_battery_peaks WHERE id = ANY(:ids)")


def raise_garmin_body_battery_peaks(db: Session, *, dry_run: bool) -> int:
    """Commits per batch, so an interrupted run keeps what it raised."""
    params = {
        "provider": ProviderName.GARMIN.value,
        "category": HealthScoreCategory.BODY_BATTERY.value,
        "series_type_id": get_series_type_id(SeriesType.garmin_body_battery),
    }
    if dry_run:
        found = db.execute(_COUNT, params).scalar() or 0
        print(f"Would raise {found} Garmin body battery score(s).\n\nDry run: no changes made.")
        return found

    db.execute(_DROP)
    db.execute(_COLLECT, params)
    db.execute(_INDEX)
    db.commit()
    raised = 0
    while ids := list(db.execute(_NEXT, {"batch_size": _BATCH_SIZE}).scalars()):
        raised += db.execute(_RAISE, {"ids": ids}).rowcount  # ty: ignore[unresolved-attribute]
        db.execute(_FORGET, {"ids": ids})
        db.commit()
    db.execute(_DROP)
    db.commit()
    print(f"Raised {raised} Garmin body battery score(s).")
    return raised


def _migrate(db: Session, dry_run: bool) -> bool:
    raise_garmin_body_battery_peaks(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(
            db, "raise_garmin_body_battery_peaks", lambda: _migrate(db, dry_run), dry_run=dry_run
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
