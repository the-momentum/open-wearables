from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common_types import SourceMetadata


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
    source: SourceMetadata
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
    source: SourceMetadata
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


class BodySlowChanging(BaseModel):
    """Slow-changing body composition metrics.

    These are metrics that change infrequently (days/weeks between measurements).
    Returns the most recent recorded value for each field.
    """

    weight_kg: float | None = Field(None, description="Most recent weight measurement", example=72.5)
    height_cm: float | None = Field(None, description="Most recent height measurement", example=175.5)
    body_fat_percent: float | None = Field(None, description="Most recent body fat percentage", example=18.5)
    muscle_mass_kg: float | None = Field(None, description="Most recent muscle/lean body mass", example=58.2)
    bmi: float | None = Field(None, description="Calculated from latest weight and height", example=23.5)
    age: int | None = Field(None, description="Age in years calculated from birth date", example=32)


class BodyAveraged(BaseModel):
    """Vitals averaged over a configurable time period.

    These metrics fluctuate daily and are more meaningful as averages.
    Period can be 1 day (current state) or 7 days (baseline trend).
    """

    period_days: int = Field(..., description="Number of days averaged (1 or 7)", example=7)
    resting_heart_rate_bpm: int | None = Field(None, description="Average resting heart rate", example=62)
    avg_hrv_sdnn_ms: float | None = Field(None, description="Average HRV (SDNN)", example=45.2)
    period_start: datetime = Field(..., description="Start of averaging period")
    period_end: datetime = Field(..., description="End of averaging period")


class BodyLatest(BaseModel):
    """Point-in-time metrics that are only relevant when recent.

    These metrics are only returned if measured within a configurable time window.
    Stale readings return null to avoid displaying outdated data.
    """

    body_temperature_celsius: float | None = Field(
        None, description="Body temperature if measured within time window", example=36.6
    )
    body_temperature_measured_at: datetime | None = Field(
        None, description="When body temperature was measured (null if no recent reading)"
    )
    skin_temperature_celsius: float | None = Field(
        None, description="Skin temperature if measured within time window", example=36.6
    )
    skin_temperature_measured_at: datetime | None = Field(
        None, description="When skin temperature was measured (null if no recent reading)"
    )
    blood_pressure: BloodPressure | None = Field(None, description="Blood pressure if measured within time window")
    blood_pressure_measured_at: datetime | None = Field(
        None, description="When blood pressure was measured (null if no recent reading)"
    )


class BodySummary(BaseModel):
    """Comprehensive body metrics with semantic grouping.

    Metrics are grouped by their temporal characteristics:
    - slow_changing: Slow-changing values (latest measurement)
    - averaged: Vitals averaged over a period (1 or 7 days)
    - latest: Point-in-time readings (only if recent)
    """

    source: SourceMetadata
    slow_changing: BodySlowChanging
    averaged: BodyAveraged
    latest: BodyLatest


class RecoverySummary(BaseModel):
    date: date
    source: SourceMetadata
    sleep_duration_seconds: int | None = None
    sleep_efficiency_percent: float | None = None
    resting_heart_rate_bpm: int | None = None
    avg_hrv_sdnn_ms: float | None = Field(None, description="Average HRV (SDNN)")
    avg_spo2_percent: float | None = None
    recovery_score: int | None = Field(None, ge=0, le=100, description="0-100 score")
