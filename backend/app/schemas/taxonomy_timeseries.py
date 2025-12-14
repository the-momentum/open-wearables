from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class BiometricType(str, Enum):
    HEART_RATE = "heart_rate"
    HRV = "hrv"
    SPO2 = "spo2"
    BLOOD_GLUCOSE = "blood_glucose"
    TEMPERATURE = "temperature"


class HeartRateSample(BaseModel):
    timestamp: datetime
    bpm: int = Field(..., ge=20, le=250, example=72)
    context: Literal["rest", "sleep", "active", "workout"] | None = Field(
        None, description="Context when measurement was taken"
    )


class StepsSample(BaseModel):
    timestamp: datetime
    count: int = Field(..., ge=0)
    duration_seconds: int | None = Field(None, description="Duration of this sample bucket")


class SleepStageSample(BaseModel):
    start_time: datetime
    end_time: datetime
    stage: Literal["awake", "light", "deep", "rem"]


class BloodGlucoseSample(BaseModel):
    timestamp: datetime
    value_mg_dl: float = Field(..., example=95.0)
    measurement_type: Literal["cgm", "fingerstick", "manual"] | None = None
    trend: Literal["rising_fast", "rising", "stable", "falling", "falling_fast"] | None = Field(
        None, description="CGM trend arrow"
    )


class HrvSample(BaseModel):
    timestamp: datetime
    rmssd_ms: float | None = Field(None, example=42.5)
    sdnn_ms: float | None = Field(None, example=55.2)
    context: Literal["rest", "sleep", "post_workout"] | None = None


class Spo2Sample(BaseModel):
    timestamp: datetime
    percent: float = Field(..., ge=0, le=100, example=97.5)
    context: Literal["rest", "sleep", "active"] | None = None
