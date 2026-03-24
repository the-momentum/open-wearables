from pydantic import BaseModel, ConfigDict


class ActivityJSON(BaseModel):
    """Garmin activity data from push notifications or API responses.

    Push notifications may have optional fields that are not always present.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required fields
    userId: str
    activityId: int | str  # Push sends int, API may send str
    activityType: str
    startTimeInSeconds: int
    durationInSeconds: int

    # Optional fields - may not be present in push notifications
    summaryId: str | None = None
    deviceName: str | None = None
    distanceInMeters: float | int | None = None
    steps: int | None = None
    activeKilocalories: int | None = None
    averageHeartRateInBeatsPerMinute: int | None = None
    maxHeartRateInBeatsPerMinute: int | None = None

    # Push-specific fields
    activityName: str | None = None
    startTimeOffsetInSeconds: int | None = None
    averageSpeedInMetersPerSecond: float | None = None
    isWebUpload: bool | None = None
    manual: bool | None = None


class RootJSON(BaseModel):
    activities: list[ActivityJSON]
    error: str | None = None
