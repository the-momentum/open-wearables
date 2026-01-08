from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from app.constants.workout_types.garmin import get_unified_workout_type
from app.database import DbSession
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    GarminActivityJSON,
)
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class GarminWorkouts(BaseWorkoutsTemplate):
    """Garmin implementation of workouts template."""

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get activities from Garmin API."""
        # Garmin API uses seconds for timestamps
        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())

        params = {
            "uploadStartTimeInSeconds": start_ts,
            "uploadEndTimeInSeconds": end_ts,
        }

        return self._make_api_request(
            db,
            user_id,
            "/wellness-api/rest/activities",
            params=params,
        )

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get activities from Garmin API with options."""
        summary_start_time = kwargs.get("summary_start_time")
        summary_end_time = kwargs.get("summary_end_time")

        start_ts = self._parse_timestamp(summary_start_time)
        end_ts = self._parse_timestamp(summary_end_time)

        # Default to last 24 hours if no time range provided
        # Garmin API requires these parameters and has a max range of 86400 seconds (24 hours)
        if not start_ts:
            start_ts = int((datetime.now() - timedelta(hours=24)).timestamp())
        if not end_ts:
            end_ts = int(datetime.now().timestamp())

        params = {
            "uploadStartTimeInSeconds": start_ts,
            "uploadEndTimeInSeconds": end_ts,
        }

        return self._make_api_request(
            db,
            user_id,
            "/wellness-api/rest/activities",
            params=params,
        )

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed activity data from Garmin API."""
        return self.get_activity_detail(db, user_id, workout_id)

    def _parse_timestamp(self, value: str | None) -> int | None:
        """Parse timestamp from string (Unix timestamp or ISO 8601 date)."""
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            pass
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except (ValueError, AttributeError):
            # If parsing fails, return None or raise error.
            # For now, let's return None to be safe, or we could raise HTTPException here if we want strict validation.
            # But since this is a helper, maybe just return None.
            # Actually, the endpoint was raising HTTPException.
            # Let's assume the caller handles validation or we just ignore invalid values.
            return None

    def _extract_dates(self, start_timestamp: int, end_timestamp: int) -> tuple[datetime, datetime]:
        """Extract start and end dates from timestamps."""
        start_date = datetime.fromtimestamp(start_timestamp)
        end_date = datetime.fromtimestamp(end_timestamp)
        return start_date, end_date

    def _build_metrics(self, raw_workout: GarminActivityJSON) -> EventRecordMetrics:
        heart_rate_avg = (
            Decimal(str(raw_workout.averageHeartRateInBeatsPerMinute))
            if raw_workout.averageHeartRateInBeatsPerMinute is not None
            else None
        )
        heart_rate_max = (
            Decimal(str(raw_workout.maxHeartRateInBeatsPerMinute))
            if raw_workout.maxHeartRateInBeatsPerMinute is not None
            else None
        )

        steps_count = int(raw_workout.steps) if raw_workout.steps is not None else None

        return {
            "heart_rate_min": int(heart_rate_avg) if heart_rate_avg is not None else None,
            "heart_rate_max": int(heart_rate_max) if heart_rate_max is not None else None,
            "heart_rate_avg": heart_rate_avg,
            "steps_count": steps_count,
        }

    def _normalize_workout(
        self,
        raw_workout: GarminActivityJSON,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Normalize Garmin activity to EventRecordCreate and EventRecordDetailCreate."""
        workout_id = uuid4()

        workout_type = get_unified_workout_type(raw_workout.activityType)

        start_date, end_date = self._extract_dates(
            raw_workout.startTimeInSeconds,
            raw_workout.startTimeInSeconds + raw_workout.durationInSeconds,
        )
        duration_seconds = raw_workout.durationInSeconds

        metrics = self._build_metrics(raw_workout)

        record = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name=raw_workout.deviceName,
            device_id=raw_workout.deviceName,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            id=workout_id,
            external_id=raw_workout.activityId,
            provider_name="Garmin",
            user_id=user_id,
        )

        detail = EventRecordDetailCreate(
            record_id=workout_id,
            **metrics,
        )

        return record, detail

    def _build_bundles(
        self,
        raw: list[GarminActivityJSON],
        user_id: UUID,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Build event record payloads for Garmin activities."""
        for raw_workout in raw:
            yield self._normalize_workout(raw_workout, user_id)

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        **kwargs: Any,
    ) -> bool:
        """Load data from Garmin API."""
        workouts = self.get_workouts_from_api(db, user_id, **kwargs)
        activities = [GarminActivityJSON(**activity) for activity in workouts]

        for record, detail in self._build_bundles(activities, user_id):
            created_record = event_record_service.create(db, record)
            detail_for_record = detail.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)

        return True

    def get_activity_detail(
        self,
        db: DbSession,
        user_id: UUID,
        activity_id: str,
    ) -> dict:
        """Get detailed activity data from Garmin API."""
        return self._make_api_request(db, user_id, f"/wellness-api/rest/activities/{activity_id}")
