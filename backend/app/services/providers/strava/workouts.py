from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from app.constants.workout_types.strava import get_unified_workout_type
from app.database import DbSession
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    StravaActivityJSON,
)
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.utils.structured_logging import log_structured
from app.config import settings

class StravaWorkouts(BaseWorkoutsTemplate):
    """Strava implementation of workouts template."""

    @property
    def events_per_page(self) -> int:
        """Get the number of events per page."""
        return settings.strava_events_per_page

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get activities from Strava API with page-based pagination.

        Strava API uses epoch timestamps for after/before parameters
        and supports up to 200 activities per page.
        """
        all_activities: list[Any] = []
        page = 1
        per_page = self.events_per_page

        after = int(start_date.timestamp())
        before = int(end_date.timestamp())

        while True:
            params: dict[str, Any] = {
                "after": after,
                "before": before,
                "page": page,
                "per_page": per_page,
            }

            try:
                response = self._make_api_request(
                    db,
                    user_id,
                    "/athlete/activities",
                    params=params,
                )

                if not isinstance(response, list):
                    break

                all_activities.extend(response)

                # Stop if fewer results than page size (last page)
                if len(response) < per_page:
                    break

                page += 1

            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    "Error fetching Strava activities page",
                    action="strava_fetch_page_error",
                    page=page,
                    user_id=str(user_id),
                    error=str(e),
                )
                if all_activities:
                    log_structured(
                        self.logger,
                        "warn",
                        "Returning partial activity data due to error",
                        action="strava_partial_data",
                        activities_count=len(all_activities),
                        user_id=str(user_id),
                        error=str(e),
                    )
                    break
                raise

        return all_activities

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get activities from Strava API with specific options."""
        page = kwargs.get("page", 1)
        per_page = self.events_per_page

        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }

        after = kwargs.get("after")
        before = kwargs.get("before")
        if after:
            params["after"] = int(after) if not isinstance(after, int) else after
        if before:
            params["before"] = int(before) if not isinstance(before, int) else before

        return self._make_api_request(db, user_id, "/athlete/activities", params=params)

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed activity data from Strava API."""
        return self._make_api_request(db, user_id, f"/activities/{workout_id}")

    def _extract_dates_from_iso(self, start_iso: str, elapsed_time: int) -> tuple[datetime, datetime]:
        """Extract start and end dates from ISO string and elapsed time."""
        start_date = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        end_date = start_date + timedelta(seconds=elapsed_time)
        return start_date, end_date

    def _build_metrics(self, raw_workout: StravaActivityJSON) -> EventRecordMetrics:
        """Build metrics from Strava activity data."""
        metrics: EventRecordMetrics = {}

        # Heart rate
        if raw_workout.average_heartrate is not None:
            metrics["heart_rate_avg"] = Decimal(str(raw_workout.average_heartrate))
        if raw_workout.max_heartrate is not None:
            metrics["heart_rate_max"] = int(raw_workout.max_heartrate)

        # Distance (meters)
        if raw_workout.distance is not None:
            metrics["distance"] = Decimal(str(raw_workout.distance))

        # Speed (m/s)
        if raw_workout.average_speed is not None:
            metrics["average_speed"] = Decimal(str(raw_workout.average_speed))
        if raw_workout.max_speed is not None:
            metrics["max_speed"] = Decimal(str(raw_workout.max_speed))

        # Power (watts)
        if raw_workout.average_watts is not None:
            metrics["average_watts"] = Decimal(str(raw_workout.average_watts))
        if raw_workout.max_watts is not None:
            metrics["max_watts"] = Decimal(str(raw_workout.max_watts))

        # Elevation
        if raw_workout.total_elevation_gain is not None:
            metrics["total_elevation_gain"] = Decimal(str(raw_workout.total_elevation_gain))
        if raw_workout.elev_high is not None:
            metrics["elev_high"] = Decimal(str(raw_workout.elev_high))
        if raw_workout.elev_low is not None:
            metrics["elev_low"] = Decimal(str(raw_workout.elev_low))

        # Energy: prefer calories (if available and non-zero), fallback to kilojoules.
        # Strava's list endpoint often returns calories=None, so we fall back to kilojoules.
        # Standard exercise approximation: kcal ≈ kJ (human efficiency ~25% cancels the unit factor).
        if raw_workout.calories is not None and raw_workout.calories > 0:
            metrics["energy_burned"] = Decimal(str(raw_workout.calories))
        elif raw_workout.kilojoules is not None:
            metrics["energy_burned"] = Decimal(str(raw_workout.kilojoules))

        # Moving time
        if raw_workout.moving_time is not None:
            metrics["moving_time_seconds"] = raw_workout.moving_time

        return metrics

    def _normalize_workout(
        self,
        raw_workout: StravaActivityJSON,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Normalize Strava activity to EventRecordCreate and EventRecordDetailCreate."""
        workout_id = uuid4()

        # Use sport_type for more specific mapping, fallback to type
        workout_type = get_unified_workout_type(raw_workout.sport_type)

        # Prefer moving_time (excludes pauses) over elapsed_time
        duration_seconds = raw_workout.moving_time or raw_workout.elapsed_time
        start_date, end_date = self._extract_dates_from_iso(raw_workout.start_date, duration_seconds)

        metrics = self._build_metrics(raw_workout)

        device_name = raw_workout.device_name or "Strava"

        record = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name=device_name,
            device_model=device_name,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            id=workout_id,
            external_id=str(raw_workout.id),
            source="strava",
            user_id=user_id,
        )

        detail = EventRecordDetailCreate(
            record_id=workout_id,
            **metrics,
        )

        return record, detail

    def _build_bundles(
        self,
        raw: list[StravaActivityJSON],
        user_id: UUID,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Build event record payloads for Strava activities."""
        for raw_workout in raw:
            yield self._normalize_workout(raw_workout, user_id)

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        **kwargs: Any,
    ) -> bool:
        """Load data from Strava API (historical backfill).

        Fetches all activities in a date range using page-based pagination.
        """
        # Get start/end dates from kwargs
        start = kwargs.get("start") or kwargs.get("start_date")
        end = kwargs.get("end") or kwargs.get("end_date")

        # Default to last 30 days if no dates provided
        if not start:
            start_dt = datetime.now(timezone.utc) - timedelta(days=30)
        elif isinstance(start, datetime):
            start_dt = start
        elif isinstance(start, str):
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        else:
            start_dt = datetime.now(timezone.utc) - timedelta(days=30)

        if not end:
            end_dt = datetime.now(timezone.utc)
        elif isinstance(end, datetime):
            end_dt = end
        elif isinstance(end, str):
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        else:
            end_dt = datetime.now(timezone.utc)

        # Fetch all activities
        raw_activities = self.get_workouts(db, user_id, start_dt, end_dt)

        # Parse and save
        parsed_activities = []
        for raw in raw_activities:
            try:
                activity = StravaActivityJSON(**raw) if isinstance(raw, dict) else raw
                parsed_activities.append(activity)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warn",
                    "Failed to parse Strava activity",
                    action="strava_parse_error",
                    user_id=str(user_id),
                    error=str(e),
                )

        for record, detail in self._build_bundles(parsed_activities, user_id):
            created_record = event_record_service.create(db, record)
            detail_for_record = detail.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)

        return True

    def process_push_activity(
        self,
        db: DbSession,
        activity: StravaActivityJSON,
        user_id: UUID,
    ) -> list[UUID]:
        """Process a single activity from webhook and save to database.

        Args:
            db: Database session
            activity: Parsed Strava activity data
            user_id: Internal user ID (already mapped from Strava athlete ID)

        Returns:
            List of created event record IDs
        """
        created_ids: list[UUID] = []

        record, detail = self._normalize_workout(activity, user_id)
        created_record = event_record_service.create(db, record)
        detail_for_record = detail.model_copy(update={"record_id": created_record.id})
        event_record_service.create_detail(db, detail_for_record)
        created_ids.append(created_record.id)

        return created_ids
