#!/usr/bin/env python3
"""Back-fill OW sleep scores for all existing users.

Run this once after deploying the sleep-score Celery task to seed scores for
users who had already synced data before the feature was introduced.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_sleep_scores.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_sleep_scores.py
    docker compose exec app uv run python scripts/data_migrations/backfill_sleep_scores.py --days-back 60
"""

import argparse
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config import settings
from app.database import SessionLocal
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities.health_score import HealthScoreCreate, ScoreComponent
from app.services.health_score_service import health_score_service
from app.services.scores.sleep_service import sleep_score_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Back-fill OW sleep scores for all users.")
    parser.add_argument("--dry-run", action="store_true", help="Preview counts without writing to the database.")
    parser.add_argument(
        "--days-back",
        type=int,
        default=settings.score_backfill_days,
        help=f"How many days back to calculate (default: {settings.score_backfill_days}).",
    )
    args = parser.parse_args()

    user_connection_repo = UserConnectionRepository()
    today = datetime.now(timezone.utc).date()
    dates = [today - timedelta(days=d) for d in range(1, args.days_back + 1)]

    with SessionLocal() as db:
        user_ids = user_connection_repo.get_all_active_users(db)
        print(f"Found {len(user_ids)} users with active connections.")
        print(f"Calculating scores for {args.days_back} days back ({dates[-1]} → {dates[0]}).")
        if args.dry_run:
            print("Dry run — no changes will be written.\n")

        total_saved = 0
        total_skipped = 0

        for uid in user_ids:
            try:
                scores_by_date = sleep_score_service.get_sleep_scores_for_date_range(db, uid, dates)
            except Exception as exc:
                print(f"  [{uid}] ERROR fetching data: {exc}")
                total_skipped += len(dates)
                continue

            if not scores_by_date:
                total_skipped += len(dates)
                continue

            scores_to_save = [
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=uid,
                    data_source_id=None,
                    provider=ProviderName.INTERNAL,
                    category=HealthScoreCategory.SLEEP,
                    value=result.overall_score,
                    recorded_at=datetime(d.year, d.month, d.day, tzinfo=timezone.utc),
                    components={
                        "duration": ScoreComponent(value=result.breakdown.duration.score),
                        "stages": ScoreComponent(value=result.breakdown.stages.score),
                        "consistency": ScoreComponent(value=result.breakdown.consistency.score),
                        "interruptions": ScoreComponent(value=result.breakdown.interruptions.score),
                    },
                )
                for d, result in scores_by_date.items()
            ]

            print(f"  [{uid}] {len(scores_to_save)} score(s) to save, {len(dates) - len(scores_to_save)} skipped.")

            if not args.dry_run:
                health_score_service.bulk_create(db, scores_to_save)
                db.commit()

            total_saved += len(scores_to_save)
            total_skipped += len(dates) - len(scores_to_save)

        print(f"\nDone. {total_saved} score(s) {'would be ' if args.dry_run else ''}saved, {total_skipped} skipped.")


if __name__ == "__main__":
    main()
