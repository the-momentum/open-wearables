"""Pydantic request/response schemas for outgoing webhook management endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from app.schemas.webhooks.event_types import WebhookEventType


def _validate_url(value: str) -> str:
    """Ensure the value is a parseable absolute HTTP(S) URL."""
    # Delegate to pydantic's own AnyHttpUrl parser for a clean error message.
    AnyHttpUrl(value)
    return value


class EndpointCreateRequest(BaseModel):
    url: str = Field(description="HTTPS URL where webhook payloads will be sent.")
    description: str | None = Field(None, description="Human-readable label for this endpoint.")
    filter_types: list[str] | None = Field(
        None,
        description="Only deliver events of these types. Empty / None = all types.",
    )
    user_id: UUID | None = Field(
        None,
        description="Subscribe only to events for this user. Empty / None = all users.",
    )

    @field_validator("url")
    @classmethod
    def url_must_be_absolute(cls, v: str) -> str:
        return _validate_url(v)


class EndpointUpdateRequest(BaseModel):
    url: str | None = None
    description: str | None = None
    filter_types: list[str] | None = None
    user_id: UUID | None = Field(
        None,
        description="Subscribe only to events for this user. Pass null to remove the filter.",
    )

    @field_validator("url")
    @classmethod
    def url_must_be_absolute(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_url(v)


class EndpointResponse(BaseModel):
    id: str
    url: str
    description: str | None = None
    filter_types: list[str] | None = None
    user_id: UUID | None = None

    model_config = {"from_attributes": True}


class EndpointSecretResponse(BaseModel):
    key: str


class EventTypeResponse(BaseModel):
    name: str
    description: str
    child_events: list[str] | None = None
    """Granular (series.*) events that belong to this group, if any."""


class TestEventRequest(BaseModel):
    event_type: str = Field(
        default=WebhookEventType.WORKOUT_CREATED,
        description="Event type to include in the test payload.",
    )


# ---------------------------------------------------------------------------
# Paginated list responses (for messages and delivery attempts)
# ---------------------------------------------------------------------------


class WebhookMessageResponse(BaseModel):
    """A single webhook message (outgoing event emitted to all subscribed endpoints)."""

    id: str
    eventType: str  # noqa: N815
    eventId: str | None = None  # noqa: N815
    timestamp: str
    channels: list[str] | None = None
    tags: list[str] | None = None
    payload: dict | None = None


class WebhookMessageAttemptResponse(BaseModel):
    """A single delivery attempt for a webhook message to one endpoint."""

    id: str
    endpointId: str  # noqa: N815
    msgId: str  # noqa: N815
    url: str
    response: str
    responseStatusCode: int  # noqa: N815
    responseDurationMs: int  # noqa: N815
    status: int
    statusText: str | None = None  # noqa: N815
    triggerType: int  # noqa: N815
    timestamp: str
    msg: WebhookMessageResponse | None = None


class PaginatedResponse[T](BaseModel):
    """Cursor-paginated list wrapper (Svix iterator pattern)."""

    data: list[T]
    done: bool = Field(description="True when this is the last page.")
    iterator: str | None = Field(
        None,
        description="Pass as `iterator` in the next request to fetch the following page.",
    )
    prevIterator: str | None = None  # noqa: N815
