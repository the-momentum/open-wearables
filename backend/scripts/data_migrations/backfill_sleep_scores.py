#!/usr/bin/env python3
"""Backfill OW sleep scores for sessions that have none.

Mirrors the logic in fill_missing_sleep_scores_task but runs as a one-off
script with a configurable lookback window.  Useful after the
cc39513098b0 migration which wiped orphaned internal sleep scores.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_sleep_scores.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_sleep_scores.py
    docker compose exec app uv run python scripts/data_migrations/backfill_sleep_scores.py --days 90
"""

import argparse
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import text

from app.algorithms.config_algorithms import sleep_config
from app.config import settings
from app.database import SessionLocal
from app.schemas.enums import HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities.health_score import HealthScoreCreate, ScoreComponent
from app.services.health_score_service import health_score_service
from app.services.scores.sleep_service import sleep_score_service

# EventRecordQueryParams caps limit at 1000. The service formula is
# (chunk_size + rolling_window_nights) * 4, so solve for chunk_size:
_QUERY_LIMIT_CAP = 1000
_CHUNK_SIZE = _QUERY_LIMIT_CAP // 4 - sleep_config.rolling_window_nights

_MISSING_SCORES_QUERY = text("""
    SELECT DISTINCT
        ds.user_id,
        ds.id AS data_source_id,
        er.id AS record_id,
        (er.end_datetime + COALESCE(er.zone_offset, '+00:00')::interval)::date AS wake_date,
        (er.end_datetime + COALESCE(er.zone_offset, '+00:00')::interval) AS local_end_datetime
    FROM event_record er
    JOIN data_source ds   ON ds.id = er.data_source_id
    JOIN sleep_details sd ON sd.record_id = er.id
    LEFT JOIN health_score hs
           ON hs.sleep_record_id = er.id
          AND hs.category     = 'sleep'
          AND hs.provider     = 'internal'
    WHERE er.category = 'sleep'
      AND (sd.is_nap IS NULL OR sd.is_nap = false)
      AND sd.sleep_total_duration_minutes IS NOT NULL
      AND sd.sleep_total_duration_minutes > 0
      AND hs.id IS NULL
      AND er.start_datetime >= :cutoff
    ORDER BY ds.user_id, wake_date DESC
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill OW sleep scores for unscored sessions.")
    parser.add_argument(
        "--days",
        type=int,
        default=settings.score_backfill_days,
        help=f"How many days back to scan (default: {settings.score_backfill_days} from settings).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview affected sessions without saving scores.")
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    print(f"Cutoff: {cutoff.date()} ({args.days} days back)")

    with SessionLocal() as db:
        rows = db.execute(_MISSING_SCORES_QUERY, {"cutoff": cutoff}).fetchall()

        if not rows:
            print("No sessions missing scores.")
            return

        print(f"Found {len(rows)} session(s) missing scores.")

        if args.dry_run:
            print(f"\n{'User ID':<38} {'Record ID':<38} {'Wake Date':<12} {'Local End'}")
            print("-" * 110)
            for user_id, data_source_id, record_id, wake_date, local_end in rows:
                print(f"{user_id!s:<38} {record_id!s:<38} {wake_date!s:<12} {local_end!s}")
            print("\nDry run — no changes made.")
            return

        records_by_user: dict[UUID, list[tuple[UUID, UUID, date, datetime]]] = defaultdict(list)
        for user_id, data_source_id, record_id, wake_date, local_end in rows:
            records_by_user[user_id].append((record_id, data_source_id, wake_date, local_end))

        total_saved = 0
        total_skipped = 0

        for uid, record_wakes_extended in records_by_user.items():
            local_end_by_id: dict[UUID, datetime] = {rid: le for rid, _, _, le in record_wakes_extended}
            data_source_by_id: dict[UUID, UUID] = {rid: dsid for rid, dsid, _, _ in record_wakes_extended}

            for chunk_start in range(0, len(record_wakes_extended), _CHUNK_SIZE):
                chunk = record_wakes_extended[chunk_start : chunk_start + _CHUNK_SIZE]
                record_wakes = [(rid, wd) for rid, _, wd, _ in chunk]

                try:
                    scores_by_record = sleep_score_service.get_sleep_scores_for_records(db, uid, record_wakes)
                except Exception as e:
                    total_skipped += len(record_wakes)
                    print(f"ERROR: failed to fetch sleep data for user {uid}: {e}", file=sys.stderr)
                    continue

                if not scores_by_record:
                    total_skipped += len(record_wakes)
                    continue

                scores_to_save = [
                    HealthScoreCreate(
                        id=uuid4(),
                        user_id=uid,
                        data_source_id=data_source_by_id[record_id],
                        provider=ProviderName.INTERNAL,
                        category=HealthScoreCategory.SLEEP,
                        value=result.overall_score,
                        sleep_record_id=record_id,
                        recorded_at=local_end_by_id[record_id].replace(tzinfo=timezone.utc),
                        components={
                            "duration": ScoreComponent(value=result.breakdown.duration.score),
                            "stages": ScoreComponent(value=result.breakdown.stages.score),
                            "consistency": ScoreComponent(value=result.breakdown.consistency.score),
                            "interruptions": ScoreComponent(value=result.breakdown.interruptions.score),
                        },
                    )
                    for (record_id, _), result in scores_by_record.items()
                ]

                try:
                    health_score_service.bulk_create(db, scores_to_save)
                    db.commit()
                    total_saved += len(scores_to_save)
                    total_skipped += len(record_wakes) - len(scores_to_save)
                    chunk_end = chunk_start + len(chunk)
                    print(f"  user {uid} [{chunk_start + 1}-{chunk_end}]: saved {len(scores_to_save)} score(s)")
                except Exception as e:
                    db.rollback()
                    total_skipped += len(record_wakes)
                    print(f"ERROR: failed to save scores for user {uid}: {e}", file=sys.stderr)

        print(f"\nDone: {total_saved} saved, {total_skipped} skipped.")


if __name__ == "__main__":
    main()
