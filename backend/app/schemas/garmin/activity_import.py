from pydantic import BaseModel, ConfigDict


class ActivityJSON(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    userId: str
    activityId: str
    summaryId: str
    activityType: str
    startTimeInSeconds: int
    durationInSeconds: int
    deviceName: str

    distanceInMeters: int
    steps: int
    activeKilocalories: int
    averageHeartRateInBeatsPerMinute: int
    maxHeartRateInBeatsPerMinute: int


class RootJSON(BaseModel):
    activities: list[ActivityJSON]
    error: str | None = None
