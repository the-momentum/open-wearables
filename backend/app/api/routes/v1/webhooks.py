"""Unified webhook router – delegates incoming requests to provider strategies.

Route: ``/providers/{provider}/webhooks``

This router is the single entry point for all provider webhook events.
It resolves the provider strategy via ``ProviderFactory``, checks that the
provider has a ``BaseWebhookHandler`` wired up, and delegates to:

* ``strategy.webhooks.handle(request, body, db)``   – POST (data events)
* ``strategy.webhooks.handle_challenge(request)``   – GET (subscription verification)

The per-provider webhook handlers (to be implemented under
``app/services/providers/{provider}/webhook_handler.py``) are responsible for:

1. Verifying the request signature / token.
2. Parsing and validating the payload schema.
3. Dispatching to the appropriate service method.

Existing provider-specific routes (``/garmin/webhooks``, ``/oura/webhooks``,
``/strava/webhooks``) are intentionally kept in place while individual handlers
are migrated.  Once a provider's ``BaseWebhookHandler`` is implemented and wired
into its strategy, traffic can be cut over to this router.
"""

from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.database import DbSession
from app.schemas.responses.incoming_webhooks import (
    WebhookDeletedResponse,
    WebhookSubscriptionResponse,
    WebhookSubscriptionsResponse,
    WebhookUpdatedResponse,
)
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.factory import ProviderFactory
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.utils.auth import DeveloperDep

router = APIRouter()
logger = getLogger(__name__)

_factory = ProviderFactory()


def _get_strategy(provider: str) -> BaseProviderStrategy:
    """Resolve and return the provider strategy, raising 404 for unknown providers."""
    try:
        return _factory.get_provider(provider)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown provider: '{provider}'")


StrategyDep = Annotated[BaseProviderStrategy, Depends(_get_strategy)]


def _get_webhook_handler(provider: str) -> BaseWebhookHandler:
    """Resolve and return the webhook handler for *provider*.

    Raises ``404`` if the provider is unknown and ``501`` if the provider
    exists but has not yet implemented a ``BaseWebhookHandler``.
    """
    try:
        strategy = _factory.get_provider(provider)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown provider: '{provider}'")

    if strategy.webhooks is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"Provider '{provider}' has not implemented a webhook handler yet. "
                f"Capabilities: {strategy.capabilities}"
            ),
        )
    return strategy.webhooks


async def _read_body(request: Request) -> bytes:
    """Async dependency: read raw request body bytes.

    Keeps body reading off the sync route handler so that FastAPI can run the
    actual handler (which does synchronous DB work) in a threadpool, preventing
    event loop blocking.
    """
    return await request.body()


@router.post("")
def handle_provider_webhook(
    provider: str,
    request: Request,
    db: DbSession,
    body: Annotated[bytes, Depends(_read_body)],
) -> dict:
    """Receive an incoming webhook event from a provider.

    Body bytes are pre-read by the async ``_read_body`` dependency so that
    signature verification has access to the exact bytes signed by the provider.
    The route itself is a plain ``def`` so FastAPI runs it in a threadpool,
    keeping synchronous DB work off the event loop.

    Returns whatever dict the provider's ``dispatch()`` method returns.
    """
    handler = _get_webhook_handler(provider)
    return handler.handle(request, body, db)


@router.get("")
def verify_provider_webhook(provider: str, request: Request) -> dict:
    """Handle GET-based subscription verification challenges.

    Some providers (Strava ``hub.challenge``, Oura ``verification_token``)
    verify webhook subscriptions by sending a GET request that must be
    echoed back.  This endpoint delegates to the provider's
    ``handle_challenge()`` method.

    Providers that do not support GET challenges will receive a ``501``
    response from the default ``BaseWebhookHandler.handle_challenge()``
    implementation.
    """
    handler = _get_webhook_handler(provider)
    return handler.handle_challenge(request)


# ---------------------------------------------------------------------------
# Subscription management (internal / developer-only)
# ---------------------------------------------------------------------------


@router.get("/subscriptions")
async def list_webhook_subscriptions(
    strategy: StrategyDep,
    _dev: DeveloperDep,
) -> WebhookSubscriptionsResponse:
    """List active webhook subscriptions for a provider."""
    if strategy.webhook_service is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Provider does not support webhook subscription management",
        )
    try:
        result = await strategy.webhook_service.list_subscriptions()
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    return WebhookSubscriptionsResponse(subscriptions=result)


@router.post("/subscriptions")
async def register_webhook_subscriptions(
    strategy: StrategyDep,
    _dev: DeveloperDep,
    callback_url: str,
) -> dict:
    """Register or update webhook subscriptions for a provider."""
    if strategy.webhook_service is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Provider does not support webhook subscription management",
        )
    try:
        result = await strategy.webhook_service.register_subscriptions(callback_url)
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    return {"subscriptions": result}


@router.post("/subscriptions/renew")
async def renew_webhook_subscriptions(
    strategy: StrategyDep,
    _dev: DeveloperDep,
) -> dict:
    """Renew all active webhook subscriptions for a provider."""
    if strategy.webhook_service is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Provider does not support webhook subscription management",
        )
    try:
        result = await strategy.webhook_service.renew_subscriptions()
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    return {"renewed": result}


@router.get("/subscriptions/{subscription_id}")
async def get_webhook_subscription(
    strategy: StrategyDep,
    subscription_id: str,
    _dev: DeveloperDep,
) -> WebhookSubscriptionResponse:
    """Get a single webhook subscription by ID."""
    if strategy.webhook_service is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Provider does not support webhook subscription management",
        )
    try:
        result = await strategy.webhook_service.get_subscription(subscription_id)
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    return WebhookSubscriptionResponse(subscription=result)


@router.delete("/subscriptions/{subscription_id}")
async def delete_webhook_subscription(
    strategy: StrategyDep,
    subscription_id: str,
    _dev: DeveloperDep,
) -> WebhookDeletedResponse:
    """Delete a webhook subscription by ID."""
    if strategy.webhook_service is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Provider does not support webhook subscription management",
        )
    try:
        result = await strategy.webhook_service.delete_subscription(subscription_id)
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    return WebhookDeletedResponse(deleted=result)


@router.put("/subscriptions/{subscription_id}")
async def update_webhook_subscription(
    strategy: StrategyDep,
    subscription_id: str,
    _dev: DeveloperDep,
    callback_url: str,
) -> WebhookUpdatedResponse:
    """Update the callback URL of a webhook subscription."""
    if strategy.webhook_service is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Provider does not support webhook subscription management",
        )
    try:
        result = await strategy.webhook_service.update_subscription(subscription_id, callback_url)
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    return WebhookUpdatedResponse(updated=result)
