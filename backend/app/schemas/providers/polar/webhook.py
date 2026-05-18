from enum import StrEnum

from pydantic import BaseModel


class PolarWebhookEventType(StrEnum):
    EXERCISE = "EXERCISE"
    SLEEP = "SLEEP"
    CONTINUOUS_HEART_RATE = "CONTINUOUS_HEART_RATE"
    ACTIVITY_SUMMARY = "ACTIVITY_SUMMARY"
    SLEEP_WISE_ALERTNESS = "SLEEP_WISE_ALERTNESS"
    SLEEP_WISE_CIRCADIAN_BEDTIME = "SLEEP_WISE_CIRCADIAN_BEDTIME"
    PHYSICAL_INFORMATION = "PHYSICAL_INFORMATION"
    PING = "PING"


class PolarWebhookEvent(BaseModel):
    event: PolarWebhookEventType
    user_id: int | None = None
    entity_id: str | None = None
    timestamp: str | None = None
    url: str | None = None
