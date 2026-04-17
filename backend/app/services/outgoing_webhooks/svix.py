"""Thin wrapper around the Svix Python SDK.

Responsibilities:
- Initialise Svix client from config
- Lazy Application creation per developer
- Register / sync event types on startup
- Send (emit) webhook messages
- CRUD proxy for endpoint management
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from jose import jwt
from svix.api import (
    ApplicationIn,
    EndpointIn,
    EndpointOut,
    EndpointPatch,
    EventTypeIn,
    EventTypeUpdate,
    ListResponseEndpointOut,
    ListResponseMessageAttemptOut,
    ListResponseMessageOut,
    MessageIn,
    MessageOut,
    Svix,
    SvixOptions,
)

from app.config import settings
from app.constants.webhooks.test_payloads import get_test_payload
from app.schemas.webhooks.event_types import EVENT_TYPE_DESCRIPTIONS, WebhookEventType

logger = logging.getLogger(__name__)

# Fixed org UID used for this self-hosted instance.
_SVIX_ORG_ID = "org_openwearables"

# Svix channel prefix used to scope messages and endpoint subscriptions per user.
# Each emitted message is tagged with "user.{user_id}".
# An endpoint without a channel filter receives ALL messages (all users).
# An endpoint with channels=["user.X"] receives only messages for user X.
# Svix allows up to 5 channels per message; we always send exactly one.
_USER_CHANNEL_PREFIX = "user."


def _user_channels(user_id: UUID | None) -> list[str] | None:
    if user_id is None:
        return None
    return [f"{_USER_CHANNEL_PREFIX}{user_id}"]


def user_id_from_endpoint(ep: EndpointOut) -> UUID | None:
    """Extract the user_id filter from an endpoint's Svix channels, if any."""
    if not ep.channels:
        return None
    for ch in ep.channels:
        if ch.startswith(_USER_CHANNEL_PREFIX):
            try:
                return UUID(ch[len(_USER_CHANNEL_PREFIX) :])
            except ValueError:
                pass
    return None


def _resolve_auth_token() -> str | None:
    """Return the Svix auth token, generating it from the JWT secret if needed.

    Priority:
    1. Explicit ``SVIX_AUTH_TOKEN`` env var — use as-is.
    2. ``SVIX_JWT_SECRET`` present — derive a token automatically (no manual step needed).
    3. Neither set — webhooks disabled.
    """
    if settings.svix_auth_token is not None:
        return settings.svix_auth_token.get_secret_value()
    if settings.svix_jwt_secret is not None:
        token = jwt.encode(
            {"sub": _SVIX_ORG_ID},
            settings.svix_jwt_secret.get_secret_value(),
            algorithm="HS256",
        )
        logger.info("SVIX_AUTH_TOKEN not set — derived from SVIX_JWT_SECRET automatically.")
        return token
    logger.warning("Neither SVIX_AUTH_TOKEN nor SVIX_JWT_SECRET is set — outgoing webhooks are disabled.")
    return None


def _build_client() -> Svix | None:
    """Create the Svix client. Returns None when no credentials are configured."""
    token = _resolve_auth_token()
    if token is None:
        return None
    return Svix(token, SvixOptions(server_url=settings.svix_server_url))


_client: Svix | None = _build_client()


def is_enabled() -> bool:
    return _client is not None


def register_event_types() -> None:
    """Create / update every WebhookEventType in Svix (idempotent)."""
    if not is_enabled():
        return
    assert _client is not None
    for evt in WebhookEventType:
        description = EVENT_TYPE_DESCRIPTIONS.get(evt, "")
        try:
            _client.event_type.create(EventTypeIn(name=evt.value, description=description))
            logger.info("Registered event type: %s", evt.value)
        except Exception:
            try:
                _client.event_type.update(evt.value, EventTypeUpdate(description=description))
            except Exception:
                logger.exception("Failed to register/update event type %s", evt.value)


def ensure_application(developer_id: str, developer_email: str) -> str:
    """Return the Svix application UID for a developer, creating it lazily.

    The Svix uid is set to the developer's UUID so no mapping is needed on our side.
    """
    if not is_enabled():
        return developer_id
    assert _client is not None
    uid = str(developer_id)
    try:
        _client.application.get_or_create(
            ApplicationIn(name=developer_email, uid=uid),
        )
    except Exception:
        logger.exception("Failed to ensure Svix application for developer %s", uid)
    return uid


def send(
    event_type: str,
    developer_id: str,
    payload: dict[str, Any],
    *,
    channels: list[str] | None = None,
    idempotency_key: str | None = None,
) -> MessageOut | None:
    """Emit a webhook message via Svix. developer_id doubles as the Svix application UID."""
    if not is_enabled():
        return None
    assert _client is not None
    app_id = str(developer_id)
    try:
        return _client.message.create(
            app_id,
            MessageIn(
                event_type=event_type,
                payload=payload,
                event_id=idempotency_key,
                channels=channels or None,
            ),
        )
    except Exception:
        logger.exception("Failed to send webhook event=%s to app=%s", event_type, app_id)
        return None


def create_endpoint(
    app_id: str,
    url: str,
    description: str | None = None,
    filter_types: list[str] | None = None,
    *,
    user_id: UUID | None = None,
) -> EndpointOut:
    assert _client is not None
    return _client.endpoint.create(
        app_id,
        EndpointIn(
            url=url,
            description=description or "",
            filter_types=filter_types or None,
            channels=_user_channels(user_id),
        ),
    )


def list_endpoints(app_id: str) -> ListResponseEndpointOut:
    assert _client is not None
    return _client.endpoint.list(app_id)


def get_endpoint(app_id: str, endpoint_id: str) -> EndpointOut:
    assert _client is not None
    return _client.endpoint.get(app_id, endpoint_id)


def patch_endpoint(
    app_id: str,
    endpoint_id: str,
    *,
    url: str | None = None,
    description: str | None = None,
    filter_types: list[str] | None = None,
    user_id: UUID | None = None,
    clear_user_id: bool = False,
) -> EndpointOut:
    """Patch an endpoint.

    Pass ``user_id`` to scope the endpoint to a specific user.
    Pass ``clear_user_id=True`` (with ``user_id=None``) to remove an existing
    user scope and receive events for all users again.
    """
    assert _client is not None
    channels: list[str] | None
    if user_id is not None:
        channels = _user_channels(user_id)
    elif clear_user_id:
        # Empty list tells Svix to remove the channel filter from this endpoint.
        channels = []
    else:
        # None = don't touch the channels field (PATCH semantics).
        channels = None
    return _client.endpoint.patch(
        app_id,
        endpoint_id,
        EndpointPatch(
            url=url,
            description=description,
            filter_types=filter_types,
            channels=channels,
        ),
    )


def delete_endpoint(app_id: str, endpoint_id: str) -> None:
    assert _client is not None
    _client.endpoint.delete(app_id, endpoint_id)


def get_endpoint_secret(app_id: str, endpoint_id: str) -> str:
    """Return the signing secret for an endpoint so developers can verify payloads."""
    assert _client is not None
    result = _client.endpoint.get_secret(app_id, endpoint_id)
    return result.key


def list_messages(app_id: str) -> ListResponseMessageOut:
    assert _client is not None
    return _client.message.list(app_id)


def list_message_attempts(app_id: str, endpoint_id: str) -> ListResponseMessageAttemptOut:
    assert _client is not None
    return _client.message_attempt.list_by_endpoint(app_id, endpoint_id)


def send_test_message(app_id: str, endpoint_id: str, event_type: str) -> MessageOut | None:
    """Send a hardcoded sample event to a specific endpoint for testing.

    Uses ``message.create`` with an example payload instead of
    ``endpoint.send_example`` which requires Svix event-type schemas to be defined.
    The event_type is adjusted to match the endpoint's filter_types if set.
    """
    if not is_enabled():
        return None
    assert _client is not None
    try:
        ep = _client.endpoint.get(app_id, endpoint_id)
        if ep.filter_types and event_type not in ep.filter_types:
            event_type = ep.filter_types[0]
        return _client.message.create(
            app_id,
            MessageIn(
                event_type=event_type,
                payload=get_test_payload(event_type),
                event_id=f"test.{endpoint_id}.{event_type}",
            ),
        )
    except Exception:
        logger.exception("Failed to send test webhook event=%s to endpoint=%s", event_type, endpoint_id)
        return None
