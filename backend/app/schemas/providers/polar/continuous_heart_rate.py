from pydantic import BaseModel


class HeartRateSampleJSON(BaseModel):
    heart_rate: int
    sample_time: str


class ContinuousHeartRateJSON(BaseModel):
    polar_user: str
    date: str
    heart_rate_samples: list[HeartRateSampleJSON]
