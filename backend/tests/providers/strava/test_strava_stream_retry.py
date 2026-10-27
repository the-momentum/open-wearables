"""Tests for the delayed Strava stream re-fetch when the webhook beats stream processing."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.config import settings
from app.integrations.celery.tasks.strava_stream_retry_task import retry_strava_stream_ingest
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.services.providers.strava.workouts import StravaWorkouts, schedule_stream_retry

_ACTIVITY = StravaActivityJSON(
    id=19769960003,
    name="Evening Ride",
    type="Ride",
    sport_type="Ride",
    start_date="2026-08-16T15:39:19Z",
    elapsed_time=5800,
    utc_offset=7200.0,
    device_name="Apple Watch",
)


@pytest.fixture
def workouts() -> StravaWorkouts:
    return StravaWorkouts(
        workout_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name="strava",
        api_base_url="https://www.strava.com",
        oauth=MagicMock(),
    )


class TestWebhookSchedulesRetry:
    def _process(
        self,
        workouts: StravaWorkouts,
        ingested: int,
        has_samples: bool,
        attempt: int = 1,
    ) -> MagicMock:
        user_id = uuid4()
        with (
            patch("app.services.providers.strava.workouts.event_record_service") as mock_service,
            patch.object(workouts, "_ingest_workout_streams", return_value=ingested),
            patch(
                "app.services.providers.strava.workouts.timeseries_service.has_samples_in_range",
                return_value=has_samples,
            ),
            patch("app.services.providers.strava.workouts.schedule_stream_retry") as mock_schedule,
            patch("app.services.providers.strava.workouts.settings") as mock_settings,
        ):
            mock_settings.ingest_workout_samples = True
            mock_settings.strava_stream_retry_max_attempts = settings.strava_stream_retry_max_attempts
            mock_service.create.return_value = MagicMock(id=uuid4())
            workouts.process_push_activity(
                db=MagicMock(), activity=_ACTIVITY, user_id=user_id, stream_retry_attempt=attempt
            )
        return mock_schedule

    def test_empty_streams_schedule_delayed_retry(self, workouts: StravaWorkouts) -> None:
        mock_schedule = self._process(workouts, ingested=0, has_samples=False)
        mock_schedule.assert_called_once()
        args, kwargs = mock_schedule.call_args
        assert str(_ACTIVITY.id) in args or kwargs.get("activity_id") == str(_ACTIVITY.id)
        assert kwargs.get("attempt", args[-1] if args else None) == 1

    def test_retry_attempt_is_propagated(self, workouts: StravaWorkouts) -> None:
        mock_schedule = self._process(workouts, ingested=0, has_samples=False, attempt=2)
        assert mock_schedule.call_args.kwargs.get("attempt") == 2

    def test_no_retry_when_samples_ingested(self, workouts: StravaWorkouts) -> None:
        mock_schedule = self._process(workouts, ingested=4752, has_samples=True)
        mock_schedule.assert_not_called()

    def test_no_retry_when_samples_already_exist(self, workouts: StravaWorkouts) -> None:
        # skip-guard returned 0 because samples are already there — nothing to retry
        mock_schedule = self._process(workouts, ingested=0, has_samples=True)
        mock_schedule.assert_not_called()

    def test_gives_up_after_attempt_budget(self, workouts: StravaWorkouts) -> None:
        exhausted = settings.strava_stream_retry_max_attempts + 1
        mock_schedule = self._process(workouts, ingested=0, has_samples=False, attempt=exhausted)
        mock_schedule.assert_not_called()


class TestRetryTask:
    """The task must reuse the regular workouts-module flow, not reimplement it."""

    def _run(self, activity_data: dict | None, attempt: int = 1) -> MagicMock:
        mock_workouts = MagicMock()
        mock_workouts.get_workout_detail_from_api.return_value = activity_data
        with (
            patch("app.integrations.celery.tasks.strava_stream_retry_task.StravaStrategy") as mock_strategy,
            patch("app.integrations.celery.tasks.strava_stream_retry_task.SessionLocal"),
        ):
            mock_strategy.return_value.workouts = mock_workouts
            retry_strava_stream_ingest(str(uuid4()), str(_ACTIVITY.id), attempt=attempt)
        return mock_workouts

    def test_reruns_webhook_flow_with_next_attempt(self) -> None:
        mock_workouts = self._run(_ACTIVITY.model_dump(), attempt=1)
        mock_workouts.process_push_activity.assert_called_once()
        kwargs = mock_workouts.process_push_activity.call_args.kwargs
        assert str(kwargs["activity"].id) == str(_ACTIVITY.id)
        assert kwargs["stream_retry_attempt"] == 2

    def test_gives_up_when_activity_gone(self) -> None:
        mock_workouts = self._run(None, attempt=1)
        mock_workouts.process_push_activity.assert_not_called()


class TestTransientFailureReschedule:
    def _run_with_error(self, attempt: int) -> MagicMock:
        with (
            patch(
                "app.integrations.celery.tasks.strava_stream_retry_task._retry_ingest",
                side_effect=RuntimeError("strava 500"),
            ),
            patch("app.integrations.celery.tasks.strava_stream_retry_task.SessionLocal"),
            patch("app.integrations.celery.tasks.strava_stream_retry_task.schedule_stream_retry") as mock_schedule,
        ):
            retry_strava_stream_ingest(str(uuid4()), "a-1", attempt=attempt)
        return mock_schedule

    def test_task_reschedules_on_transient_error(self) -> None:
        mock_schedule = self._run_with_error(attempt=1)
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args.args[2] == 2

    def test_task_gives_up_on_transient_error_at_budget(self) -> None:
        mock_schedule = self._run_with_error(attempt=settings.strava_stream_retry_max_attempts)
        mock_schedule.assert_not_called()


class TestScheduleStreamRetry:
    def test_uses_configured_backoff_per_attempt(self) -> None:
        with patch("app.services.providers.strava.workouts.celery_app.send_task") as mock_send:
            schedule_stream_retry("u-1", "a-1", attempt=2)
        kwargs = mock_send.call_args.kwargs
        assert kwargs["countdown"] == settings.strava_stream_retry_base_delay_seconds * 3
        assert kwargs["kwargs"]["attempt"] == 2
