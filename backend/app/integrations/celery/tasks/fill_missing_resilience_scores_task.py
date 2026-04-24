from collections import defaultdict
from datetime import date, datetime, timezone
from logging import getLogger
from uuid import UUID, uuid4

from celery import shared_task
from sqlalchemy import text

from app.algorithms.config_algorithms import resilience_config
from app.config import settings
from app.database import SessionLocal
from app.schemas.enums import HealthScoreCategory, ProviderName, SeriesType, get_series_type_id
from app.schemas.model_crud.activities.health_score import HealthScoreCreate, ScoreComponent
from app.services.health_score_service import health_score_service
from app.services.scores.resilience_service import resilience_score_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

_RMSSD_TYPE_ID = get_series_type_id(SeriesType.heart_rate_variability_rmssd)
_SDNN_TYPE_ID = get_series_type_id(SeriesType.heart_rate_variability_sdnn)

# Find all (user, reference_date) pairs that are missing an OW resilience score.
# active_users: users who have any RMSSD or SDNN data in the extended lookback window.
# We cross-join with a date series covering the backfill window and filter out any
# dates that already have a score, ensuring idempotency.
_MISSING_RESILIENCE_SCORES_QUERY = text("""
    SELECT DISTINCT
        active_users.user_id,
        gs.target_date::date AS reference_date
    FROM generate_series(
        CURRENT_DATE - :backfill_days * INTERVAL '1 day',
        CURRENT_DATE,
        INTERVAL '1 day'
    ) AS gs(target_date)
    CROSS JOIN (
        SELECT DISTINCT ds.user_id
        FROM data_point_series dp
        JOIN data_source ds ON ds.id = dp.data_source_id
        WHERE dp.series_type_definition_id IN (:rmssd_id, :sdnn_id)
          AND dp.recorded_at >= CURRENT_DATE - :data_lookback_days * INTERVAL '1 day'
    ) AS active_users
    LEFT JOIN health_score hs
           ON hs.user_id  = active_users.user_id
          AND hs.category = 'resilience'
          AND hs.provider = 'internal'
          AND hs.recorded_at::date = gs.target_date::date
    WHERE hs.id IS NULL
    ORDER BY active_users.user_id, reference_date DESC
""")


@shared_task
def fill_missing_resilience_scores() -> dict:
    """Find (user, date) pairs without an OW resilience score and calculate them.

    Runs frequently so scores appear shortly after any sync path that delivers
    HRV data. Uses a LEFT JOIN against generate_series to guarantee idempotency
    — already-scored dates are never re-processed.

    Only dates where the service returns a non-null hrv_cv are persisted.
    Dates where there is insufficient HRV data remain unscored so they are
    retried on the next run once more data arrives.
    """
    with SessionLocal() as db:
        rows = db.execute(
            _MISSING_RESILIENCE_SCORES_QUERY,
            {
                "backfill_days": settings.score_backfill_days,
                "rmssd_id": _RMSSD_TYPE_ID,
                "sdnn_id": _SDNN_TYPE_ID,
                "data_lookback_days": settings.score_backfill_days + resilience_config.lookback_days,
            },
        ).fetchall()

        if not rows:
            return {"saved": 0, "skipped": 0}

        # Group reference dates per user
        dates_by_user: dict[UUID, list[date]] = defaultdict(list)
        for user_id, reference_date in rows:
            dates_by_user[UUID(str(user_id))].append(reference_date)

        log_structured(
            logger,
            "info",
            f"Found {len(rows)} resilience score(s) missing across {len(dates_by_user)} user(s)",
            task="fill_missing_resilience_scores",
        )

        total_saved = 0
        total_skipped = 0

        for uid, reference_dates in dates_by_user.items():
            try:
                scores_by_date = resilience_score_service.get_hrv_cv_scores_for_date_range(db, uid, reference_dates)
            except Exception as e:
                total_skipped += len(reference_dates)
                log_and_capture_error(
                    e,
                    logger,
                    f"Failed to fetch HRV data for user {uid}",
                    extra={"user_id": str(uid), "task": "fill_missing_resilience_scores"},
                )
                continue

            scores_to_save = [
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=uid,
                    data_source_id=None,
                    provider=ProviderName.INTERNAL,
                    category=HealthScoreCategory.RESILIENCE,
                    value=result.hrv_cv,
                    recorded_at=datetime(ref_date.year, ref_date.month, ref_date.day, tzinfo=timezone.utc),
                    components={
                        "days_counted": ScoreComponent(value=result.days_counted),
                        "metric_type": ScoreComponent(qualifier=result.metric_type),
                    },
                )
                for ref_date, result in scores_by_date.items()
                if result.hrv_cv is not None
            ]

            # Dates with hrv_cv=None have insufficient data — leave unscored for retry.
            total_skipped += len(reference_dates) - len(scores_to_save)

            if not scores_to_save:
                continue

            try:
                health_score_service.bulk_create(db, scores_to_save)
                db.commit()
                total_saved += len(scores_to_save)
            except Exception as e:
                db.rollback()
                total_skipped += len(scores_to_save)
                log_and_capture_error(
                    e,
                    logger,
                    f"Failed to save resilience scores for user {uid}",
                    extra={"user_id": str(uid), "task": "fill_missing_resilience_scores"},
                )

        log_structured(
            logger,
            "info",
            f"Resilience score fill complete: {total_saved} saved, {total_skipped} skipped",
            task="fill_missing_resilience_scores",
            saved=total_saved,
            skipped=total_skipped,
        )

        return {"saved": total_saved, "skipped": total_skipped}
