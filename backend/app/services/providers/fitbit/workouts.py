import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.constants.workout_types.fitbit import get_unified_workout_type
from app.database import DbSession
from app.schemas import EventRecordCreate, EventRecordDetailCreate, EventRecordMetrics
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.utils.sentry_helpers import log_and_capture_error

logger = logging.getLogger(__name__)


class FitbitWorkouts(BaseWorkoutsTemplate):
    """Fitbit PULL-based workouts handler.

    Fetches activities from Fitbit's Activities List API and normalizes
    them to EventRecord. Duration is in milliseconds; timestamps are ISO 8601.
    """

    def _extract_dates(self, start_timestamp: Any, end_timestamp: Any) -> tuple[datetime, datetime]:
        """Not used by Fitbit — use _parse_fitbit_dates instead."""
        raise NotImplementedError("Use _parse_fitbit_dates for Fitbit workouts")

    def _parse_fitbit_dates(
        self,
        start_time: str,
        duration_ms: int,
    ) -> tuple[datetime, datetime]:
        """Parse ISO 8601 start time and compute end time from duration in ms."""
        parsed_start = datetime.fromisoformat(start_time)
        if parsed_start.tzinfo is None:
            raise ValueError(f"Fitbit startTime is missing timezone offset: {start_time}")
        start_dt = parsed_start.astimezone(timezone.utc)
        end_dt = start_dt + timedelta(milliseconds=duration_ms)
        return start_dt, end_dt

    def _build_metrics(self, raw: dict[str, Any]) -> EventRecordMetrics:
        """Extract available metrics from a raw Fitbit activity record."""
        hr_avg = raw.get("averageHeartRate")
        calories = raw.get("calories")
        distance = raw.get("distance")
        steps = raw.get("steps")

        return {
            "heart_rate_min": None,
            "heart_rate_max": None,
            "heart_rate_avg": Decimal(str(hr_avg)) if hr_avg is not None else None,
            "steps_count": int(steps) if steps is not None else None,
            "energy_burned": Decimal(str(calories)) if calories is not None else None,
            "distance": Decimal(str(distance)) if distance is not None else None,
        }

    def _normalize_workout(
        self,
        raw_workout: dict[str, Any],
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Normalize Fitbit activity to EventRecordCreate + EventRecordDetailCreate."""
        workout_id = uuid4()
        workout_type = get_unified_workout_type(
            raw_workout.get("activityTypeId", 0),
            raw_workout.get("activityName"),
        )

        duration_seconds = raw_workout["duration"] // 1000  # ms → seconds
        start_date, end_date = self._parse_fitbit_dates(
            raw_workout["startTime"],
            raw_workout["duration"],
        )

        source_dict = raw_workout.get("source")
        source_name = source_dict.get("name", "Fitbit") if source_dict else "Fitbit"

        record = EventRecordCreate(
            id=workout_id,
            category="workout",
            type=workout_type.value,
            source_name=source_name,
            device_model=source_name,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            external_id=str(raw_workout["logId"]),
            source="fitbit",
            user_id=user_id,
        )

        detail = EventRecordDetailCreate(
            record_id=workout_id,
            **self._build_metrics(raw_workout),
        )

        return record, detail

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Fetch all activities from Fitbit API between start and end dates, handling pagination."""
        # Fitbit only accepts exactly one of afterDate or beforeDate per request.
        # Use afterDate + sort=asc and paginate forward, filtering out records past end_date.
        params = {
            "afterDate": start_date.strftime("%Y-%m-%d"),
            "sort": "asc",
            "limit": "100",
            "offset": "0",
        }
        all_activities: list[Any] = []
        offset = 0
        end_date_str = end_date.strftime("%Y-%m-%d")

        while True:
            params["offset"] = str(offset)
            response = self._make_api_request(db, user_id, "/1/user/-/activities/list.json", params=params)
            if not response:
                break
            activities = response.get("activities", [])
            # Filter out activities beyond end_date
            in_range = [a for a in activities if a.get("startTime", "")[:10] <= end_date_str]
            all_activities.extend(in_range)
            # Stop if we've passed end_date or there are no more pages
            next_page = response.get("pagination", {}).get("next", "")
            if not next_page or not activities or len(in_range) < len(activities):
                break
            offset += len(activities)

        return all_activities

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Fetch workouts from Fitbit API with optional date range."""
        start_date = kwargs.get("start_date") or (datetime.now(timezone.utc) - timedelta(days=30))
        end_date = kwargs.get("end_date") or datetime.now(timezone.utc)
        return self.get_workouts(db, user_id, start_date, end_date)

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        **kwargs: Any,
    ) -> bool:
        """Fetch activities since start_date and save to database."""
        start_date = kwargs.get("start_date") or (datetime.now(timezone.utc) - timedelta(days=30))
        end_date = kwargs.get("end_date") or datetime.now(timezone.utc)

        activities = self.get_workouts(db, user_id, start_date, end_date)

        for raw in activities:
            try:
                record, detail = self._normalize_workout(raw, user_id)
                created_record = event_record_service.create(db, record)
                detail_for_record = detail.model_copy(update={"record_id": created_record.id})
                event_record_service.create_detail(db, detail_for_record)
            except Exception as e:
                log_and_capture_error(
                    e,
                    logger,
                    f"Failed to save Fitbit activity {raw.get('logId', 'unknown')}: {e}",
                    extra={"user_id": str(user_id), "activity": raw.get("logId")},
                )
                continue

        return True
