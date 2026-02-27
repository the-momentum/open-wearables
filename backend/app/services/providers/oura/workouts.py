"""Oura Ring workouts implementation."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from app.constants.workout_types.oura import get_unified_workout_type
from app.database import DbSession
from app.schemas import EventRecordCreate, EventRecordDetailCreate, EventRecordMetrics
from app.schemas.oura.imports import OuraWorkoutCollectionJSON, OuraWorkoutJSON
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.utils.structured_logging import log_structured


class OuraWorkouts(BaseWorkoutsTemplate):
    """Oura implementation of workouts template."""

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get workouts from Oura API with pagination."""
        all_workouts: list[OuraWorkoutJSON] = []
        next_token: str | None = None

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        while True:
            params: dict[str, Any] = {
                "start_date": start_str,
                "end_date": end_str,
            }
            if next_token:
                params["next_token"] = next_token

            try:
                response = self._make_api_request(db, user_id, "/v2/usercollection/workout", params=params)

                if isinstance(response, dict):
                    collection = OuraWorkoutCollectionJSON(**response)
                else:
                    collection = OuraWorkoutCollectionJSON(data=[])

                all_workouts.extend(collection.data)

                next_token = collection.next_token
                if not collection.data or not next_token:
                    break

            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    "Error fetching Oura workout data",
                    action="oura_workout_fetch_error",
                    error=str(e),
                )
                if all_workouts:
                    log_structured(
                        self.logger,
                        "warning",
                        "Returning partial workout data due to error",
                        action="oura_workout_partial_data",
                        error=str(e),
                    )
                    break
                raise

        return all_workouts

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get workouts from Oura API with specific options."""
        params: dict[str, Any] = {}
        if kwargs.get("start_date"):
            params["start_date"] = kwargs["start_date"]
        if kwargs.get("end_date"):
            params["end_date"] = kwargs["end_date"]
        if kwargs.get("next_token"):
            params["next_token"] = kwargs["next_token"]

        return self._make_api_request(db, user_id, "/v2/usercollection/workout", params=params)

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed workout data from Oura API."""
        return self._make_api_request(db, user_id, f"/v2/usercollection/workout/{workout_id}")

    def _extract_dates(self, start_timestamp: str, end_timestamp: str) -> tuple[datetime, datetime]:
        """Extract start and end dates from ISO 8601 strings."""
        start_date = datetime.fromisoformat(start_timestamp.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_timestamp.replace("Z", "+00:00"))

        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        return start_date, end_date

    def _build_metrics(self, raw_workout: OuraWorkoutJSON) -> EventRecordMetrics:
        """Build metrics from Oura workout data."""
        metrics: EventRecordMetrics = {}

        if raw_workout.calories is not None:
            metrics["energy_burned"] = Decimal(str(raw_workout.calories))

        if raw_workout.distance is not None:
            metrics["distance"] = Decimal(str(raw_workout.distance))

        if raw_workout.start_datetime and raw_workout.end_datetime:
            start_dt, end_dt = self._extract_dates(raw_workout.start_datetime, raw_workout.end_datetime)
            duration_seconds = int((end_dt - start_dt).total_seconds())
            metrics["moving_time_seconds"] = duration_seconds

        return metrics

    def _normalize_workout(
        self,
        raw_workout: OuraWorkoutJSON,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Normalize Oura workout to EventRecordCreate and EventRecordDetailCreate."""
        workout_id = uuid4()

        workout_type = get_unified_workout_type(raw_workout.activity)

        if raw_workout.start_datetime and raw_workout.end_datetime:
            start_date, end_date = self._extract_dates(raw_workout.start_datetime, raw_workout.end_datetime)
        else:
            start_date = datetime.now(timezone.utc)
            end_date = start_date
        duration_seconds = int((end_date - start_date).total_seconds())

        metrics = self._build_metrics(raw_workout)

        workout_create = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name="Oura",
            device_model=None,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            id=workout_id,
            external_id=raw_workout.id,
            source=self.provider_name,
            user_id=user_id,
        )

        workout_detail_create = EventRecordDetailCreate(
            record_id=workout_id,
            **metrics,
        )

        return workout_create, workout_detail_create

    def _build_bundles(
        self,
        raw: list[OuraWorkoutJSON],
        user_id: UUID,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Build event record payloads for Oura workouts."""
        for raw_workout in raw:
            record, details = self._normalize_workout(raw_workout, user_id)
            yield record, details

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        **kwargs: Any,
    ) -> bool:
        """Load data from Oura API with pagination."""
        start = kwargs.get("start") or kwargs.get("start_date")
        end = kwargs.get("end") or kwargs.get("end_date")

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

        all_workouts = self.get_workouts(db, user_id, start_dt, end_dt)

        for record, details in self._build_bundles(all_workouts, user_id):
            created_record = event_record_service.create(db, record)
            detail_for_record = details.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)

        return True
