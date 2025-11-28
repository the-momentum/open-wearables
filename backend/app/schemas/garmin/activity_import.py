from pydantic import BaseModel


class ActivityJSON(BaseModel):
    userId: str
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
