from datetime import datetime

import isodate
from pydantic import BaseModel

_EXERCISE_ZONES = frozenset({"MODERATE", "VIGOROUS"})


class StepSampleJSON(BaseModel):
    steps: int
    timestamp: str


class StepsJSON(BaseModel):
    interval_ms: int
    total_steps: int
    samples: list[StepSampleJSON]


class ActivityZoneSampleJSON(BaseModel):
    zone: str | None = None
    timestamp: str | None = None


class ActivityZonesJSON(BaseModel):
    samples: list[ActivityZoneSampleJSON] | None = None


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

    @property
    def basal_calories(self) -> int | None:
        """Total ``calories`` (incl. BMR) minus ``active_calories`` (excl. BMR)."""
        if self.calories is None or self.active_calories is None:
            return None
        basal = self.calories - self.active_calories
        return basal if basal > 0 else None

    @property
    def active_time_minutes(self) -> int | None:
        """Parse the ISO-8601 ``active_duration`` (e.g. "PT1H30M") into whole minutes."""
        if not self.active_duration:
            return None
        try:
            return int(isodate.parse_duration(self.active_duration).total_seconds() // 60)
        except (ValueError, isodate.ISO8601Error, AttributeError):
            return None

    @property
    def exercise_time_minutes(self) -> int | None:
        """Whole minutes the day spent in the MODERATE and VIGOROUS activity zones.

        A zone sample marks where a segment starts; it lasts until the next sample, the last
        one until ``end_time``. None when the day carries no zone samples or a sample lacks its
        zone or a readable timestamp, since the day's split is then unknown.
        """
        zones = self.samples.activity_zones if self.samples else None
        if not zones or not zones.samples or not self.end_time:
            return None
        labelled = [(s.timestamp, s.zone) for s in zones.samples if s.timestamp and s.zone]
        if len(labelled) != len(zones.samples):
            return None
        try:
            segments = sorted((datetime.fromisoformat(ts).replace(tzinfo=None), zone) for ts, zone in labelled)
            day_end = datetime.fromisoformat(self.end_time).replace(tzinfo=None)
        except ValueError:
            return None
        ends = [start for start, _ in segments[1:]] + [day_end]
        seconds = sum(
            (end - start).total_seconds()
            for (start, zone), end in zip(segments, ends, strict=True)
            if zone in _EXERCISE_ZONES and end > start
        )
        return int(seconds // 60)
