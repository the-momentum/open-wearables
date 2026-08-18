"""Google Health API webhook subscription management.

Subscribers are registered at the GCP *project* level (not per user):
``POST /v4/projects/{project}/subscribers``. One subscriber fans out notifications
for the configured dataTypes to our callback endpoint, echoing a bearer secret in
the Authorization header (verified by GoogleWebhookHandler).

Inbound notification processing is handled by GoogleWebhookHandler.

The call authenticates with *project* credentials (a service account), not a user
OAuth token: the service-account key at ``google_service_account_file`` (falling back
to Application Default Credentials). Supports create / list / get / update / delete;
Google has no renew operation.
"""

from logging import getLogger
from typing import Any

import google.auth
import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from pydantic import ValidationError

from app.config import settings
from app.constants.google_health_endpoints import SUBSCRIBERS_ENDPOINT
from app.schemas.responses.incoming_webhooks import (
    GoogleWebhookSubscription,
    ProviderWebhookSubscription,
    WebhookOperationResult,
    WebhookSubscriptionStatus,
)
from app.services.providers.google.health_api.metrics import METRICS
from app.services.providers.templates.base_webhook_service import BaseWebhookService
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

GOOGLE_HEALTH_API_BASE = "https://health.googleapis.com"

# Standard scope for a service account calling a project-scoped GCP API.
_SUBSCRIBER_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

# Stable id for our single project subscriber, so re-registration targets the same one.
SUBSCRIBER_ID = "open-wearables"

# not every data type is supported  that we pull from - might
# not be the best solution, but this is all supported
GOOGLE_WEBHOOK_SUPPORTED_DATA_TYPES = frozenset(
    {
        "active-zone-minutes",
        "activity-level",
        "altitude",
        "blood-glucose",
        "body-fat",
        "daily-heart-rate-variability",
        "daily-oxygen-saturation",
        "daily-respiratory-rate",
        "daily-resting-heart-rate",
        "distance",
        "exercise",
        "floors",
        "heart-rate",
        "heart-rate-variability",
        "height",
        "hydration-log",
        "nutrition-log",
        "run-vo2-max",
        "sedentary-period",
        "sleep",
        "steps",
        "weight",
    }
)

# Subscribe to the handled types (24/7 metrics + sessions) that Google supports for webhooks.
# AUTOMATIC lets Google create per-user subscriptions itself as users connect.
GOOGLE_WEBHOOK_DATA_TYPES = [
    data_type
    for data_type in ([m.data_type for m in METRICS] + ["sleep", "exercise"])
    if data_type in GOOGLE_WEBHOOK_SUPPORTED_DATA_TYPES
]


def _subscribers_url() -> str:
    if not settings.google_project_id:
        raise ValueError("GOOGLE_PROJECT_ID is not configured; cannot manage Health API subscribers")
    return f"{GOOGLE_HEALTH_API_BASE}{SUBSCRIBERS_ENDPOINT.format(project=settings.google_project_id)}"


def _error_result(subscription_id: str, action: str, error: httpx.HTTPError) -> WebhookOperationResult:
    response_body = error.response.text if isinstance(error, httpx.HTTPStatusError) else None
    log_structured(
        logger,
        "error",
        f"Failed to {action} Google Health API subscriber",
        provider="google",
        action=f"google_webhook_subscription_{action}_error",
        subscription_id=subscription_id,
        error=str(error),
        status_code=error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None,
        response_body=response_body,
    )
    return WebhookOperationResult(
        subscription_id=subscription_id, status=WebhookSubscriptionStatus.ERROR, error=str(error)
    )


class GoogleWebhookService(BaseWebhookService):
    """App-level Google Health API subscriber registration."""

    async def register_subscriptions(self, callback_url: str | None = None) -> list[dict[str, Any]]:
        """Register (or refresh) the project's Health API subscriber for our callback."""
        if not callback_url:
            raise ValueError("callback_url is required to register webhook subscriptions")
        if not settings.google_project_id:
            raise ValueError("GOOGLE_PROJECT_ID is not configured; cannot register Health API subscribers")
        if not settings.google_webhook_secret:
            raise ValueError("google webhook secret is not configured")

        # secret is the literal Authorization header value Google echoes back on every
        # notification; GoogleWebhookHandler.verify_signature expects the "Bearer " prefix.
        body = {
            "endpointUri": callback_url,
            "subscriberConfigs": [
                {"dataTypes": GOOGLE_WEBHOOK_DATA_TYPES, "subscriptionCreatePolicy": "AUTOMATIC"},
            ],
            "endpointAuthorization": {
                "secret": f"Bearer {settings.google_webhook_secret.get_secret_value()}",
            },
        }
        url = _subscribers_url()
        headers = {"Authorization": f"Bearer {self._project_token()}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, headers=headers, params={"subscriberId": SUBSCRIBER_ID}, json=body, timeout=30.0
                )
                if response.status_code == 409:
                    return [{"status": "skipped", "subscriber_id": SUBSCRIBER_ID}]
                response.raise_for_status()
            except httpx.HTTPError as e:
                response_body = e.response.text if isinstance(e, httpx.HTTPStatusError) else None
                log_structured(
                    logger,
                    "error",
                    "Failed to register Google Health API subscriber",
                    provider="google",
                    action="google_webhook_subscription_register_error",
                    error=str(e),
                    status_code=e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None,
                    response_body=response_body,
                )
                return [{"status": "error", "error": str(e), "response_body": response_body}]

        return [{"status": "created", "subscriber_id": SUBSCRIBER_ID, "response": response.json()}]

    async def list_subscriptions(self) -> list[ProviderWebhookSubscription]:
        """List the project's Health API subscribers."""
        headers = {"Authorization": f"Bearer {self._project_token()}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(_subscribers_url(), headers=headers, timeout=30.0)
                response.raise_for_status()
                raw = response.json() or {}
        except httpx.HTTPError as e:
            log_structured(
                logger,
                "error",
                "Failed to list Google Health API subscribers",
                provider="google",
                action="google_webhook_subscription_list_error",
                error=str(e),
                status_code=e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None,
            )
            return []

        result: list[ProviderWebhookSubscription] = []
        for item in raw.get("subscribers", []):
            try:
                result.append(GoogleWebhookSubscription.model_validate(item))
            except ValidationError as e:
                log_structured(
                    logger,
                    "error",
                    "Failed to parse Google Health API subscriber",
                    provider="google",
                    action="google_webhook_subscription_parse_error",
                    error=str(e),
                )
        return result

    async def get_subscription(self, subscription_id: str) -> GoogleWebhookSubscription | None:
        """Fetch a single subscriber by id; None if missing or unparseable."""
        headers = {"Authorization": f"Bearer {self._project_token()}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{_subscribers_url()}/{subscription_id}", headers=headers, timeout=30.0)
                response.raise_for_status()
                return GoogleWebhookSubscription.model_validate(response.json())
        except (httpx.HTTPError, ValidationError) as e:
            log_structured(
                logger,
                "error",
                "Failed to get Google Health API subscriber",
                provider="google",
                action="google_webhook_subscription_get_error",
                subscription_id=subscription_id,
                error=str(e),
            )
            return None

    async def update_subscription(self, subscription_id: str, callback_url: str) -> WebhookOperationResult:
        """Update a subscriber's callback URL (triggers Google's endpoint re-verification)."""
        headers = {"Authorization": f"Bearer {self._project_token()}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{_subscribers_url()}/{subscription_id}",
                    headers=headers,
                    params={"updateMask": "endpointUri"},
                    json={"endpointUri": callback_url},
                    timeout=30.0,
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            return _error_result(subscription_id, "update", e)
        return WebhookOperationResult(subscription_id=subscription_id, status=WebhookSubscriptionStatus.UPDATED)

    async def delete_subscription(self, subscription_id: str) -> WebhookOperationResult:
        """Delete a subscriber by id."""
        headers = {"Authorization": f"Bearer {self._project_token()}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(f"{_subscribers_url()}/{subscription_id}", headers=headers, timeout=30.0)
                response.raise_for_status()
        except httpx.HTTPError as e:
            return _error_result(subscription_id, "delete", e)
        return WebhookOperationResult(subscription_id=subscription_id, status=WebhookSubscriptionStatus.DELETED)

    def _project_token(self) -> str:
        """Mint a short-lived project-level access token for the subscriber API.

        Uses the service-account key at ``google_service_account_file`` when set,
        otherwise Application Default Credentials. The refresh is a blocking network
        call; acceptable here since registration runs in a Celery task.
        """
        if settings.google_service_account_file:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    settings.google_service_account_file, scopes=[_SUBSCRIBER_SCOPE]
                )
            except OSError as e:
                raise ValueError(
                    f"Could not read google_service_account_file {settings.google_service_account_file!r}: {e}"
                ) from e
        else:
            credentials, _ = google.auth.default(scopes=[_SUBSCRIBER_SCOPE])
        credentials.refresh(GoogleAuthRequest())
        return credentials.token
