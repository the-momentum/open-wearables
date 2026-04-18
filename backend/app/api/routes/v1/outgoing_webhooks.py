"""Outgoing webhooks management API.

Endpoints for developers to manage their webhook endpoints, view event types,
view delivery history, get endpoint secrets, and send test events.

All endpoints require developer authentication (JWT or API key).
A Svix Application per developer is created lazily on first use.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from svix.api import EndpointOut, MessageAttemptListByEndpointOptions, MessageListOptions, MessageStatus

from app.schemas.webhooks.endpoints import (
    EndpointCreateRequest,
    EndpointResponse,
    EndpointSecretResponse,
    EndpointUpdateRequest,
    EventTypeResponse,
    PaginatedResponse,
    TestEventRequest,
    WebhookMessageAttemptResponse,
    WebhookMessageResponse,
)
from app.schemas.webhooks.event_types import EVENT_TYPE_DESCRIPTIONS, EVENT_TYPE_GROUPS, WebhookEventType
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
        EventTypeResponse(
            name=evt.value,
            description=EVENT_TYPE_DESCRIPTIONS.get(evt, ""),
            child_events=EVENT_TYPE_GROUPS.get(evt.value) or None,
        )
        for evt in WebhookEventType
    ]


@router.get("/messages", response_model=PaginatedResponse[WebhookMessageResponse])
def list_messages(
    app_id: SvixAppId,
    limit: Annotated[int, Query(ge=1, le=250, description="Items per page.")] = 50,
    iterator: Annotated[str | None, Query(description="Cursor from the previous page's `iterator` field.")] = None,
    before: Annotated[datetime | None, Query(description="Only messages created before this timestamp.")] = None,
    after: Annotated[datetime | None, Query(description="Only messages created after this timestamp.")] = None,
) -> Any:
    result = svix_service.list_messages(
        app_id,
        MessageListOptions(limit=limit, iterator=iterator, before=before, after=after),
    )
    return PaginatedResponse[WebhookMessageResponse](
        data=[
            WebhookMessageResponse(
                id=m.id,
                eventType=m.event_type,
                eventId=m.event_id,
                timestamp=m.timestamp.isoformat(),
                channels=m.channels,
                tags=m.tags,
            )
            for m in result.data
        ],
        done=result.done,
        iterator=result.iterator,
        prevIterator=result.prev_iterator,
    )


@router.get(
    "/endpoints/{endpoint_id}/attempts",
    response_model=PaginatedResponse[WebhookMessageAttemptResponse],
)
def list_endpoint_attempts(
    endpoint_id: str,
    app_id: SvixAppId,
    limit: Annotated[int, Query(ge=1, le=250, description="Items per page.")] = 50,
    iterator: Annotated[str | None, Query(description="Cursor from the previous page's `iterator` field.")] = None,
    before: Annotated[datetime | None, Query(description="Only attempts created before this timestamp.")] = None,
    after: Annotated[datetime | None, Query(description="Only attempts created after this timestamp.")] = None,
    status: Annotated[
        int | None, Query(description="Filter by status: 0=success, 1=pending, 2=failed, 3=sending.")
    ] = None,
    event_types: Annotated[list[str] | None, Query(description="Filter by event type(s).")] = None,
) -> Any:
    options = MessageAttemptListByEndpointOptions(
        limit=limit,
        iterator=iterator,
        before=before,
        after=after,
        status=MessageStatus(status) if status is not None else None,
        event_types=event_types,
    )
    result = svix_service.list_message_attempts(app_id, endpoint_id, options)

    # Enrich each attempt with its message (eventType + payload).
    # Page is bounded by `limit`; unique msg_ids ≤ limit (retries share same msg_id).
    unique_msg_ids = {a.msg_id for a in result.data}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(svix_service.get_message, app_id, mid): mid for mid in unique_msg_ids}
        msg_map: dict[str, Any] = {}
        for future in as_completed(futures):
            mid = futures[future]
            msg = future.result()
            if msg is not None:
                msg_map[mid] = msg

    return PaginatedResponse[WebhookMessageAttemptResponse](
        data=[
            WebhookMessageAttemptResponse(
                id=a.id,
                endpointId=a.endpoint_id,
                msgId=a.msg_id,
                url=a.url,
                response=a.response,
                responseStatusCode=a.response_status_code,
                responseDurationMs=a.response_duration_ms,
                status=int(a.status),
                statusText=str(a.status_text) if a.status_text else None,
                triggerType=int(a.trigger_type),
                timestamp=a.timestamp.isoformat(),
                msg=WebhookMessageResponse(
                    id=msg_map[a.msg_id].id,
                    eventType=msg_map[a.msg_id].event_type,
                    eventId=msg_map[a.msg_id].event_id,
                    timestamp=msg_map[a.msg_id].timestamp.isoformat(),
                    channels=msg_map[a.msg_id].channels,
                    tags=msg_map[a.msg_id].tags,
                    payload=msg_map[a.msg_id].payload,
                )
                if a.msg_id in msg_map
                else None,
            )
            for a in result.data
        ],
        done=result.done,
        iterator=result.iterator,
        prevIterator=result.prev_iterator,
    )


@router.post("/endpoints/{endpoint_id}/test")
def send_test_event(endpoint_id: str, app_id: SvixAppId, body: TestEventRequest | None = None) -> Any:
    event_type = body.event_type if body else WebhookEventType.WORKOUT_CREATED
    result = svix_service.send_test_message(app_id, endpoint_id, event_type)
    if result is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send test event.")
    return {"message": "Test event sent successfully.", "message_id": result.id}
