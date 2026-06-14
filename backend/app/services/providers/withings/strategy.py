"""Withings provider strategy.

Withings delivers data via a REST API (RPC-over-POST with an ``action`` param,
every response wrapped in a ``{status, body}`` envelope) and via notify-only
webhooks. Subscriptions are **per-user** (created with the user's bearer token),
so they are registered from the connect lifecycle (``on_connect``) rather than
the app-level webhook-registration API.
"""

from uuid import UUID

from celery import current_app as celery_app

from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.oauth import WithingsOAuth
from app.services.providers.withings.webhook_handler import WithingsWebhookHandler
from app.services.providers.withings.workouts import WithingsWorkouts

_SUBSCRIBE_WITHINGS_USER_TASK = "app.integrations.celery.tasks.withings.subscribe_task.subscribe_withings_user"


class WithingsStrategy(BaseProviderStrategy):
    """Withings provider implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.oauth = WithingsOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.data_247 = Withings247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        self.workouts = WithingsWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        self.webhooks = WithingsWebhookHandler(data_247=self.data_247, workouts=self.workouts)
        # Subscriptions are per-user (see on_connect), so the app-level service is unused.
        self.webhook_service = None

    @property
    def name(self) -> str:
        return "withings"

    @property
    def api_base_url(self) -> str:
        return "https://wbsapi.withings.net"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            rest_pull=True,
            webhook_ping=True,
        )

    def on_connect(self, user_id: UUID) -> None:
        """Register the user's notify subscriptions."""
        celery_app.send_task(_SUBSCRIBE_WITHINGS_USER_TASK, args=[str(user_id)])
