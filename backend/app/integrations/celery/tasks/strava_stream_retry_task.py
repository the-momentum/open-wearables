"""Delayed Strava stream re-fetch for webhooks that arrive before Strava finishes processing streams."""

from typing import cast
from uuid import UUID

from celery import shared_task

from app.config import settings
from app.constants.celery_tasks import CeleryTask
from app.database import DbSession, SessionLocal
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.services.providers.strava.strategy import StravaStrategy
from app.services.providers.strava.workouts import StravaWorkouts, schedule_stream_retry
from app.utils.exceptions import ProviderConnectionError, ProviderError, is_provider_state_error
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


def _is_transient(exc: Exception) -> bool:
    """An outage or a database hiccup; not a deleted activity, a lost connection or a rejected request."""
    if isinstance(exc, ProviderConnectionError):
        return False
    if isinstance(exc, ProviderError):
        return not exc.request_rejected and not is_provider_state_error(exc)
    return True


@shared_task(name=CeleryTask.RETRY_STRAVA_STREAM_INGEST)
def retry_strava_stream_ingest(user_id: str, activity_id: str, attempt: int = 1) -> None:
    """Re-run the webhook processing flow for an activity whose streams weren't ready."""
    try:
        with SessionLocal() as db:
            _retry_ingest(db, UUID(user_id), str(activity_id), attempt)
            # Bulk sample writes defer their commit to the caller.
            db.commit()
    except Exception as exc:
        retry = _is_transient(exc) and attempt < settings.strava_stream_retry_max_attempts
        logger.error(
            "Strava stream retry failed",
            exc_info=exc,
            provider="strava",
            activity_id=activity_id,
            attempt=attempt,
            retry=retry,
        )
        if retry:
            schedule_stream_retry(user_id, str(activity_id), attempt + 1)


def _retry_ingest(db: DbSession, user_uuid: UUID, activity_id: str, attempt: int) -> None:
    workouts = cast("StravaWorkouts", StravaStrategy().workouts)
    activity_data = workouts.get_workout_detail_from_api(db, user_uuid, activity_id)
    if not activity_data:
        logger.warning(
            "Strava stream retry: no data returned for activity, giving up",
            provider="strava",
            action="stream_retry_no_activity",
            activity_id=activity_id,
        )
        return

    activity = StravaActivityJSON(**activity_data)
    # Schedules the next attempt itself if streams are still empty.
    workouts.process_push_activity(db=db, activity=activity, user_id=user_uuid, stream_retry_attempt=attempt + 1)
