"""Google Health API workouts handler.

Fetches Exercise sessions via the dataPoints ``list`` operation and normalizes them to
the unified EventRecord model. Exercise.ExerciseType maps to the unified WorkoutType via
``get_unified_google_workout_type``; device/source come from each record's ``dataSource``.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.constants.google_health_endpoints import LIST_ENDPOINT as DATAPOINTS_LIST_ENDPOINT
from app.constants.workout_types import get_unified_google_workout_type
from app.database import DbSession
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import ProviderName
from app.schemas.model_crud.activities import EventRecordCreate, EventRecordDetailCreate
from app.services.event_record_service import event_record_service
from app.services.providers.google.health_api.helpers import (
    GOOGLE_HEALTH_API_SOURCE,
    extract_source,
    parse_duration_seconds,
    parse_interval,
    parse_rfc3339,
    read_number,
    zone_offset_from,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.raw_payload_storage import store_raw_payload
from app.utils.conversion import as_int
from app.utils.sentry_helpers import log_and_capture_error

_MM_TO_M = Decimal("0.001")


class GoogleHealthApiWorkouts(BaseWorkoutsTemplate):
    """Fetches Google Health API Exercise sessions and stores them as workout EventRecords."""

    LIST_ENDPOINT = DATAPOINTS_LIST_ENDPOINT.format(data_type="exercise")
    PAGE_SIZE = 1000

    def __init__(
        self,
        workout_repo: EventRecordRepository,
        connection_repo: UserConnectionRepository,
        oauth: BaseOAuthTemplate,
        api_base_url: str,
    ):
        super().__init__(workout_repo, connection_repo, "google", api_base_url, oauth)

    # -- fetch -----------------------------------------------------------------

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """List Exercise DataPoints and keep those starting within the sync window.

        list has no range parameter, so we filter client-side on the exercise interval.
        """
        kept: list[dict[str, Any]] = []
        for point in self._fetch_points(db, user_id):
            interval = (point.get("exercise") or {}).get("interval") or {}
            start = parse_rfc3339(interval.get("startTime"))
            if start is not None and start_date <= start < end_date:
                kept.append(point)
        return kept

    def _fetch_points(self, db: DbSession, user_id: UUID) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": self.PAGE_SIZE}
            if page_token:
                params["pageToken"] = page_token
            response = self._make_api_request(db, user_id, self.LIST_ENDPOINT, method="GET", params=params)
            store_raw_payload(
                source="api_response",
                provider="google",
                payload=response,
                user_id=str(user_id),
                trace_id=self.LIST_ENDPOINT,
            )
            if not isinstance(response, dict):
                break
            points.extend(response.get("dataPoints", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return points

    # -- normalize -------------------------------------------------------------

    def _normalize_workout(
        self,
        raw_workout: dict[str, Any],
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Map an Exercise DataPoint to an EventRecord + detail."""
        workout_id = uuid4()
        exercise = raw_workout.get("exercise") or {}
        interval = exercise.get("interval") or {}
        start, end = parse_interval(interval)
        if start is None or end is None:
            raise ValueError("Exercise interval missing startTime/endTime")
        source_name, device_model = extract_source(raw_workout.get("dataSource"))

        duration_seconds = int((end - start).total_seconds()) if start and end else None
        zone_offset = zone_offset_from(interval.get("startUtcOffset"))

        record = EventRecordCreate(
            id=workout_id,
            category="workout",
            type=get_unified_google_workout_type(exercise.get("exerciseType", "")).value,
            provider=ProviderName.GOOGLE.value,
            source=GOOGLE_HEALTH_API_SOURCE,
            source_name=source_name,
            device_model=device_model,
            external_id=raw_workout.get("name"),
            start_datetime=start,
            end_datetime=end,
            duration_seconds=duration_seconds,
            zone_offset=zone_offset,
            user_id=user_id,
        )
        detail = self._build_detail(workout_id, exercise)
        return record, detail

    def _build_detail(self, workout_id: UUID, exercise: dict[str, Any]) -> EventRecordDetailCreate:
        metrics = exercise.get("metricsSummary") or {}
        return EventRecordDetailCreate(
            record_id=workout_id,
            moving_time_seconds=as_int(parse_duration_seconds(exercise.get("activeDuration"))),
            energy_burned=read_number(metrics, "caloriesKcal"),
            distance=read_number(metrics, "distanceMillimeters", scale=_MM_TO_M),
            steps_count=as_int(read_number(metrics, "steps")),
            average_speed=read_number(metrics, "averageSpeedMillimetersPerSecond", scale=_MM_TO_M),
            heart_rate_avg=read_number(metrics, "averageHeartRateBeatsPerMinute"),
            total_elevation_gain=read_number(metrics, "elevationGainMillimeters", scale=_MM_TO_M),
            average_cadence=read_number(metrics, "mobilityMetrics", "avgCadenceStepsPerMinute"),
        )

    # -- load ------------------------------------------------------------------

    def load_data(self, db: DbSession, user_id: UUID, **kwargs: Any) -> int:
        """Fetch Exercises in the window and persist each as an EventRecord + detail."""
        start = self._as_datetime(kwargs.get("start_date"))
        end = self._as_datetime(kwargs.get("end_date")) or datetime.now().astimezone()
        if start is None:
            return 0

        count = 0
        for point in self.get_workouts(db, user_id, start, end):
            try:
                record, detail = self._normalize_workout(point, user_id)
                created = event_record_service.create(db, record)
                event_record_service.create_detail(db, detail.model_copy(update={"record_id": created.id}))
            except Exception as e:
                log_and_capture_error(
                    e,
                    self.logger,
                    f"Google workout sync failed for a datapoint: {e}",
                    extra={"user_id": str(user_id), "provider": "google", "external_id": point.get("name")},
                )
                continue
            count += 1
        return count

    @staticmethod
    def _as_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return parse_rfc3339(value)
        return None
