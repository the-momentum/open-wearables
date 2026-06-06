"""Sensor Bio workouts implementation."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from app.constants.workout_types.sensorbio import get_unified_workout_type
from app.database import DbSession
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
)
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured


class SensorBioWorkouts(BaseWorkoutsTemplate):
    """Sensor Bio implementation of workout syncing.

    API response shape (GET /v1/activities):
      {
        "data": [WorkoutStats, ...],
        "links": { "next": "..." }
      }

    WorkoutStats:
      { "timestamp": <ms>, "name": "Run", "activities": [Activity, ...] }

    Activity:
      { "start_time": <ms>, "end_time": <ms>, "likely_name": "Run",
        "calories": ..., "distance": ..., "active_time": ...,
        "duration": ..., "cardio_metrics": {...}, ... }

    Pagination cursor: WorkoutStats.timestamp (already milliseconds — used as-is).
    """

    def _make_api_request(  # type: ignore[override]
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        """Make an authenticated request using HTTP/2 and store raw payload.

        Sensor Bio requires HTTP/2 (see API docs). Overrides the base
        implementation to pass ``http2=True``; other providers that use the
        shared api_client are unaffected.

        All successful responses are stored via store_raw_payload() for
        observability — mirrors polar/data_247.py ~98-103.
        """
        result = make_authenticated_request(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            api_base_url=self.api_base_url,
            provider_name=self.provider_name,
            endpoint=endpoint,
            method=method,
            params=params,
            headers=headers,
            json_data=json_data,
            http2=True,
        )
        store_raw_payload(
            source="api_response",
            provider="sensorbio",
            payload=result,
            user_id=str(user_id),
            trace_id=endpoint,
        )
        return result

    @staticmethod
    def _from_epoch_millis(timestamp: int | float | None) -> datetime | None:
        """Convert Unix epoch milliseconds to UTC datetime."""
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc) if timestamp is not None else None

    def get_workouts(self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime) -> list[Any]:
        """Fetch and flatten Activity records from /v1/activities within the date window.

        The API returns pages of WorkoutStats, each containing a nested
        ``activities`` list.  We iterate the nested activities and filter by
        their start_time (ms).

        Pagination cursor is WorkoutStats.timestamp (ms) — used directly as
        ``last-timestamp``; no *1000 heuristic needed because the spec states
        the field is already milliseconds.
        """
        all_workouts: list[dict[str, Any]] = []
        last_timestamp = 0
        limit = 50
        while True:
            try:
                response = self._make_api_request(
                    db, user_id, "/v1/activities", params={"last-timestamp": last_timestamp, "limit": limit}
                )
                # data: WorkoutStats[]
                records = response.get("data", []) if isinstance(response, dict) else []
                if not isinstance(records, list) or not records:
                    break

                for workout_stats in records:
                    # Each WorkoutStats contains nested Activity objects
                    activities = workout_stats.get("activities") or []
                    for activity in activities:
                        start_dt = self._from_epoch_millis(activity.get("start_time"))
                        if start_dt and start_date <= start_dt <= end_date:
                            # Attach workout-level name as context for type mapping
                            activity.setdefault("_workout_name", workout_stats.get("name"))
                            all_workouts.append(activity)

                # Cursor: WorkoutStats.timestamp is already in milliseconds per spec.
                next_cursor = records[-1].get("timestamp")
                if next_cursor is None:
                    break
                next_cursor_int = int(next_cursor)
                if next_cursor_int == last_timestamp:
                    break
                last_timestamp = next_cursor_int

                if not (response.get("links") or {}).get("next"):
                    break
            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    f"Error fetching Sensor Bio workout data: {e}",
                    provider="sensorbio",
                    task="get_workouts",
                )
                if all_workouts:
                    log_structured(
                        self.logger,
                        "warning",
                        f"Returning partial workout data due to error: {e}",
                        provider="sensorbio",
                        task="get_workouts",
                    )
                    break
                raise
        return all_workouts

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        limit = min(int(kwargs.get("limit", 50)), 50)
        last_timestamp = int(kwargs.get("last-timestamp", kwargs.get("last_timestamp", 0)))
        return self._make_api_request(
            db, user_id, "/v1/activities", params={"last-timestamp": last_timestamp, "limit": limit}
        )

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        raise NotImplementedError("Sensor Bio does not support API-based workout detail fetching")

    def _extract_dates(
        self,
        start_timestamp: int | float | None,
        end_timestamp: int | float | None,
    ) -> tuple[datetime, datetime]:
        """Convert Activity.start_time / end_time (ms) to datetime."""
        start_date = self._from_epoch_millis(start_timestamp)
        end_date = self._from_epoch_millis(end_timestamp)
        now = datetime.now(timezone.utc)
        return start_date or now, end_date or start_date or now

    def _build_metrics(self, raw_workout: dict[str, Any]) -> EventRecordMetrics:
        metrics: EventRecordMetrics = {}
        cardio_metrics = raw_workout.get("cardio_metrics", {}) or {}
        if cardio_metrics.get("avg_bpm") is not None:
            metrics["heart_rate_avg"] = Decimal(str(cardio_metrics["avg_bpm"]))
        if cardio_metrics.get("max_bpm") is not None:
            metrics["heart_rate_max"] = int(cardio_metrics["max_bpm"])
        if cardio_metrics.get("min_bpm") is not None:
            metrics["heart_rate_min"] = int(cardio_metrics["min_bpm"])
        if raw_workout.get("calories") is not None:
            metrics["energy_burned"] = Decimal(str(raw_workout["calories"]))
        if raw_workout.get("distance") is not None:
            metrics["distance"] = Decimal(str(raw_workout["distance"]))
        if raw_workout.get("active_time") is not None:
            metrics["moving_time_seconds"] = int(raw_workout["active_time"])
        return metrics

    def _normalize_workout(
        self, raw_workout: dict[str, Any], user_id: UUID
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        workout_id = uuid4()
        # Per spec, Activity.likely_name is the type field; no raw "type" field.
        # Fall back to the parent WorkoutStats.name (stashed as _workout_name).
        workout_type = get_unified_workout_type(raw_workout.get("likely_name") or raw_workout.get("_workout_name"))
        start_date, end_date = self._extract_dates(raw_workout.get("start_time"), raw_workout.get("end_time"))
        duration_seconds = int(raw_workout.get("duration") or max(int((end_date - start_date).total_seconds()), 0))
        metrics = self._build_metrics(raw_workout)
        workout_create = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name="Sensor Bio",
            device_model=None,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            id=workout_id,
            external_id=str(raw_workout.get("id")) if raw_workout.get("id") is not None else None,
            source=self.provider_name,
            user_id=user_id,
        )
        workout_detail_create = EventRecordDetailCreate(record_id=workout_id, **metrics)
        return workout_create, workout_detail_create

    def _build_bundles(
        self, raw: list[dict[str, Any]], user_id: UUID
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        for raw_workout in raw:
            yield self._normalize_workout(raw_workout, user_id)

    def load_data(self, db: DbSession, user_id: UUID, **kwargs: Any) -> int:
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
        count = 0
        for record, details in self._build_bundles(all_workouts, user_id):
            created_record = event_record_service.create(db, record)
            detail_for_record = details.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)
            count += 1
        return count
