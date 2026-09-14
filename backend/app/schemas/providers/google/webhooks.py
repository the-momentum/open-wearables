"""Google Health API webhook notification schema.

Google sends notify-only pings: the payload names the changed ``dataType`` and the
physical-time ``intervals`` that changed, but carries no data. The handler fetches
the actual data via REST (rollUp/list) over those intervals.

See: https://developers.google.com/health/notifications
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GooglePhysicalTimeInterval(BaseModel):
    """A physical-time window ``{startTime, endTime}`` (RFC3339)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    start_time: datetime | None = Field(default=None, alias="startTime")
    end_time: datetime | None = Field(default=None, alias="endTime")


class GoogleWebhookInterval(BaseModel):
    """One changed interval; carries the physical-time window that changed."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    physical_time_interval: GooglePhysicalTimeInterval | None = Field(default=None, alias="physicalTimeInterval")


class GoogleWebhookData(BaseModel):
    """The ``data`` object of a Google Health API notification."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    health_user_id: str = Field(alias="healthUserId")
    operation: Literal["UPSERT", "DELETE"]
    data_type: str = Field(alias="dataType")
    intervals: list[GoogleWebhookInterval] = Field(default_factory=list)
    subscription_name: str | None = Field(default=None, alias="clientProvidedSubscriptionName")
    version: str | None = None


class GoogleWebhookNotification(BaseModel):
    """Top-level Google Health API webhook notification payload."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    data: GoogleWebhookData
