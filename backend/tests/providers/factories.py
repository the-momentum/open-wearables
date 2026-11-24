"""Model-backed provider data for tests; keep real API examples in contract tests."""

from typing import Any

from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.field_meta import FieldMeta
from pydantic import BaseModel

from app.schemas.providers.garmin import ActivityJSON as GarminActivityJSON
from app.schemas.providers.oura import OuraDailyReadinessJSON, OuraSleepJSON, OuraWorkoutJSON
from app.schemas.providers.polar import ExerciseJSON as PolarExerciseJSON
from app.schemas.providers.suunto import WorkoutJSON as SuuntoWorkoutJSON


class ProviderPayloadFactory[T: BaseModel](ModelFactory[T]):
    """Generate required fields while leaving optional data at its schema defaults.

    Subclasses supply meaningful dates/durations where the schema only says str/int.
    Tests must pin scenario-specific values and IDs instead of asserting on random filler.
    """

    __is_base_factory__ = True
    __use_defaults__ = True
    __by_name__ = True

    @classmethod
    def should_use_default_value(cls, field_meta: FieldMeta) -> bool:
        """Prefer explicit factory values over schema defaults, including optional dates."""
        return not hasattr(cls, field_meta.name) and super().should_use_default_value(field_meta)

    @classmethod
    def build_payload(cls, **kwargs: Any) -> dict[str, Any]:
        """Return JSON-compatible provider keys, omitting absent optional fields."""
        return cls.build(**kwargs).model_dump(mode="json", by_alias=True, exclude_none=True)


class GarminActivityFactory(ProviderPayloadFactory[GarminActivityJSON]):
    userId = "garmin_user_123"
    activityType = "RUNNING"
    startTimeInSeconds = 1705309200
    durationInSeconds = 3600


class PolarExerciseFactory(ProviderPayloadFactory[PolarExerciseJSON]):
    device = "Polar Vantage V2"
    sport = "RUNNING"
    start_time = "2024-01-15T08:00:00"
    start_time_utc_offset = 60
    duration = "PT1H0M0S"


class SuuntoWorkoutFactory(ProviderPayloadFactory[SuuntoWorkoutJSON]):
    workoutId = 0
    activityId = 1
    startTime = 1705309200000
    stopTime = 1705312800000
    totalTime = 3600.0


class OuraWorkoutFactory(ProviderPayloadFactory[OuraWorkoutJSON]):
    day = "2024-01-15"
    start_datetime = "2024-01-15T08:00:00+00:00"
    end_datetime = "2024-01-15T09:00:00+00:00"


class OuraSleepFactory(ProviderPayloadFactory[OuraSleepJSON]):
    day = "2024-01-15"
    bedtime_start = "2024-01-14T23:00:00+00:00"
    bedtime_end = "2024-01-15T07:00:00+00:00"


class OuraReadinessFactory(ProviderPayloadFactory[OuraDailyReadinessJSON]):
    day = "2024-01-15"
    timestamp = "2024-01-15T07:00:00+00:00"
