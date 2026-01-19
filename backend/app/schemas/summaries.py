from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common_types import DataSource


class IntensityMinutes(BaseModel):
    light: int | None = None
    moderate: int | None = None
    vigorous: int | None = None


class HeartRateStats(BaseModel):
    """Heart rate statistics for a period."""

    avg_bpm: int | None = None
    max_bpm: int | None = None
    min_bpm: int | None = None


class ActivitySummary(BaseModel):
    date: date
    source: DataSource
    # Step and movement metrics
    steps: int | None = Field(None, description="Total step count", example=8432)
    distance_meters: float | None = Field(None, example=6240.5)
    # Elevation metrics
    floors_climbed: int | None = Field(None, description="Calculated from elevation (1 floor ≈ 3m)", example=12)
    elevation_meters: float | None = Field(None, description="Raw total elevation gain", example=36.0)
    # Energy metrics
    active_calories_kcal: float | None = Field(None, description="Active energy burned", example=342.5)
    total_calories_kcal: float | None = Field(None, description="Active + basal energy", example=2150.0)
    # Duration metrics (based on step threshold)
    active_minutes: int | None = Field(None, description="Minutes with activity above threshold", example=60)
    sedentary_minutes: int | None = Field(None, description="Minutes with minimal activity", example=480)
    # Intensity metrics (based on HR zones)
    intensity_minutes: IntensityMinutes | None = None
    # Heart rate aggregates
    heart_rate: HeartRateStats | None = None


class SleepStagesSummary(BaseModel):
    awake_minutes: int | None = None
    light_minutes: int | None = None
    deep_minutes: int | None = None
    rem_minutes: int | None = None


class SleepSummary(BaseModel):
    date: date
    source: DataSource
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_minutes: int | None = Field(None, description="Total sleep duration excluding naps", example=450)
    time_in_bed_minutes: int | None = Field(None, description="Total time in bed excluding naps", example=480)
    efficiency_percent: float | None = Field(None, ge=0, le=100, example=89.5)
    stages: SleepStagesSummary | None = None
    interruptions_count: int | None = None
    nap_count: int | None = Field(None, description="Number of naps taken", example=1)
    nap_duration_minutes: int | None = Field(None, description="Total nap duration", example=30)
    avg_heart_rate_bpm: int | None = None
    avg_hrv_sdnn_ms: float | None = Field(None, description="Average HRV (SDNN) during sleep")
    avg_respiratory_rate: float | None = None
    avg_spo2_percent: float | None = None


class BloodPressure(BaseModel):
    """Blood pressure statistics aggregated over a period.

    Values are aggregated from multiple readings to provide a more representative measure.
    """

    avg_systolic_mmhg: int | None = Field(None, description="Average systolic pressure", example=120)
    avg_diastolic_mmhg: int | None = Field(None, description="Average diastolic pressure", example=80)
    max_systolic_mmhg: int | None = Field(None, description="Maximum systolic pressure", example=135)
    max_diastolic_mmhg: int | None = Field(None, description="Maximum diastolic pressure", example=90)
    min_systolic_mmhg: int | None = Field(None, description="Minimum systolic pressure", example=110)
    min_diastolic_mmhg: int | None = Field(None, description="Minimum diastolic pressure", example=72)
    reading_count: int | None = Field(None, description="Number of readings in period", example=5)


class BodySummary(BaseModel):
    """Daily body composition and vital statistics summary.

    Combines slow-changing measurements (weight, height, body fat) with
    aggregated vitals (resting HR, HRV, blood pressure) over a rolling period.
    """

    date: date
    source: DataSource
    # Static/demographic
    age: int | None = Field(None, description="Age in years calculated from birth date", example=32)
    # Body composition (latest values)
    height_cm: float | None = Field(None, description="Height in centimeters", example=175.5)
    weight_kg: float | None = Field(None, description="Most recent weight", example=72.5)
    body_fat_percent: float | None = Field(None, description="Most recent body fat percentage", example=18.5)
    muscle_mass_kg: float | None = Field(None, description="Most recent muscle mass", example=58.2)
    bmi: float | None = Field(None, description="Calculated from weight and height", example=23.5)
    # Vitals (7-day rolling averages)
    resting_heart_rate_bpm: int | None = Field(None, description="Average resting heart rate over 7 days", example=62)
    avg_hrv_sdnn_ms: float | None = Field(None, description="Average HRV (SDNN) over 7 days", example=45.2)
    blood_pressure: BloodPressure | None = Field(None, description="Blood pressure averages over 7 days")
    basal_body_temperature_celsius: float | None = Field(None, description="Most recent body temperature", example=36.6)


class RecoverySummary(BaseModel):
    date: date
    source: DataSource
    sleep_duration_seconds: int | None = None
    sleep_efficiency_percent: float | None = None
    resting_heart_rate_bpm: int | None = None
    avg_hrv_sdnn_ms: float | None = Field(None, description="Average HRV (SDNN)")
    avg_spo2_percent: float | None = None
    recovery_score: int | None = Field(None, ge=0, le=100, description="0-100 score")
