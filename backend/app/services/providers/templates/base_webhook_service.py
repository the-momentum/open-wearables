"""Contract for provider webhook subscription services."""

from typing import Any
from uuid import UUID

from app.database import DbSession
from app.schemas.auth import LiveSyncMode


class BaseWebhookService:
    """Base class for managing webhook subscriptions with a provider's API.

    Concrete services override the methods supported by their provider.
    Unsupported operations raise ``NotImplementedError``, which the router
    maps to HTTP 501.
    """

    async def register_subscriptions(self, callback_url: str) -> Any:
        raise NotImplementedError("This provider does not support programmatic webhook registration")

    async def list_subscriptions(self) -> Any:
        raise NotImplementedError("This provider does not support listing webhook subscriptions")

    async def get_subscription(self, subscription_id: str) -> Any:
        raise NotImplementedError("This provider does not support fetching a webhook subscription by ID")

    async def renew_subscriptions(self) -> Any:
        raise NotImplementedError("This provider does not support renewing webhook subscriptions")

    async def delete_subscription(self, subscription_id: str) -> Any:
        raise NotImplementedError("This provider does not support deleting a webhook subscription")

    async def update_subscription(self, subscription_id: str, callback_url: str) -> Any:
        raise NotImplementedError("This provider does not support updating a webhook subscription")

    def sync_user(self, db: DbSession, user_id: UUID, mode: LiveSyncMode) -> list[dict[str, Any]]:
        """Reconcile subscriptions owned by one connected provider user."""
        raise NotImplementedError("This provider does not support per-user webhook subscription management")
