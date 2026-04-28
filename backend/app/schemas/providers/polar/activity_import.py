"""Polar AccessLink v3 daily activity response schemas.

Source endpoint: GET /v3/users/activities and GET /v3/users/activities/{date}
Docs: https://www.polar.com/accesslink-api/#daily-activity-summary

Polar's v3 response fields are documented as snake_case, but older/related
endpoints in the same API use hyphenated JSON keys (see HRSamplesJSON in
exercise_import.py). We accept both via `populate_by_name=True` + explicit
hyphen aliases, and tolerate unknown fields so new keys added upstream
don't break parsing.
"""

from pydantic import BaseModel, ConfigDict, Field


class PolarActivityJSON(BaseModel):
    """Single daily activity summary from Polar AccessLink v3."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # --- Time window ---------------------------------------------------------
    start_time: str | None = Field(default=None, validation_alias="start-time")
    end_time: str | None = Field(default=None, validation_alias="end-time")
    created: str | None = None

    # --- Durations (ISO 8601 duration strings, e.g., "PT3H11M") -------------
    active_duration: str | None = Field(default=None, validation_alias="active-duration")
    inactive_duration: str | None = Field(default=None, validation_alias="inactive-duration")

    # --- Metrics -------------------------------------------------------------
    calories: int | None = None
    active_calories: int | None = Field(default=None, validation_alias="active-calories")
    steps: int | None = None
    distance_from_steps: float | None = Field(default=None, validation_alias="distance-from-steps")
    inactivity_alert_count: int | None = Field(default=None, validation_alias="inactivity-alert-count")
    daily_activity: float | None = Field(default=None, validation_alias="daily-activity")
