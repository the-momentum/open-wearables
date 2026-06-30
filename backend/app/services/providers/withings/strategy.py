from uuid import UUID

from celery import current_app as celery_app

from app.database import SessionLocal
from app.schemas.auth import LiveSyncMode
from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.withings.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.oauth import WithingsOAuth
from app.services.providers.withings.webhook_handler import WithingsWebhookHandler
from app.services.providers.withings.workouts import WithingsWorkouts

_SUBSCRIBE_WITHINGS_USER_TASK = "app.integrations.celery.tasks.withings.subscribe_task.subscribe_withings_user"
_REVOKE_WITHINGS_USER_TASK = "app.integrations.celery.tasks.withings.subscribe_task.revoke_withings_user"


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
        self.webhooks = WithingsWebhookHandler(
            data_247=self.data_247,
            workouts=self.workouts,
            default_live_sync_mode=self.default_live_sync_mode,
        )
        # Subscriptions are per-user, so the app-level registration service is unused.
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
            webhook_per_user_subscriptions=True,
        )

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )

    def on_connect(self, user_id: UUID) -> None:
        """Register notify subscriptions only when webhook live sync is active."""
        with SessionLocal() as db:
            if self.effective_live_sync_mode(db) == LiveSyncMode.WEBHOOK:
                celery_app.send_task(_SUBSCRIBE_WITHINGS_USER_TASK, args=[str(user_id)], queue="webhook_sync")

    def live_sync_subscription_task(self, mode: LiveSyncMode) -> str | None:
        if mode == LiveSyncMode.WEBHOOK:
            return _SUBSCRIBE_WITHINGS_USER_TASK
        if mode == LiveSyncMode.PULL:
            return _REVOKE_WITHINGS_USER_TASK
        return None
