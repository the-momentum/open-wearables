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
        """Get activities from Garmin API for a single time range.

        Note: Garmin API has a maximum range of ~24 hours per request.
        For longer date ranges, use get_workouts_historical().
        """
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

    def get_workouts_historical(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        chunk_hours: int = 24,
    ) -> list[Any]:
        """Fetch workouts in 24-hour chunks for extended date ranges.

        Garmin API limits requests to ~24 hours. This method fetches data
        in chunks to support historical backfill of any date range.

        Args:
            db: Database session
            user_id: User ID
            start_date: Start of date range
            end_date: End of date range
            chunk_hours: Size of each chunk in hours (default 24)

        Returns:
            List of all activities from the date range
        """
        all_activities: list[Any] = []
        current_start = start_date

        while current_start < end_date:
            current_end = min(current_start + timedelta(hours=chunk_hours), end_date)

            try:
                activities = self.get_workouts(db, user_id, current_start, current_end)
                if isinstance(activities, list):
                    all_activities.extend(activities)
            except Exception as e:
                # Log error but continue with other chunks
                import logging

                logging.getLogger(__name__).warning(
                    f"Error fetching activities chunk ({current_start.isoformat()} to {current_end.isoformat()}): {e}"
                )

            current_start = current_end

        return all_activities

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get activities from Garmin API with options.

        Supports extended date ranges by automatically chunking requests
        when the range exceeds 24 hours (Garmin API limit).
        """
        summary_start_time = kwargs.get("summary_start_time")
        summary_end_time = kwargs.get("summary_end_time")

        start_ts = self._parse_timestamp(summary_start_time)
        end_ts = self._parse_timestamp(summary_end_time)

        # Default to last 24 hours if no time range provided
        if not start_ts:
            start_ts = int((datetime.now() - timedelta(hours=24)).timestamp())
        if not end_ts:
            end_ts = int(datetime.now().timestamp())

        # Convert to datetime for chunked fetching
        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = datetime.fromtimestamp(end_ts)

        # Check if range exceeds 24 hours - if so, use chunked fetching
        if (end_dt - start_dt) > timedelta(hours=24):
            return self.get_workouts_historical(db, user_id, start_dt, end_dt)

        # Single request for ranges <= 24 hours
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

        # Use device name if available, otherwise fallback to "Garmin"
        device_name = raw_workout.deviceName or "Garmin"

        record = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name=device_name,
            device_id=device_name,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            id=workout_id,
            external_id=str(raw_workout.activityId),  # Convert to str (push sends int)
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
        """Load data from Garmin API via backfill.

        Note: Garmin Health API requires pull tokens for direct polling.
        Instead, we use the backfill API which triggers Garmin to send
        data to our configured webhooks asynchronously.
        """
        from contextlib import suppress

        from app.services.providers.garmin.backfill import GarminBackfillService

        # Parse date range from kwargs
        start_dt: datetime | None = None
        end_dt: datetime | None = None

        summary_start_time = kwargs.get("summary_start_time")
        summary_end_time = kwargs.get("summary_end_time")

        if summary_start_time:
            with suppress(ValueError, AttributeError):
                if isinstance(summary_start_time, str):
                    start_dt = datetime.fromisoformat(summary_start_time.replace("Z", "+00:00"))
                elif isinstance(summary_start_time, datetime):
                    start_dt = summary_start_time

        if summary_end_time:
            with suppress(ValueError, AttributeError):
                if isinstance(summary_end_time, str):
                    end_dt = datetime.fromisoformat(summary_end_time.replace("Z", "+00:00"))
                elif isinstance(summary_end_time, datetime):
                    end_dt = summary_end_time

        # Use backfill API - data will arrive via webhooks
        backfill_service = GarminBackfillService(
            provider_name=self.provider_name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

        result = backfill_service.trigger_backfill(
            db=db,
            user_id=user_id,
            data_types=["activities"],
            start_time=start_dt,
            end_time=end_dt,
        )

        self.logger.info(
            f"Garmin activities backfill triggered for user {user_id}: "
            f"triggered={result['triggered']}, failed={result['failed']}"
        )

        return "activities" in result["triggered"]

    def get_activity_detail(
        self,
        db: DbSession,
        user_id: UUID,
        activity_id: str,
    ) -> dict:
        """Get detailed activity data from Garmin API."""
        return self._make_api_request(db, user_id, f"/wellness-api/rest/activities/{activity_id}")

    def process_push_activities(
        self,
        db: DbSession,
        activities: list[GarminActivityJSON],
        user_id: UUID,
    ) -> list[UUID]:
        """Process activities received from push notification and save to database.

        Args:
            db: Database session
            activities: List of parsed activity data from push webhook
            user_id: Internal user ID (already mapped from Garmin user ID)

        Returns:
            List of created event record IDs
        """
        created_ids: list[UUID] = []

        for record, detail in self._build_bundles(activities, user_id):
            created_record = event_record_service.create(db, record)
            detail_for_record = detail.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)
            created_ids.append(created_record.id)

        return created_ids
