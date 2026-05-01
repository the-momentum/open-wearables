"""Withings workout sync — POST /v2/measure action=getworkouts.

Reference: ``app/services/providers/whoop/workouts.py``. Differences:
- Withings has no strain analog → returns no HealthScoreCreate.
- Pagination via ``more`` / ``offset`` integers (not Whoop's nextToken).
- Workout types are integers; ``constants/workout_types/withings.py`` maps
  them to UnifiedWorkoutType.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.constants.workout_types.withings import get_unified_workout_type
from app.database import DbSession
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
)
from app.schemas.providers.withings import (
    WithingsWorkoutGetworkoutsResponse,
    WithingsWorkoutJSON,
)
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.providers.withings.withings_api_client import post_withings_action
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured


class WithingsWorkouts(BaseWorkoutsTemplate):
    """Withings workouts via /v2/measure action=getworkouts."""

    def _post(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> dict:
        return post_withings_action(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            api_base_url=self.api_base_url,
            endpoint=endpoint,
            action=action,
            params=params,
        )

    def _epoch_to_dt(self, epoch_seconds: int) -> datetime:
        return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)

    def _extract_dates(
        self,
        start_timestamp: int,
        end_timestamp: int,
    ) -> tuple[datetime, datetime]:
        return self._epoch_to_dt(start_timestamp), self._epoch_to_dt(end_timestamp)

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[WithingsWorkoutJSON]:
        """Fetch all workouts in [start_date, end_date], paginated."""
        all_workouts: list[WithingsWorkoutJSON] = []
        offset: int | None = None
        start_ymd = start_date.astimezone(timezone.utc).strftime("%Y-%m-%d")
        end_ymd = end_date.astimezone(timezone.utc).strftime("%Y-%m-%d")

        # All workout-data fields we want returned. Withings only fills the
        # ones the device captured.
        data_fields = ",".join([
            "calories",
            "intensity",
            "manual_distance",
            "distance",
            "elevation",
            "hr_average",
            "hr_min",
            "hr_max",
            "hr_zone_0",
            "hr_zone_1",
            "hr_zone_2",
            "hr_zone_3",
            "spo2_average",
            "steps",
            "pause_duration",
            "pool_laps",
            "strokes",
            "pool_length",
        ])

        while True:
            params: dict[str, Any] = {
                "startdateymd": start_ymd,
                "enddateymd": end_ymd,
                "data_fields": data_fields,
            }
            if offset is not None:
                params["offset"] = offset

            try:
                body = self._post(db, user_id, "/v2/measure", "getworkouts", params=params)
            except Exception as e:
                log_structured(
                    self.logger, "error",
                    f"Error fetching Withings workouts: {e}",
                    provider="withings", task="get_workouts", user_id=str(user_id),
                )
                if all_workouts:
                    break
                raise

            store_raw_payload(
                source="api_response", provider="withings", payload=body,
                user_id=str(user_id), trace_id="/v2/measure:getworkouts",
            )

            try:
                parsed = WithingsWorkoutGetworkoutsResponse(**body)
            except Exception as e:
                log_structured(
                    self.logger, "warning",
                    f"Withings workouts response did not validate: {e}",
                    provider="withings", task="get_workouts", user_id=str(user_id),
                )
                break

            all_workouts.extend(parsed.series)

            if not parsed.more or parsed.offset is None:
                break
            offset = parsed.offset

        return all_workouts

    def _build_metrics(self, workout: WithingsWorkoutJSON) -> EventRecordMetrics:
        """Build EventRecordMetrics from a Withings workout."""
        metrics: EventRecordMetrics = {}
        d = workout.data
        if d is None:
            # Still record moving_time from start/end even with no data block.
            metrics["moving_time_seconds"] = max(0, workout.enddate - workout.startdate)
            return metrics

        if d.hr_average is not None:
            metrics["heart_rate_avg"] = Decimal(str(d.hr_average))
        if d.hr_max is not None:
            metrics["heart_rate_max"] = d.hr_max
        if d.hr_min is not None:
            metrics["heart_rate_min"] = d.hr_min
        if d.calories is not None:
            metrics["energy_burned"] = Decimal(str(d.calories))
        # Distance and elevation in meters per Withings docs.
        if d.distance is not None:
            metrics["distance"] = Decimal(str(d.distance))
        elif d.manual_distance is not None:
            metrics["distance"] = Decimal(str(d.manual_distance))
        if d.elevation is not None:
            metrics["total_elevation_gain"] = Decimal(str(d.elevation))
        elif d.elevation_climbed is not None:
            metrics["total_elevation_gain"] = Decimal(str(d.elevation_climbed))
        if d.steps is not None:
            metrics["steps_count"] = d.steps

        # Moving time = total duration minus pauses.
        total_seconds = max(0, workout.enddate - workout.startdate)
        pause_seconds = (d.pause_duration or 0) + (d.algo_pause_duration or 0)
        metrics["moving_time_seconds"] = max(0, total_seconds - pause_seconds)
        return metrics

    def _normalize_workout(  # type: ignore[override]
        self,
        raw_workout: WithingsWorkoutJSON,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Normalize a Withings workout to (EventRecordCreate, EventRecordDetailCreate)."""
        record_id = uuid4()
        workout_type = get_unified_workout_type(raw_workout.category)
        start_dt, end_dt = self._extract_dates(raw_workout.startdate, raw_workout.enddate)
        duration_seconds = max(0, int((end_dt - start_dt).total_seconds()))
        metrics = self._build_metrics(raw_workout)

        record = EventRecordCreate(
            id=record_id,
            category="workout",
            type=workout_type.value,
            source_name="Withings",
            device_model=None,
            duration_seconds=duration_seconds,
            start_datetime=start_dt,
            end_datetime=end_dt,
            zone_offset=None,  # Withings provides a tz NAME, not a "+/-HH:MM" offset
            external_id=str(raw_workout.id) if raw_workout.id is not None else None,
            source=self.provider_name,
            user_id=user_id,
        )
        detail = EventRecordDetailCreate(record_id=record_id, **metrics)
        return record, detail

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        **kwargs: Any,
    ) -> int:
        """Fetch all workouts in the requested window, normalize, and save.

        Mirrors Whoop's load_data() shape. Returns the count of workouts saved.
        """
        # Resolve start/end from kwargs with the same flexibility Whoop has.
        start = kwargs.get("start") or kwargs.get("start_date")
        end = kwargs.get("end") or kwargs.get("end_date")

        if not start:
            start = datetime.now(timezone.utc) - timedelta(days=30)
        elif isinstance(start, str):
            try:
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                start = datetime.now(timezone.utc) - timedelta(days=30)
        if not end:
            end = datetime.now(timezone.utc)
        elif isinstance(end, str):
            try:
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                end = datetime.now(timezone.utc)

        all_workouts = self.get_workouts(db, user_id, start, end)

        count = 0
        for raw_workout in all_workouts:
            try:
                record, detail = self._normalize_workout(raw_workout, user_id)
                created = event_record_service.create(db, record)
                detail_for_record = detail.model_copy(update={"record_id": created.id})
                event_record_service.create_detail(db, detail_for_record)
                count += 1
            except Exception as e:
                log_structured(
                    self.logger, "warning",
                    f"Failed to save Withings workout (external_id={getattr(raw_workout, 'id', None)}): {e}",
                    provider="withings", task="load_data", user_id=str(user_id),
                )

        return count
