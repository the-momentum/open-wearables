from typing import Any

from pydantic import BaseModel, ConfigDict


class StravaStream(BaseModel):
    """A single Strava activity stream (one metric sampled over the activity).

    Based on Strava API v3 the `keys` query param. With ``key_by_type=true``
    each stream is nested under its type in the parent object.
    """

    model_config = ConfigDict(populate_by_name=True)

    data: list[Any] = []
    series_type: str | None = None
    original_size: int | None = None
    resolution: str | None = None


class StravaStreamSet(BaseModel):
    """Strava streams response requested with ``key_by_type=true``.

    Returned as an object keyed by stream type (not a list of stream objects).
    Only the streams we ingest are modelled; any other keys are ignored.
    """

    model_config = ConfigDict(populate_by_name=True)

    time: StravaStream | None = None
    heartrate: StravaStream | None = None
    velocity_smooth: StravaStream | None = None
    cadence: StravaStream | None = None
    watts: StravaStream | None = None
