from pydantic import BaseModel


class TimeseriesMetric(BaseModel):
    code: str
    unit: str
    providers: list[str]


class TimeseriesCategory(BaseModel):
    name: str
    metrics: list[TimeseriesMetric]


class WorkoutField(BaseModel):
    code: str
    providers: list[str]


class SleepField(BaseModel):
    code: str
    providers: list[str]


class HealthScore(BaseModel):
    code: str
    providers: list[str]


class CoverageResponse(BaseModel):
    providers: list[str]
    timeseries: list[TimeseriesCategory]
    workout_fields: list[WorkoutField]
    sleep_fields: list[SleepField]
    health_scores: list[HealthScore]
