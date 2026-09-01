from pydantic import BaseModel, Field

_DESCRIPTION_DOC: str = (
    "Optional human-readable clarification of what this data type represents. Empty when none is defined."
)


class TimeseriesMetric(BaseModel):
    code: str
    unit: str
    description: str = Field(default="", description=_DESCRIPTION_DOC)
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


class MenstrualCycleField(BaseModel):
    code: str
    providers: list[str]


class HealthScore(BaseModel):
    code: str
    description: str = Field(default="", description=_DESCRIPTION_DOC)
    providers: list[str]


class CoverageResponse(BaseModel):
    providers: list[str]
    timeseries: list[TimeseriesCategory]
    workout_fields: list[WorkoutField]
    sleep_fields: list[SleepField]
    menstrual_cycle_fields: list[MenstrualCycleField]
    health_scores: list[HealthScore]
