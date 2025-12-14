from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.taxonomy_common import DataSource


class IntensityMinutes(BaseModel):
    light: int | None = None
    moderate: int | None = None
    vigorous: int | None = None


class ActivitySummary(BaseModel):
    date: date
    source: DataSource
    steps: int | None = Field(None, description="Total step count", example=8432)
    distance_meters: float | None = Field(None, example=6240.5)
    floors_climbed: int | None = Field(None, example=12)
    active_calories_kcal: float | None = Field(None, example=342.5)
    total_calories_kcal: float | None = Field(None, example=2150.0)
    active_duration_seconds: int | None = Field(None, description="Total active time", example=3600)
    sedentary_duration_seconds: int | None = Field(None, example=28800)
    intensity_minutes: IntensityMinutes | None = None


class SleepStagesSummary(BaseModel):
    awake_seconds: int | None = None
    light_seconds: int | None = None
    deep_seconds: int | None = None
    rem_seconds: int | None = None


class SleepSummary(BaseModel):
    date: date
    source: DataSource
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: int | None = Field(None, example=27000)
    time_in_bed_seconds: int | None = Field(None, example=28800)
    efficiency_percent: float | None = Field(None, ge=0, le=100, example=89.5)
    latency_seconds: int | None = Field(None, description="Time to fall asleep", example=480)
    stages: SleepStagesSummary | None = None
    interruptions_count: int | None = None
    avg_heart_rate_bpm: int | None = None
    avg_hrv_rmssd_ms: float | None = None
    avg_respiratory_rate: float | None = None
    avg_spo2_percent: float | None = None


class BloodPressure(BaseModel):
    systolic_mmhg: int | None = None
    diastolic_mmhg: int | None = None


class BodySummary(BaseModel):
    date: date
    source: DataSource
    weight_kg: float | None = Field(None, example=72.5)
    body_fat_percent: float | None = None
    muscle_mass_kg: float | None = None
    bmi: float | None = None
    resting_heart_rate_bpm: int | None = Field(None, example=62)
    avg_hrv_rmssd_ms: float | None = Field(None, example=45.2)
    blood_pressure: BloodPressure | None = None
    basal_body_temperature_celsius: float | None = None


class RecoverySummary(BaseModel):
    date: date
    source: DataSource
    sleep_duration_seconds: int | None = None
    sleep_efficiency_percent: float | None = None
    resting_heart_rate_bpm: int | None = None
    avg_hrv_rmssd_ms: float | None = None
    avg_spo2_percent: float | None = None
    recovery_score: int | None = Field(None, ge=0, le=100, description="0-100 score")
