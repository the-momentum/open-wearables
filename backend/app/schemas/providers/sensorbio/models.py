"""Typed Pydantic models for Sensor Bio API response shapes.

Mirrors the Polar pattern (polar/schemas/providers/polar/*.py) for boundary
validation: parse raw API dicts through these before normalization. Any field
that the API guarantees but whose absence would cause a silent data-loss bug is
marked required; optional/supplementary fields use Optional with None defaults.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class BiometricsInSleep(BaseModel):
    """Biometric averages nested inside a /v1/sleep record."""

    bpm: float | None = None
    hrv: float | None = None
    spo2: float | None = None
    resting_bpm: float | None = None
    resting_hrv: float | None = None


class ScoreInSleep(BaseModel):
    """Sleep score nested inside a /v1/sleep record (efficiency 0-100)."""

    value: float | int | None = Field(default=None, ge=0, le=100)


class SleepRecord(BaseModel):
    """Response shape for a single /v1/sleep record.

    NOTE: start_timestamp / end_timestamp are epoch *seconds* even though the
    API introduction claims milliseconds — confirmed against live responses.
    """

    id: str | int | None = None
    start_timestamp: int | float | None = None
    end_timestamp: int | float | None = None
    total_sleep_mins: float | None = None
    deep_sleep_mins: float | None = None
    light_sleep_mins: float | None = None
    rem_sleep_mins: float | None = None
    awake_time_mins: float | None = None
    avg_heart_rate: float | None = None
    biometrics: BiometricsInSleep | None = None
    score: ScoreInSleep | None = None

    @field_validator("biometrics", mode="before")
    @classmethod
    def coerce_biometrics(cls, v: Any) -> Any:
        if v == {} or v is None:
            return None
        return v

    @field_validator("score", mode="before")
    @classmethod
    def coerce_score(cls, v: Any) -> Any:
        if v == {} or v is None:
            return None
        return v


class RecoveryInScores(BaseModel):
    """Recovery sub-object inside a /v1/scores response."""

    value: float | int | None = Field(default=None, ge=0, le=100)
    stage: str | None = None


class BiometricsInScores(BaseModel):
    """Biometric averages nested inside a /v1/scores record."""

    resting_bpm: float | None = None
    resting_hrv: float | None = None
    hrv: float | None = None
    spo2: float | None = None


class ActivityInScores(BaseModel):
    """Activity sub-object inside a /v1/scores response."""

    value: float | int | None = Field(default=None, ge=0, le=100)
    avg: float | int | None = None


class SleepInScores(BaseModel):
    """Sleep sub-object inside a /v1/scores response.

    ``value`` is the 0-100 sleep score from /v1/scores (distinct from
    sleep_efficiency_score on the /v1/sleep EventRecordDetail).
    """

    value: float | int | None = Field(default=None, ge=0, le=100)
    biometrics: BiometricsInScores | None = None

    @field_validator("biometrics", mode="before")
    @classmethod
    def coerce_biometrics(cls, v: Any) -> Any:
        if v == {} or v is None:
            return None
        return v


class ScoresRecord(BaseModel):
    """Response shape for a single /v1/scores record (recovery + activity + sleep).

    The outer wrapper is ``{\"data\": ScoresRecord}`` — we validate the inner
    ``data`` dict, not the envelope.
    """

    date: str | None = None
    recovery: RecoveryInScores | None = None
    sleep: SleepInScores | None = None
    activity: ActivityInScores | None = None

    @field_validator("recovery", mode="before")
    @classmethod
    def coerce_recovery(cls, v: Any) -> Any:
        if v == {} or v is None:
            return None
        return v

    @field_validator("sleep", mode="before")
    @classmethod
    def coerce_sleep(cls, v: Any) -> Any:
        if v == {} or v is None:
            return None
        return v

    @field_validator("activity", mode="before")
    @classmethod
    def coerce_activity(cls, v: Any) -> Any:
        if v == {} or v is None:
            return None
        return v


class BiometricsRecord(BaseModel):
    """A single /v1/biometrics cursor-paginated record."""

    timestamp: int | float  # epoch milliseconds
    bpm: float | None = None
    hrv: float | None = None
    spo2: float | None = None
    brpm: float | None = None


class StepDetailMetric(BaseModel):
    """A single metric entry inside /v1/step/details response.metrics[]."""

    name: str | None = None
    type: str | None = None  # alternative key the API may use
    value: float | int | None = None
    unit: str | None = None


class StepDetailsResponse(BaseModel):
    """Response shape for /v1/step/details (no data wrapper — body IS the record).

    Granularity is always 'day' for our use-case.
    """

    date: str | None = None
    granularity: str | None = None
    metrics: list[StepDetailMetric] = Field(default_factory=list)
    daily_steps_goal: int | None = None
    steps_goal_achieved_percentage: float | None = None


class CardioMetrics(BaseModel):
    """Cardio metrics nested inside an Activity record."""

    avg_bpm: float | None = None
    max_bpm: float | None = None
    min_bpm: float | None = None


class Activity(BaseModel):
    """A single Activity nested inside a WorkoutStats record from /v1/activities."""

    id: str | int | None = None
    start_time: int | float | None = None  # epoch milliseconds
    end_time: int | float | None = None  # epoch milliseconds
    likely_name: str | None = None
    calories: float | None = None
    distance: float | None = None
    active_time: int | float | None = None
    duration: int | float | None = None
    cardio_metrics: CardioMetrics | None = None

    @field_validator("cardio_metrics", mode="before")
    @classmethod
    def coerce_cardio(cls, v: Any) -> Any:
        if v == {} or v is None:
            return None
        return v


class WorkoutStats(BaseModel):
    """A WorkoutStats page record from GET /v1/activities."""

    timestamp: int | float  # epoch milliseconds — cursor field
    name: str | None = None
    activities: list[Activity] = Field(default_factory=list)
