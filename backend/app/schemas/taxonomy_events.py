from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, RootModel

from app.schemas.taxonomy_common import DataSource
from app.schemas.taxonomy_summaries import SleepStagesSummary
from app.schemas.taxonomy_timeseries import HeartRateSample


class WorkoutType(RootModel[str]):
    # Using str for now as enum might be extensive, but RFC lists specific values
    # running, walking, cycling, swimming, strength_training, hiit, yoga, pilates, rowing, elliptical, hiking, other
    pass


class Workout(BaseModel):
    id: UUID
    type: str  # Should be WorkoutType enum ideally
    name: str | None = Field(None, example="Morning Run")
    start_time: datetime
    end_time: datetime
    duration_seconds: int | None = None
    source: DataSource
    calories_kcal: float | None = None
    distance_meters: float | None = None
    avg_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None
    avg_pace_sec_per_km: int | None = None
    elevation_gain_meters: float | None = None


class WorkoutDetailed(Workout):
    heart_rate_samples: list[HeartRateSample] | None = None


class Macros(BaseModel):
    protein_g: float | None = None
    carbohydrates_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None


class Meal(BaseModel):
    id: UUID
    timestamp: datetime
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] | None = None
    name: str | None = None
    source: DataSource
    calories_kcal: float | None = None
    macros: Macros | None = None
    water_ml: float | None = None


class Measurement(BaseModel):
    id: UUID
    type: Literal["weight", "blood_pressure", "body_composition", "temperature", "blood_glucose"]
    timestamp: datetime
    source: DataSource
    values: dict[str, float | str] = Field(..., description="Measurement-specific values", example={"weight_kg": 72.5})


class SleepSession(BaseModel):
    id: UUID
    start_time: datetime
    end_time: datetime
    source: DataSource
    duration_seconds: int
    efficiency_percent: float | None = None
    stages: SleepStagesSummary | None = None
    is_nap: bool = False
