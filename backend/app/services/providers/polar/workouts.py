from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

import isodate

from app.config import settings
from app.constants.workout_types.polar import get_unified_workout_type
from app.database import DbSession
from app.models import EventRecordDetail
from app.repositories import EventRecordDetailRepository
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
)
from app.schemas.providers.polar import ExerciseJSON as PolarExerciseJSON
from app.services.event_record_service import event_record_service
from app.services.fit_parser import parse_fit_file
from app.services.providers.api_client import download_binary_content
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.raw_payload_storage import store_fit_file
from app.services.timeseries_service import timeseries_service
from app.utils.dates import offset_to_iso
from app.utils.structured_logging import log_structured

# AccessLink exposes the device's own FIT recording per exercise. No partner
# programme and no callback-URL expiry window (unlike Garmin) — a plain REST pull.
# See https://www.polar.com/accesslink-api/#get-exercise-fit
_FIT_ENDPOINT = "/v3/exercises/{exercise_id}/fit"


class PolarWorkouts(BaseWorkoutsTemplate):
    """Polar implementation of workouts template."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.event_record_detail_repo = EventRecordDetailRepository(EventRecordDetail)

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get exercises from Polar API."""
        return self._make_api_request(db, user_id, "/v3/exercises")

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get exercises from Polar API with options."""
        samples = kwargs.get("samples", False)
        zones = kwargs.get("zones", False)
        route = kwargs.get("route", False)

        params = {
            "samples": str(samples).lower(),
            "zones": str(zones).lower(),
            "route": str(route).lower(),
        }
        return self._make_api_request(db, user_id, "/v3/exercises", params=params)

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed exercise data from Polar API."""
        samples = kwargs.get("samples", False)
        zones = kwargs.get("zones", False)
        route = kwargs.get("route", False)
        return self.get_exercise_detail(db, user_id, workout_id, samples, zones, route)

    def _extract_dates(self, start_timestamp: Any, end_timestamp: Any) -> tuple[datetime, datetime]:
        """Extract start and end dates from timestamps.

        Note: Polar uses a different format with offset, so this delegates to _extract_dates_with_offset.
        This is required by the base template but not used directly.
        """
        raise NotImplementedError("Use _extract_dates_with_offset for Polar workouts")

    def _extract_dates_with_offset(
        self,
        start_time: str,
        start_time_utc_offset: int,
        duration: str,
    ) -> tuple[datetime, datetime]:
        """Extract start and end dates from timestamps with UTC offset."""
        start_date = isodate.parse_datetime(start_time)
        offset = timedelta(minutes=start_time_utc_offset)
        start_date = start_date + offset
        duration_td = isodate.parse_duration(duration)
        end_date = start_date + duration_td
        return start_date, end_date

    def _build_metrics(self, raw_workout: PolarExerciseJSON) -> EventRecordMetrics:
        hr_avg = (
            Decimal(str(raw_workout.heart_rate.average))
            if raw_workout.heart_rate and raw_workout.heart_rate.average is not None
            else None
        )
        hr_max = (
            Decimal(str(raw_workout.heart_rate.maximum))
            if raw_workout.heart_rate and raw_workout.heart_rate.maximum is not None
            else None
        )

        energy_burned = Decimal(str(raw_workout.calories)) if raw_workout.calories is not None else None

        distance = Decimal(str(raw_workout.distance)) if raw_workout.distance is not None else None

        return {
            "heart_rate_max": int(hr_max) if hr_max is not None else None,
            "heart_rate_avg": hr_avg,
            "energy_burned": energy_burned,
            "distance": distance,
        }

    def _normalize_workout(
        self,
        raw_workout: PolarExerciseJSON,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Normalize Polar exercise to EventRecordCreate and EventRecordDetailCreate."""
        workout_id = uuid4()

        workout_type = get_unified_workout_type(raw_workout.sport, raw_workout.detailed_sport_info)

        start_date, end_date = self._extract_dates_with_offset(
            raw_workout.start_time,
            raw_workout.start_time_utc_offset,
            raw_workout.duration,
        )
        duration_seconds = int((end_date - start_date).total_seconds())

        metrics = self._build_metrics(raw_workout)

        # convert from offset minutes to seconds first
        zone_offset = offset_to_iso(raw_workout.start_time_utc_offset * 60)

        record = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name=raw_workout.device,
            device_model=raw_workout.device,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            zone_offset=zone_offset,
            id=workout_id,
            external_id=raw_workout.id,
            source="polar",
            user_id=user_id,
        )

        detail = EventRecordDetailCreate(
            record_id=workout_id,
            **metrics,
        )

        return record, detail

    def _build_bundles(
        self,
        raw: list[PolarExerciseJSON],
        user_id: UUID,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Build event record payloads for Polar exercises."""
        for raw_workout in raw:
            yield self._normalize_workout(raw_workout, user_id)

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        **kwargs: Any,
    ) -> int:
        """Load data from Polar API."""
        workouts_data = self.get_workouts_from_api(db, user_id, **kwargs)
        workouts = [PolarExerciseJSON(**w) for w in workouts_data]

        count = 0
        for record, detail in self._build_bundles(workouts, user_id):
            created_record = event_record_service.create(db, record)
            detail_for_record = detail.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)
            self._ingest_exercise_fit(db, user_id, created_record.id, created_record.external_id)
            count += 1

        return count

    def _ingest_exercise_fit(
        self,
        db: DbSession,
        user_id: UUID,
        record_id: UUID,
        exercise_id: str | None,
    ) -> None:
        """Enrich a saved exercise with the detail only its FIT recording carries.

        The exercise JSON is a summary: total duration, distance, avg/max HR. The FIT
        file the watch recorded is a superset — laps, splits and pool lengths, plus
        time-in-zone — so it is the only route to per-lap data for Polar.

        Deliberately best-effort: the summary row is already committed by the caller,
        and AccessLink has no FIT for every exercise (manual entries, third-party
        uploads), so a miss here is logged and the workout is kept as-is.
        """
        if not exercise_id:
            return

        try:
            fit_bytes = download_binary_content(
                db=db,
                user_id=user_id,
                connection_repo=self.connection_repo,
                oauth=self.oauth,
                provider_name=self.provider_name,
                url=f"{self.api_base_url}{_FIT_ENDPOINT.format(exercise_id=exercise_id)}",
            )
        except Exception as e:
            log_structured(
                self.logger,
                "warning",
                "Failed to download Polar exercise FIT",
                provider=self.provider_name,
                task="_ingest_exercise_fit",
                user_id=str(user_id),
                exercise_id=exercise_id,
                error=str(e),
            )
            return

        if not fit_bytes:
            return

        try:
            store_fit_file(
                provider=self.provider_name,
                fit_bytes=fit_bytes,
                user_id=str(user_id),
                activity_id=exercise_id,
            )
            fit_result = parse_fit_file(fit_bytes, user_id, source=self.provider_name)
            fields: dict[str, Any] = {}
            if fit_result.segments:
                fields["segments"] = fit_result.segments
            if fit_result.hr_zones:
                fields["hr_zones"] = fit_result.hr_zones.model_dump()
            if fit_result.power_zones:
                fields["power_zones"] = fit_result.power_zones.model_dump()
            if fields:
                self.event_record_detail_repo.update_workout_fields(db, record_id, fields)

            samples_saved = 0
            if settings.ingest_workout_samples and fit_result.samples:
                samples_saved = int(timeseries_service.bulk_create_samples(db, fit_result.samples))

            # Both writes above leave the transaction open by contract, and the exercise
            # summary is already committed, so this method has to commit its own work.
            if fields or samples_saved:
                db.commit()
        except Exception as e:
            db.rollback()
            log_structured(
                self.logger,
                "warning",
                "Failed to ingest Polar exercise FIT",
                provider=self.provider_name,
                task="_ingest_exercise_fit",
                user_id=str(user_id),
                exercise_id=exercise_id,
                error=str(e),
            )
            return

        log_structured(
            self.logger,
            "info",
            "Parsed Polar exercise FIT",
            provider=self.provider_name,
            task="_ingest_exercise_fit",
            user_id=str(user_id),
            exercise_id=exercise_id,
            segments=len(fit_result.segments),
            samples=samples_saved,
        )

    def fetch_and_save_exercise(self, db: DbSession, user_id: UUID, path: str) -> int:
        """Fetch a single exercise by URL path and save it. Used by webhook handler."""
        raw = self._make_api_request(db, user_id, path)
        if not raw:
            return 0
        count = 0
        for record, detail in self._build_bundles([PolarExerciseJSON(**raw)], user_id):
            created = event_record_service.create(db, record)
            event_record_service.create_detail(db, detail.model_copy(update={"record_id": created.id}))
            self._ingest_exercise_fit(db, user_id, created.id, created.external_id)
            count += 1
        return count

    def get_exercise_detail(
        self,
        db: DbSession,
        user_id: UUID,
        exercise_id: str,
        samples: bool = False,
        zones: bool = False,
        route: bool = False,
    ) -> dict:
        """Get detailed exercise data from Polar API."""
        params = {
            "samples": str(samples).lower(),
            "zones": str(zones).lower(),
            "route": str(route).lower(),
        }
        return self._make_api_request(db, user_id, f"/v3/exercises/{exercise_id}", params=params)
