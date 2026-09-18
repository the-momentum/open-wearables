"""Abstract base class for provider webhook subscription management services."""

from collections.abc import Sequence
from typing import Any

from app.schemas.responses.incoming_webhooks import ProviderWebhookSubscription, WebhookOperationResult


class BaseWebhookService:
    """Base class for managing webhook subscriptions with a provider's API.

    Concrete services override the methods supported by their provider.
    Unsupported operations raise ``NotImplementedError``, which the router
    maps to HTTP 501.
    """

    # Dicts, not WebhookOperationResult: entries carry provider payload the model has no field for.
    async def register_subscriptions(self, callback_url: str) -> list[dict[str, Any]]:
        raise NotImplementedError("This provider does not support programmatic webhook registration")

    async def deregister_subscriptions(self) -> list[WebhookOperationResult]:
        raise NotImplementedError("This provider does not support deleting its webhook subscriptions")

    async def list_subscriptions(self) -> Sequence[ProviderWebhookSubscription]:
        raise NotImplementedError("This provider does not support listing webhook subscriptions")

    async def get_subscription(self, subscription_id: str) -> ProviderWebhookSubscription | None:
        raise NotImplementedError("This provider does not support fetching a webhook subscription by ID")

    async def renew_subscriptions(self) -> list[dict[str, Any]]:
        raise NotImplementedError("This provider does not support renewing webhook subscriptions")

    async def delete_subscription(self, subscription_id: str) -> WebhookOperationResult:
        raise NotImplementedError("This provider does not support deleting a webhook subscription")

    async def update_subscription(self, subscription_id: str, callback_url: str) -> WebhookOperationResult:
        raise NotImplementedError("This provider does not support updating a webhook subscription")
