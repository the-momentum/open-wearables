from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class OverviewMetric(StrEnum):
    STEPS = "steps"
    SLEEP_MINUTES = "sleep_minutes"
    RESTING_HEART_RATE = "resting_heart_rate"
    ACTIVE_CALORIES = "active_calories"


class OverviewTile(BaseModel):
    """One "Today" tile: today's value against the average of the days before."""

    metric: OverviewMetric
    unit: str = Field(description="count, min, bpm or kcal")
    today: float | None = Field(description="null when nothing is recorded for today yet")
    average: float | None = Field(description="Mean over the previous days that have data")
    delta_percent: float | None = Field(description="today against average, in percent; null without both")


class OverviewPoint(BaseModel):
    date: date
    value: float | None = None


class SdkOverview(BaseModel):
    """A user's own week at a glance, as the instance merges their sources (same as the dashboard).

    Tiles appear only for metrics with data in the period, so an app shows what the user actually records.
    """

    today: date
    days: int
    tiles: list[OverviewTile]
    series: dict[OverviewMetric, list[OverviewPoint]] = Field(
        description="One point per day, oldest first, ending today; for the steps, sleep and heart rate charts"
    )


class DataDeletionRequestResponse(BaseModel):
    notified: bool = Field(description="The organisation was emailed; false when it was already asked today")
