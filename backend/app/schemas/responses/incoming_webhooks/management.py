"""Response schemas for provider webhook subscription management operations.

Covers list, get, delete, and update responses for Polar, Oura, and Strava.
These are admin-level operations (register/inspect/remove subscriptions), not
inbound event processing.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, model_serializer, model_validator

from app.schemas.providers.polar.webhook import PolarWebhookEventType


class WebhookSubscriptionStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    PATCHED = "patched"
    DELETED = "deleted"
    SKIPPED = "skipped"
    ERROR = "error"


class WebhookOperationResult(BaseModel):
    """Generic result for a single webhook subscription operation (delete / update)."""

    subscription_id: str
    status: WebhookSubscriptionStatus
    error: str | None = None

    @model_validator(mode="after")
    def _validate_error_contract(self) -> "WebhookOperationResult":
        if self.status == WebhookSubscriptionStatus.ERROR and self.error is None:
            raise ValueError("error must be set when status is ERROR")
        if self.error is not None and self.status != WebhookSubscriptionStatus.ERROR:
            raise ValueError("error must only be set when status is ERROR")
        return self

    @model_serializer
    def _serialize(self) -> dict:
        out: dict = {"subscription_id": self.subscription_id, "status": self.status}
        if self.status == WebhookSubscriptionStatus.ERROR:
            out["error"] = self.error
        return out


class ProviderWebhookSubscription(BaseModel):
    """Base class for all provider webhook subscription responses."""


class PolarWebhookSubscription(ProviderWebhookSubscription):
    """A single Polar app-level webhook as returned by GET /v3/webhooks."""

    id: str
    events: list[PolarWebhookEventType]
    url: str


class OuraWebhookSubscription(ProviderWebhookSubscription):
    """A single Oura webhook subscription as returned by GET /v2/webhook/subscription."""

    id: str
    callback_url: str
    event_type: str
    data_type: str
    expiration_time: str | None = None


class StravaWebhookSubscription(ProviderWebhookSubscription):
    """A single Strava push subscription as returned by GET /api/v3/push_subscriptions."""

    id: int
    application_id: int
    callback_url: str
    created_at: str
    updated_at: str
    resource_state: int | None = None


class GoogleSubscriberConfig(BaseModel):
    """One dataType group of a Google Health API subscriber."""

    model_config = ConfigDict(populate_by_name=True)

    data_types: list[str] = Field(default_factory=list, alias="dataTypes")
    subscription_create_policy: str | None = Field(default=None, alias="subscriptionCreatePolicy")


class GoogleWebhookSubscription(ProviderWebhookSubscription):
    """A single Google Health API subscriber as returned by GET /v4/projects/{project}/subscribers."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    endpoint_uri: str = Field(alias="endpointUri")
    subscriber_configs: list[GoogleSubscriberConfig] = Field(default_factory=list, alias="subscriberConfigs")


class WebhookSubscriptionsResponse(BaseModel):
    """Response wrapper for listing webhook subscriptions (any provider)."""

    subscriptions: list[SerializeAsAny[ProviderWebhookSubscription]]


class WebhookSubscriptionResponse(BaseModel):
    """Response wrapper for fetching a single webhook subscription."""

    subscription: SerializeAsAny[ProviderWebhookSubscription] | None = None


class WebhookDeletedResponse(BaseModel):
    """Response wrapper for a delete operation result."""

    deleted: WebhookOperationResult


class WebhookUpdatedResponse(BaseModel):
    """Response wrapper for an update operation result."""

    updated: WebhookOperationResult
