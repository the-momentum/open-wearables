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

from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import DbSession
from app.services.providers.factory import ProviderFactory
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler

router = APIRouter()
logger = getLogger(__name__)

_factory = ProviderFactory()


def _get_webhook_handler(provider: str) -> BaseWebhookHandler:
    """Resolve and return the webhook handler for *provider*.

    Raises ``404`` if the provider is unknown and ``501`` if the provider
    exists but has not yet implemented a ``BaseWebhookHandler``.
    """
    try:
        strategy = _factory.get_provider(provider)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown provider: '{provider}'")

    if strategy.webhooks is None:
        raise HTTPException(
            status_code=501,
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


@router.post("/{provider}/webhooks")
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


@router.get("/{provider}/webhooks")
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
