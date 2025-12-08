from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from app.constants.workout_types.suunto import get_unified_workout_type
from app.database import DbSession
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    SuuntoWorkoutJSON,
)
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class SuuntoWorkouts(BaseWorkoutsTemplate):
    """Suunto implementation of workouts template."""

    def _get_suunto_headers(self) -> dict[str, str]:
        """Get Suunto-specific headers including subscription key."""
        headers = {}
        if self.oauth and hasattr(self.oauth, "credentials"):
            subscription_key = self.oauth.credentials.subscription_key
            if subscription_key:
                headers["Ocp-Apim-Subscription-Key"] = subscription_key
        return headers

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get workouts from Suunto API."""
        # Suunto uses 'since' parameter
        since = int(start_date.timestamp())
        params = {
            "since": since,
            "limit": 100,
        }
        headers = self._get_suunto_headers()
        response = self._make_api_request(db, user_id, "/v3/workouts/", params=params, headers=headers)
        return response.get("payload", [])

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get workouts from Suunto API with specific options."""
        since = kwargs.get("since", 0)
        limit = kwargs.get("limit", 50)
        offset = kwargs.get("offset", 0)
        filter_by_modification_time = kwargs.get("filter_by_modification_time", True)

        params = {
            "since": since,
            "limit": min(limit, 100),
            "offset": offset,
            "filter-by-modification-time": str(filter_by_modification_time).lower(),
        }

        # Suunto requires subscription key header
        headers = self._get_suunto_headers()

        return self._make_api_request(db, user_id, "/v3/workouts/", params=params, headers=headers)

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed workout data from Suunto API."""
        return self.get_workout_detail(db, user_id, workout_id)

    def _extract_dates(self, start_timestamp: int, end_timestamp: int) -> tuple[datetime, datetime]:
        """Extract start and end dates from timestamps."""
        start_date = datetime.fromtimestamp(start_timestamp / 1000)
        end_date = datetime.fromtimestamp(end_timestamp / 1000)
        return start_date, end_date

    def _build_metrics(self, raw_workout: SuuntoWorkoutJSON) -> EventRecordMetrics:
        hr_data = raw_workout.hrdata
        heart_rate_avg = Decimal(str(hr_data.avg)) if hr_data and hr_data.avg is not None else None
        heart_rate_max = Decimal(str(hr_data.max)) if hr_data and hr_data.max is not None else None
        steps_count = int(raw_workout.stepCount) if raw_workout.stepCount is not None else None
        steps_avg = Decimal(str(raw_workout.stepCount)) if raw_workout.stepCount is not None else None

        return {
            "heart_rate_min": int(heart_rate_avg) if heart_rate_avg is not None else None,
            "heart_rate_max": int(heart_rate_max) if heart_rate_max is not None else None,
            "heart_rate_avg": heart_rate_avg,
            "steps_min": steps_count,
            "steps_max": steps_count,
            "steps_avg": steps_avg,
            "steps_total": steps_count,
        }

    def _normalize_workout(
        self,
        raw_workout: SuuntoWorkoutJSON,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Normalize Suunto workout to EventRecordCreate."""
        workout_id = uuid4()

        workout_type = get_unified_workout_type(raw_workout.activityId)

        start_date, end_date = self._extract_dates(raw_workout.startTime, raw_workout.stopTime)
        duration_seconds = int(raw_workout.totalTime)

        source_name = raw_workout.gear.name if raw_workout.gear else "Unknown"

        device_id = raw_workout.gear.serialNumber if raw_workout.gear else None

        metrics = self._build_metrics(raw_workout)

        workout_create = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name=source_name,
            device_id=device_id,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            id=workout_id,
            provider_id=str(raw_workout.workoutId),
            user_id=user_id,
        )

        workout_detail_create = EventRecordDetailCreate(
            record_id=workout_id,
            **metrics,
        )

        return workout_create, workout_detail_create

    def _build_bundles(
        self,
        raw: list[SuuntoWorkoutJSON],
        user_id: UUID,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Build event record payloads for Suunto workouts."""
        for raw_workout in raw:
            record, details = self._normalize_workout(raw_workout, user_id)
            yield record, details

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        **kwargs: Any,
    ) -> bool:
        """Load data from Suunto API."""
        response = self.get_workouts_from_api(db, user_id, **kwargs)
        workouts_data = response.get("payload", [])
        workouts = [SuuntoWorkoutJSON(**w) for w in workouts_data]

        for record, details in self._build_bundles(workouts, user_id):
            event_record_service.create(db, record)
            event_record_service.create_detail(db, details)

        return True

    def get_workout_detail(
        self,
        db: DbSession,
        user_id: UUID,
        workout_key: str,
    ) -> dict:
        """Get detailed workout data from Suunto API."""
        headers = self._get_suunto_headers()
        return self._make_api_request(db, user_id, f"/v3/workouts/{workout_key}", headers=headers)
