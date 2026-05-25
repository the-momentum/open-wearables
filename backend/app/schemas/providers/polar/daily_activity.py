from pydantic import BaseModel


class StepSampleJSON(BaseModel):
    steps: int
    timestamp: str


class StepsJSON(BaseModel):
    interval_ms: int
    total_steps: int
    samples: list[StepSampleJSON]


class ActivityZoneSampleJSON(BaseModel):
    zone: str
    timestamp: str


class ActivityZonesJSON(BaseModel):
    samples: list[ActivityZoneSampleJSON]


class DailyActivitySamplesJSON(BaseModel):
    date: str | None = None
    steps: StepsJSON | None = None
    activity_zones: ActivityZonesJSON | None = None
    inactivity_stamps: list[str] | None = None


class DailyActivityJSON(BaseModel):
    start_time: str | None = None
    end_time: str | None = None
    active_duration: str | None = None
    inactive_duration: str | None = None
    daily_activity: float | None = None
    calories: int | None = None
    active_calories: int | None = None
    steps: int | None = None
    inactivity_alert_count: int | None = None
    distance_from_steps: float | None = None  # meters
    samples: DailyActivitySamplesJSON | None = None
