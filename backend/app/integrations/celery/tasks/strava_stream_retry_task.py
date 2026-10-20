"""Delayed Strava stream re-fetch for webhooks that arrive before Strava finishes processing streams."""

from logging import getLogger
from uuid import UUID

from celery import shared_task

from app.config import settings
from app.constants.celery_tasks import CeleryTask
from app.database import DbSession, SessionLocal
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.services.providers.strava.strategy import StravaStrategy
from app.services.providers.strava.workouts import schedule_stream_retry
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


@shared_task(name=CeleryTask.RETRY_STRAVA_STREAM_INGEST)
def retry_strava_stream_ingest(user_id: str, activity_id: str, attempt: int = 1) -> None:
    """Re-run the webhook processing flow for an activity whose streams weren't ready."""
    try:
        with SessionLocal() as db:
            _retry_ingest(db, UUID(user_id), str(activity_id), attempt)
            # Bulk sample writes defer their commit to the caller.
            db.commit()
    except Exception as e:
        # Transient failures keep the chain going until the attempt budget runs out.
        log_and_capture_error(e, logger, "Strava stream retry failed", extra={"activity_id": activity_id})
        if attempt < settings.strava_stream_retry_max_attempts:
            schedule_stream_retry(user_id, str(activity_id), attempt + 1)


def _retry_ingest(db: DbSession, user_uuid: UUID, activity_id: str, attempt: int) -> None:
    workouts = StravaStrategy().workouts
    activity_data = workouts.get_workout_detail_from_api(db, user_uuid, activity_id)
    if not activity_data:
        log_structured(
            logger,
            "warning",
            "Strava stream retry: no data returned for activity, giving up",
            provider="strava",
            action="stream_retry_no_activity",
            activity_id=activity_id,
        )
        return

    activity = StravaActivityJSON(**activity_data)
    # Schedules the next attempt itself if streams are still empty.
    workouts.process_push_activity(db=db, activity=activity, user_id=user_uuid, stream_retry_attempt=attempt + 1)
