"""Withings workouts (``getworkouts``) → unified EventRecord + EventRecordDetail."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.constants.workout_types.withings import get_unified_workout_type
from app.database import DbSession
from app.schemas.model_crud.activities import EventRecordCreate, EventRecordDetailCreate
from app.schemas.providers.withings import WithingsWorkout
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.providers.withings._client import paginate

logger = logging.getLogger(__name__)

_WORKOUT_FIELDS = "calories,steps,distance,hr_average,hr_min,hr_max,elevation"


class WithingsWorkouts(BaseWorkoutsTemplate):
    """Withings workouts handler."""

    def get_workouts(self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime) -> list[Any]:
        return self.get_workouts_from_api(
            db,
            user_id,
            startdateymd=start_date.strftime("%Y-%m-%d"),
            enddateymd=end_date.strftime("%Y-%m-%d"),
        )

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> list[dict]:
        # Accept Withings-native ymd keys or the generic ISO keys the sync task emits.
        start_ymd = kwargs.get("startdateymd") or self._to_ymd(kwargs.get("start_date"))
        end_ymd = kwargs.get("enddateymd") or self._to_ymd(kwargs.get("end_date"))
        params = {
            "startdateymd": start_ymd,
            "enddateymd": end_ymd,
            "data_fields": _WORKOUT_FIELDS,
        }
        return paginate(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path="/v2/measure",
            action="getworkouts",
            params={k: v for k, v in params.items() if v is not None},
            list_key="series",
        )

    @staticmethod
    def _to_ymd(value: Any) -> str | None:
        """Convert an ISO datetime string or ``datetime`` to ``YYYY-MM-DD``.

        Returns ``None`` for falsy inputs or values that cannot be parsed.
        """
        if not value:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    def _normalize_workout(
        self, raw_workout: WithingsWorkout, user_id: UUID
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        start_dt = datetime.fromtimestamp(raw_workout.startdate, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(raw_workout.enddate, tz=timezone.utc)
        workout_type = get_unified_workout_type(raw_workout.category)
        data = raw_workout.data
        record_id = uuid4()

        record = EventRecordCreate(
            id=record_id,
            category="workout",
            type=workout_type.value,
            source_name="Withings",
            duration_seconds=int(end_dt.timestamp() - start_dt.timestamp()),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=str(raw_workout.id) if raw_workout.id is not None else None,
            source=self.provider_name,
            user_id=user_id,
        )
        detail = EventRecordDetailCreate(
            record_id=record_id,
            heart_rate_avg=Decimal(str(data.hr_average)) if data.hr_average is not None else None,
            heart_rate_min=data.hr_min,
            heart_rate_max=data.hr_max,
            steps_count=data.steps,
            energy_burned=Decimal(str(data.calories)) if data.calories is not None else None,
            distance=Decimal(str(data.distance)) if data.distance is not None else None,
            total_elevation_gain=Decimal(str(data.elevation)) if data.elevation is not None else None,
        )
        return record, detail

    def load_data(self, db: DbSession, user_id: UUID, **kwargs: Any) -> int:
        raw_workouts = self.get_workouts_from_api(db, user_id, **kwargs)
        count = 0
        for raw in raw_workouts:
            # Tolerate a malformed record without dropping the rest of the batch.
            try:
                workout = WithingsWorkout.model_validate(raw)
            except ValidationError as e:
                logger.warning("Skipping unparseable Withings workout: %s", e)
                continue
            # A null deviceid marks a workout imported from a foreign source (e.g.
            # Health Connect); skip it so the origin connector isn't double-counted.
            if workout.deviceid is None:
                logger.debug("Skipping imported Withings workout %s (no deviceid)", workout.id)
                continue
            try:
                record, detail = self._normalize_workout(workout, user_id)
                # create() dedups on the (source, start, end) window and returns the
                # canonical record; the detail FK must point at its id, not ours.
                created = event_record_service.create(db, record)
                event_record_service.create_detail(db, detail.model_copy(update={"record_id": created.id}))
                count += 1
            except Exception as e:
                # Reset the session so one bad record doesn't poison the batch.
                db.rollback()
                logger.warning("Failed to save Withings workout: %s", e)
                continue
        return count
