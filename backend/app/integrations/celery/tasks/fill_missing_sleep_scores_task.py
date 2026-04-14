from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from logging import getLogger
from uuid import UUID, uuid4

from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.schemas.enums import HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities.health_score import HealthScoreCreate, ScoreComponent
from app.services.health_score_service import health_score_service
from app.services.scores.sleep_service import sleep_score_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured
from celery import shared_task

logger = getLogger(__name__)

# Find all non-nap sleep sessions that have no corresponding OW sleep score.
# The match is on user + calendar date (UTC) of start_datetime vs recorded_at.
# Limited to sessions within the configured backfill window to avoid scanning
# the entire history on every run.
_MISSING_SCORES_QUERY = text("""
    SELECT DISTINCT
        ds.user_id,
        (er.start_datetime + COALESCE(er.zone_offset, '+00:00')::interval)::date AS sleep_date
    FROM event_record er
    JOIN data_source ds   ON ds.id = er.data_source_id
    JOIN sleep_details sd ON sd.record_id = er.id
    LEFT JOIN health_score hs
           ON hs.user_id     = ds.user_id
          AND hs.category     = 'sleep'
          AND hs.provider     = 'internal'
          AND hs.recorded_at::date = (er.start_datetime + COALESCE(er.zone_offset, '+00:00')::interval)::date
    WHERE er.category = 'sleep'
      AND (sd.is_nap IS NULL OR sd.is_nap = false)
      AND sd.sleep_total_duration_minutes IS NOT NULL
      AND sd.sleep_total_duration_minutes > 0
      AND hs.id IS NULL
      AND er.start_datetime >= :cutoff
    ORDER BY ds.user_id, sleep_date DESC
""")


@shared_task
def fill_missing_sleep_scores() -> dict:
    """Find sleep sessions without an OW sleep score and calculate them.

    Runs frequently (every few minutes) so scores appear shortly after any sync
    path (periodic pull, webhook, SDK upload). Uses a LEFT JOIN to guarantee
    idempotency — already-scored sessions are never re-processed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.score_backfill_days)

    with SessionLocal() as db:
        rows = db.execute(_MISSING_SCORES_QUERY, {"cutoff": cutoff}).fetchall()

        if not rows:
            return {"saved": 0, "skipped": 0}

        # Group dates per user
        dates_by_user: dict[UUID, list[date]] = defaultdict(list)
        for user_id, sleep_date in rows:
            dates_by_user[UUID(str(user_id))].append(sleep_date)

        log_structured(
            logger,
            "info",
            f"Found {len(rows)} session(s) missing scores across {len(dates_by_user)} user(s)",
            task="fill_missing_sleep_scores",
        )

        total_saved = 0
        total_skipped = 0

        for uid, dates in dates_by_user.items():
            try:
                scores_by_date = sleep_score_service.get_sleep_scores_for_date_range(db, uid, dates)
            except Exception as e:
                total_skipped += len(dates)
                log_and_capture_error(
                    e,
                    logger,
                    f"Failed to fetch sleep data for user {uid}",
                    extra={"user_id": str(uid), "task": "fill_missing_sleep_scores"},
                )
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

            try:
                health_score_service.bulk_create(db, scores_to_save)
                db.commit()
                total_saved += len(scores_to_save)
                total_skipped += len(dates) - len(scores_to_save)
            except Exception as e:
                db.rollback()
                total_skipped += len(scores_to_save)
                log_and_capture_error(
                    e,
                    logger,
                    f"Failed to save sleep scores for user {uid}",
                    extra={"user_id": str(uid), "task": "fill_missing_sleep_scores"},
                )

        log_structured(
            logger,
            "info",
            f"Sleep score fill complete: {total_saved} saved, {total_skipped} skipped",
            task="fill_missing_sleep_scores",
            saved=total_saved,
            skipped=total_skipped,
        )

        return {"saved": total_saved, "skipped": total_skipped}
