from pydantic import BaseModel, Field


class HeartRateJSON(BaseModel):
    average: int
    maximum: int


# unused for now - time series data
class HRSamplesJSON(BaseModel):
    recording_rate: int = Field(alias="recording-rate")
    sample_type: str = Field(alias="sample-type")
    data: str


class HRZoneJSON(BaseModel):
    index: int
    lower_limit: int = Field(alias="lower-limit")
    upper_limit: int = Field(alias="upper-limit")
    in_zone: str = Field(alias="in-zone")


class ExerciseJSON(BaseModel):
    id: str
    sport: str
    device: str

    start_time: str
    start_time_utc_offset: int
    duration: str

    calories: int
    distance: int
    heart_rate: HeartRateJSON
