"""Whoop webhook notification schema."""

from enum import StrEnum

from pydantic import BaseModel


class WhoopWebhookNotificationType(StrEnum):
    WORKOUT_UPDATED = "workout.updated"
    WORKOUT_DELETED = "workout.deleted"
    SLEEP_UPDATED = "sleep.updated"
    SLEEP_DELETED = "sleep.deleted"
    RECOVERY_UPDATED = "recovery.updated"
    RECOVERY_DELETED = "recovery.deleted"

    @property
    def is_delete_type(self) -> bool:
        return self.value.endswith(".deleted")

    @property
    def is_update_type(self) -> bool:
        return self.value.endswith(".updated")


class WhoopWebhookNotification(BaseModel):
    """Webhook notification payload from Whoop.

    Whoop sends a lightweight notify-only payload; the actual data must be
    fetched from the REST API using the resource ``id``.

    See: https://developer.whoop.com/docs/developing/webhooks/
    """

    user_id: int  # Whoop user ID
    id: str | int  # Resource ID: UUID string (v2) or int (v1)
    type: WhoopWebhookNotificationType  # e.g. workout.updated, sleep.updated, recovery.updated
    trace_id: str | None = None
