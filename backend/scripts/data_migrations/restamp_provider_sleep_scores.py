#!/usr/bin/env python3
"""Move Garmin, Polar and Whoop sleep scores from the night's start to its wake-up.

These providers' sleep scores were recorded at the start of the night, in UTC and with no zone
offset, so anything that groups scores by day (the panel, API clients) filed a night under the UTC
date of falling asleep. East of UTC, a user who falls asleep sometimes before and sometimes after
midnight UTC got two scores on one day and none on the next. Ingestion now records them at the
night's end with its zone offset, and this moves the scores already stored.

A score's night is the event record it links (Polar's, whose start a re-sync may have moved
since) or, for an unlinked score, the user's sleep record of the same provider that starts at the
score's ``recorded_at``. The score moves to the night's ``end_datetime`` and ``zone_offset``, which
is empty for Polar's sleep records and for Whoop's stored before ingestion read Whoop's
``timezone_offset``. A score whose night already has one at the wake-up, written by the fixed
ingestion, is deleted, and of two scores moving to the same time only the newest stays. Scores
without a matching night stay where they are.

Runs once per instance (``data_migration``): one pass collects the scores to move, then committed
batches move them.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/restamp_provider_sleep_scores.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/restamp_provider_sleep_scores.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.schemas.enums import HealthScoreCategory, ProviderName
from app.services.data_migration_service import data_migration_service

_BATCH_SIZE = 10_000
_PROVIDERS = [ProviderName.GARMIN.value, ProviderName.POLAR.value, ProviderName.WHOOP.value]

# A linked score finds its night by id, since a re-sync may have moved its start; an unlinked one sits at it.
# Two branches, not one join on an OR, so each probes its own index (the primary key, ix_event_record_source_time).
_AT_START = """
    SELECT DISTINCT ON (id) id, user_id, provider, data_source_id, category, created_at, wake_up, zone_offset
    FROM (
        SELECT hs.id, hs.user_id, hs.provider, hs.data_source_id, hs.category, hs.created_at, hs.recorded_at,
            er.end_datetime AS wake_up, er.zone_offset
        FROM health_score hs
        JOIN event_record er ON er.id = hs.event_record_id
        JOIN data_source ds ON ds.id = er.data_source_id AND ds.user_id = hs.user_id AND ds.provider = hs.provider
        WHERE hs.provider = ANY(:providers) AND hs.category = :category AND er.category = 'sleep'
        UNION ALL
        SELECT hs.id, hs.user_id, hs.provider, hs.data_source_id, hs.category, hs.created_at, hs.recorded_at,
            er.end_datetime, er.zone_offset
        FROM health_score hs
        JOIN data_source ds ON ds.user_id = hs.user_id AND ds.provider = hs.provider
        JOIN event_record er ON er.data_source_id = ds.id AND er.start_datetime = hs.recorded_at
        WHERE hs.provider = ANY(:providers) AND hs.category = :category AND er.category = 'sleep'
          AND hs.event_record_id IS NULL
    ) night
    WHERE recorded_at <> wake_up
    ORDER BY id, wake_up DESC
"""
_COUNT = text(f"SELECT count(*) FROM ({_AT_START}) at_start")
# Collected in one pass into a session temp table, so batches cost a key lookup each and not a
# rescan of the sleep records; the session must stay on one connection (see main)
_DROP = text("DROP TABLE IF EXISTS sleep_scores_at_start")
_COLLECT = text(f"CREATE TEMP TABLE sleep_scores_at_start AS {_AT_START}")
_INDEX = text("CREATE INDEX ON sleep_scores_at_start (id)")
# Moving a score onto a time another score of its key holds (#1877 added the source to the key) would
# break the unique key and fail every run, so the score already there stays, and of several moving to
# one time only the newest does
_DELETE_DUPLICATES = text("""
    WITH ranked AS (
        SELECT id, row_number() OVER (
            PARTITION BY user_id, provider, data_source_id, category, wake_up ORDER BY created_at DESC, id
        ) AS n
        FROM sleep_scores_at_start
    )
    DELETE FROM health_score hs
    USING sleep_scores_at_start s, ranked
    WHERE hs.id = s.id AND ranked.id = s.id
      AND (ranked.n > 1 OR EXISTS (
          SELECT 1 FROM health_score taken
          WHERE taken.user_id = s.user_id AND taken.provider = s.provider
            AND taken.data_source_id IS NOT DISTINCT FROM s.data_source_id
            AND taken.category = s.category AND taken.recorded_at = s.wake_up AND taken.id <> s.id
      ))
""")
_FORGET_DELETED = text(
    "DELETE FROM sleep_scores_at_start s WHERE NOT EXISTS (SELECT 1 FROM health_score hs WHERE hs.id = s.id)"
)
_NEXT = text("SELECT id FROM sleep_scores_at_start ORDER BY id LIMIT :batch_size")
_MOVE = text("""
    UPDATE health_score hs SET recorded_at = s.wake_up, zone_offset = s.zone_offset
    FROM sleep_scores_at_start s
    WHERE hs.id = s.id AND s.id = ANY(:ids)
""")
_FORGET = text("DELETE FROM sleep_scores_at_start WHERE id = ANY(:ids)")


def restamp_provider_sleep_scores(db: Session, *, dry_run: bool) -> int:
    """Commits per batch, so an interrupted run keeps what it moved."""
    params = {"providers": _PROVIDERS, "category": HealthScoreCategory.SLEEP.value}
    if dry_run:
        found = db.execute(_COUNT, params).scalar() or 0
        print(f"Would move {found} sleep score(s) to the wake-up.\n\nDry run: no changes made.")
        return found

    db.execute(_DROP)
    db.execute(_COLLECT, params)
    db.execute(_INDEX)
    deleted = db.execute(_DELETE_DUPLICATES).rowcount  # ty: ignore[unresolved-attribute]
    db.execute(_FORGET_DELETED)
    db.commit()
    moved = 0
    while ids := list(db.execute(_NEXT, {"batch_size": _BATCH_SIZE}).scalars()):
        moved += db.execute(_MOVE, {"ids": ids}).rowcount  # ty: ignore[unresolved-attribute]
        db.execute(_FORGET, {"ids": ids})
        db.commit()
    db.execute(_DROP)
    db.commit()
    print(f"Moved {moved} sleep score(s) to the wake-up, deleted {deleted} duplicate(s).")
    return moved


def _migrate(db: Session, dry_run: bool) -> bool:
    restamp_provider_sleep_scores(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(db, "restamp_provider_sleep_scores", lambda: _migrate(db, dry_run), dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
