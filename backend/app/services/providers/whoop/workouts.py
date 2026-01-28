from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from app.constants.workout_types.whoop import get_unified_workout_type
from app.database import DbSession
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    WhoopWorkoutCollectionJSON,
    WhoopWorkoutJSON,
)
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class WhoopWorkouts(BaseWorkoutsTemplate):
    """Whoop implementation of workouts template."""

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get workouts from Whoop API."""
        all_workouts = []
        next_token = None
        max_limit = 25  # Whoop API limit

        # Convert datetimes to ISO 8601 strings
        start_iso = start_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        while True:
            params: dict[str, Any] = {
                "start": start_iso,
                "end": end_iso,
                "limit": max_limit,
            }

            if next_token:
                params["nextToken"] = next_token

            try:
                response = self._make_api_request(db, user_id, "/v2/activity/workout", params=params)

                # Parse response
                if isinstance(response, dict):
                    collection = WhoopWorkoutCollectionJSON(**response)
                else:
                    collection = WhoopWorkoutCollectionJSON(records=[])

                all_workouts.extend(collection.records)

                # Check for next page
                next_token = collection.next_token

                # Stop if no more records or no next token
                if not collection.records or not next_token:
                    break

            except Exception as e:
                self.logger.error(f"Error fetching Whoop workout data: {e}")
                # If we got some data, return what we have; otherwise re-raise
                if all_workouts:
                    self.logger.warning(f"Returning partial workout data due to error: {e}")
                    break
                raise

        return all_workouts

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get workouts from Whoop API with specific options."""
        start = kwargs.get("start")
        end = kwargs.get("end")
        limit = kwargs.get("limit", 25)
        next_token = kwargs.get("nextToken")

        # Convert start/end dates to ISO 8601 if provided
        if isinstance(start, datetime):
            start = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(end, datetime):
            end = end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        params: dict[str, Any] = {
            "limit": min(limit, 25),  # Whoop API max limit is 25
        }

        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if next_token:
            params["nextToken"] = next_token

        return self._make_api_request(db, user_id, "/v2/activity/workout", params=params)

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed workout data from Whoop API."""
        return self._make_api_request(db, user_id, f"/v2/activity/workout/{workout_id}")

    def _extract_dates(self, start_timestamp: str, end_timestamp: str) -> tuple[datetime, datetime]:
        """Extract start and end dates from ISO 8601 strings."""
        # Parse ISO 8601 strings, handling timezone info
        start_date = datetime.fromisoformat(start_timestamp.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_timestamp.replace("Z", "+00:00"))

        # Ensure timezone-aware
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        return start_date, end_date

    def _build_metrics(self, raw_workout: WhoopWorkoutJSON) -> EventRecordMetrics:
        """Build metrics from Whoop workout data."""
        score = raw_workout.score
        if not score:
            return {}

        metrics: EventRecordMetrics = {}

        # Heart rate
        if score.average_heart_rate is not None:
            metrics["heart_rate_avg"] = Decimal(str(score.average_heart_rate))
        if score.max_heart_rate is not None:
            metrics["heart_rate_max"] = score.max_heart_rate

        # Energy: Convert kilojoule to kcal (1 kJ = 0.239 kcal)
        if score.kilojoule is not None:
            energy_kcal = Decimal(str(score.kilojoule)) * Decimal("0.239")
            metrics["energy_burned"] = energy_kcal

        # Distance: Keep in meters (or convert to km if schema expects km)
        # Based on schema, distance is Decimal, so we'll keep in meters
        if score.distance_meter is not None:
            metrics["distance"] = Decimal(str(score.distance_meter))

        # Elevation
        if score.altitude_gain_meter is not None:
            metrics["total_elevation_gain"] = Decimal(str(score.altitude_gain_meter))

        # Moving time: Calculate from start/end (Whoop doesn't separate moving time)
        start_date, end_date = self._extract_dates(raw_workout.start, raw_workout.end)
        duration_seconds = int((end_date - start_date).total_seconds())
        metrics["moving_time_seconds"] = duration_seconds

        return metrics

    def _normalize_workout(
        self,
        raw_workout: WhoopWorkoutJSON,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Normalize Whoop workout to EventRecordCreate and EventRecordDetailCreate."""
        workout_id = uuid4()

        # Get workout type from sport_name (sport_id deprecated after 09/01/2025)
        workout_type = get_unified_workout_type(raw_workout.sport_name)

        # Extract dates
        start_date, end_date = self._extract_dates(raw_workout.start, raw_workout.end)
        duration_seconds = int((end_date - start_date).total_seconds())

        # Build metrics
        metrics = self._build_metrics(raw_workout)

        # Create EventRecordCreate
        workout_create = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name="Whoop",
            device_model=None,  # Whoop doesn't provide device info in workout
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            id=workout_id,
            external_id=raw_workout.id,  # Whoop workout UUID
            source=self.provider_name,
            user_id=user_id,
        )

        # Create EventRecordDetailCreate
        workout_detail_create = EventRecordDetailCreate(
            record_id=workout_id,
            **metrics,
        )

        return workout_create, workout_detail_create

    def _build_bundles(
        self,
        raw: list[WhoopWorkoutJSON],
        user_id: UUID,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Build event record payloads for Whoop workouts."""
        for raw_workout in raw:
            # Only process workouts that are scored
            if raw_workout.score_state == "SCORED" or raw_workout.score is not None:
                record, details = self._normalize_workout(raw_workout, user_id)
                yield record, details

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        **kwargs: Any,
    ) -> bool:
        """Load data from Whoop API with pagination."""
        all_workouts = []
        next_token = None
        max_limit = 25  # Whoop API limit

        # Get start/end dates from kwargs (support both 'start'/'end' and 'start_date'/'end_date')
        start = kwargs.get("start") or kwargs.get("start_date")
        end = kwargs.get("end") or kwargs.get("end_date")

        # Default to last 30 days if no dates provided
        if not start:
            start_dt = datetime.now(timezone.utc) - timedelta(days=30)
            start = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(start, datetime):
            start = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(start, str) and "T" not in start:
            # If it's just a date string, convert to ISO 8601
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                start = start_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, AttributeError):
                pass

        if not end:
            end_dt = datetime.now(timezone.utc)
            end = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(end, datetime):
            end = end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(end, str) and "T" not in end:
            # If it's just a date string, convert to ISO 8601
            try:
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                end = end_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, AttributeError):
                pass

        # Fetch all pages
        while True:
            params: dict[str, Any] = {
                "limit": max_limit,
            }

            if start:
                params["start"] = start
            if end:
                params["end"] = end
            if next_token:
                params["nextToken"] = next_token

            try:
                response = self.get_workouts_from_api(db, user_id, **params)

                # Parse response
                if isinstance(response, dict):
                    collection = WhoopWorkoutCollectionJSON(**response)
                else:
                    collection = WhoopWorkoutCollectionJSON(records=[])

                # collection.records is already a list of WhoopWorkoutJSON objects (parsed by Pydantic)
                all_workouts.extend(collection.records)

                # Check for next page
                next_token = collection.next_token

                # Stop if no more records or no next token
                if not collection.records or not next_token:
                    break

            except Exception as e:
                self.logger.error(f"Error fetching Whoop workout data: {e}")
                # If we got some data, continue processing; otherwise re-raise
                if all_workouts:
                    self.logger.warning(f"Processing partial workout data due to error: {e}")
                    break
                raise

        # Process and save all workouts
        for record, details in self._build_bundles(all_workouts, user_id):
            created_record = event_record_service.create(db, record)
            detail_for_record = details.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)

        return True
