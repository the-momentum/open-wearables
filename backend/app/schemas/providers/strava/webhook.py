from typing import Any

from pydantic import BaseModel


class StravaWebhookEvent(BaseModel):
    """Strava webhook push event payload.

    Strava sends this for activity create/update/delete and athlete deauthorize.

    See: https://developers.strava.com/docs/webhooks/
    """

    object_type: str  # "activity" or "athlete"
    object_id: int
    aspect_type: str  # "create", "update", or "delete"
    updates: dict[str, Any] = {}
    owner_id: int  # Strava athlete ID
    subscription_id: int
    event_time: int  # Unix timestamp
