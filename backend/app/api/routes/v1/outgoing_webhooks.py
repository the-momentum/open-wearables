"""Outgoing webhooks management API.

Endpoints for developers to manage their webhook endpoints, view event types,
view delivery history, get endpoint secrets, and send test events.

All endpoints require developer authentication (JWT or API key).
A Svix Application per developer is created lazily on first use.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from svix.api import EndpointOut

from app.schemas.webhooks.endpoints import (
    EndpointCreateRequest,
    EndpointResponse,
    EndpointSecretResponse,
    EndpointUpdateRequest,
    EventTypeResponse,
    TestEventRequest,
)
from app.schemas.webhooks.event_types import EVENT_TYPE_DESCRIPTIONS, WebhookEventType
from app.services import DeveloperDep
from app.services.outgoing_webhooks import svix as svix_service

router = APIRouter()


def _ep_to_response(ep: EndpointOut) -> EndpointResponse:
    return EndpointResponse(
        id=ep.id,
        url=ep.url,
        description=ep.description,
        filter_types=ep.filter_types,
        user_id=svix_service.user_id_from_endpoint(ep),
    )


def _svix_app_id(developer: DeveloperDep) -> str:
    """Authenticate the developer, assert Svix is configured, and return the app UID."""
    if not svix_service.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Outgoing webhooks are not configured (set SVIX_JWT_SECRET or SVIX_AUTH_TOKEN).",
        )
    return svix_service.ensure_application(str(developer.id), developer.email)


SvixAppId = Annotated[str, Depends(_svix_app_id)]


@router.post("/endpoints", status_code=status.HTTP_201_CREATED)
def create_endpoint(body: EndpointCreateRequest, app_id: SvixAppId) -> EndpointResponse:
    ep = svix_service.create_endpoint(
        app_id,
        url=body.url,
        description=body.description,
        filter_types=body.filter_types,
        user_id=body.user_id,
    )
    return _ep_to_response(ep)


@router.get("/endpoints")
def list_endpoints(app_id: SvixAppId) -> list[EndpointResponse]:
    result = svix_service.list_endpoints(app_id)
    return [_ep_to_response(ep) for ep in result.data]


@router.get("/endpoints/{endpoint_id}")
def get_endpoint(endpoint_id: str, app_id: SvixAppId) -> EndpointResponse:
    ep = svix_service.get_endpoint(app_id, endpoint_id)
    return _ep_to_response(ep)


@router.patch("/endpoints/{endpoint_id}")
def update_endpoint(endpoint_id: str, body: EndpointUpdateRequest, app_id: SvixAppId) -> EndpointResponse:
    clear_user = "user_id" in body.model_fields_set and body.user_id is None
    ep = svix_service.patch_endpoint(
        app_id,
        endpoint_id,
        url=body.url,
        description=body.description,
        filter_types=body.filter_types,
        user_id=body.user_id,
        clear_user_id=clear_user,
    )
    return _ep_to_response(ep)


@router.delete("/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(endpoint_id: str, app_id: SvixAppId) -> None:
    svix_service.delete_endpoint(app_id, endpoint_id)


@router.get("/endpoints/{endpoint_id}/secret")
def get_endpoint_secret(endpoint_id: str, app_id: SvixAppId) -> EndpointSecretResponse:
    key = svix_service.get_endpoint_secret(app_id, endpoint_id)
    return EndpointSecretResponse(key=key)


@router.get("/event-types")
def list_event_types() -> list[EventTypeResponse]:
    return [
        EventTypeResponse(name=evt.value, description=EVENT_TYPE_DESCRIPTIONS.get(evt, "")) for evt in WebhookEventType
    ]


@router.get("/messages")
def list_messages(app_id: SvixAppId) -> Any:
    return svix_service.list_messages(app_id)


@router.get("/endpoints/{endpoint_id}/attempts")
def list_endpoint_attempts(endpoint_id: str, app_id: SvixAppId) -> Any:
    return svix_service.list_message_attempts(app_id, endpoint_id)


@router.post("/endpoints/{endpoint_id}/test")
def send_test_event(endpoint_id: str, app_id: SvixAppId, body: TestEventRequest | None = None) -> Any:
    event_type = body.event_type if body else WebhookEventType.WORKOUT_CREATED
    result = svix_service.send_test_message(app_id, endpoint_id, event_type)
    if result is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send test event.")
    return {"message": "Test event sent successfully.", "message_id": result.id}
