from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


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
    averageRunCadenceInStepsPerMinute: float | None = None
    averageBikingCadenceInRevPerMinute: float | None = None
    averageSwimCadenceInStrokesPerMinute: float | None = None
    totalElevationGainInMeters: float | int | None = None
    totalElevationLossInMeters: float | int | None = None
    elevationGainInMeters: float | int | None = None
    elevationLossInMeters: float | int | None = None
    isWebUpload: bool | None = None
    manual: bool | None = None

    averageCadence: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _unify_cadence(cls, data: Any) -> Any:
        data.setdefault(
            "averageCadence",
            data.get("averageRunCadenceInStepsPerMinute")
            or data.get("averageBikingCadenceInRevPerMinute")
            or data.get("averageSwimCadenceInStrokesPerMinute"),
        )
        return data

    @model_validator(mode="before")
    @classmethod
    def _unify_elevation(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("totalElevationGainInMeters") is None and data.get("elevationGainInMeters") is not None:
                data["totalElevationGainInMeters"] = data["elevationGainInMeters"]
            if data.get("totalElevationLossInMeters") is None and data.get("elevationLossInMeters") is not None:
                data["totalElevationLossInMeters"] = data["elevationLossInMeters"]
        return data


class RootJSON(BaseModel):
    activities: list[ActivityJSON]
    error: str | None = None
