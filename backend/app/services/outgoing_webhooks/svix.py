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

from jose import jwt
from svix.api import (
    ApplicationIn,
    EndpointIn,
    EndpointOut,
    EndpointPatch,
    EventExampleIn,
    EventTypeIn,
    EventTypeUpdate,
    ListResponseEndpointOut,
    ListResponseMessageAttemptOut,
    MessageIn,
    MessageOut,
    Svix,
    SvixOptions,
)

from app.config import settings
from app.schemas.webhooks.event_types import EVENT_TYPE_DESCRIPTIONS, WebhookEventType

logger = logging.getLogger(__name__)

# Fixed org UID used for this self-hosted instance.
_SVIX_ORG_ID = "org_openwearables"


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
            _client.event_type.create(
                EventTypeIn(name=evt.value, description=description),
            )
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
            ),
        )
    except Exception:
        logger.exception("Failed to send webhook event=%s to app=%s", event_type, app_id)
        return None


def create_endpoint(app_id: str, endpoint_in: EndpointIn) -> EndpointOut:
    assert _client is not None
    return _client.endpoint.create(app_id, endpoint_in)


def list_endpoints(app_id: str) -> ListResponseEndpointOut:
    assert _client is not None
    return _client.endpoint.list(app_id)


def get_endpoint(app_id: str, endpoint_id: str) -> EndpointOut:
    assert _client is not None
    return _client.endpoint.get(app_id, endpoint_id)


def patch_endpoint(app_id: str, endpoint_id: str, endpoint_patch: EndpointPatch) -> EndpointOut:
    assert _client is not None
    return _client.endpoint.patch(app_id, endpoint_id, endpoint_patch)


def delete_endpoint(app_id: str, endpoint_id: str) -> None:
    assert _client is not None
    _client.endpoint.delete(app_id, endpoint_id)


def get_endpoint_secret(app_id: str, endpoint_id: str) -> str:
    """Return the signing secret for an endpoint so developers can verify payloads."""
    assert _client is not None
    result = _client.endpoint.get_secret(app_id, endpoint_id)
    return result.key


def list_messages(app_id: str) -> Any:
    assert _client is not None
    return _client.message.list(app_id)


def list_message_attempts(app_id: str, endpoint_id: str) -> ListResponseMessageAttemptOut:
    assert _client is not None
    return _client.message_attempt.list_by_endpoint(app_id, endpoint_id)


def send_test_message(app_id: str, endpoint_id: str, event_type: str) -> MessageOut | None:
    """Send a sample event to a specific endpoint for testing.

    Uses Svix's ``endpoint.send_example`` so only the targeted endpoint
    receives the message, regardless of other endpoints in the application.
    """
    if not is_enabled():
        return None
    assert _client is not None
    try:
        return _client.endpoint.send_example(
            app_id,
            endpoint_id,
            EventExampleIn(event_type=event_type),
        )
    except Exception:
        logger.exception("Failed to send test webhook event=%s to endpoint=%s", event_type, endpoint_id)
        return None
