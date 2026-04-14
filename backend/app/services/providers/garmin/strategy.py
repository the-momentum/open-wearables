from uuid import UUID

from app.integrations.celery.tasks.garmin_backfill_task import start_full_backfill as start_garmin_full_backfill
from app.services.providers.base_strategy import BaseProviderStrategy, HistoricalSyncResult, ProviderCapabilities
from app.services.providers.garmin.data_247 import Garmin247Data
from app.services.providers.garmin.oauth import GarminOAuth
from app.services.providers.garmin.webhook_handler import GarminWebhookHandler
from app.services.providers.garmin.workouts import GarminWorkouts


class GarminStrategy(BaseProviderStrategy):
    """Garmin provider implementation.

    Supports:
    - OAuth 2.0 with PKCE
    - Workouts/activities
    - 24/7 data (sleep, dailies, epochs, body composition)
    """

    def __init__(self):
        super().__init__()
        self.oauth = GarminOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.workouts = GarminWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        # 24/7 data handler for sleep, dailies, epochs, body composition
        self.data_247 = Garmin247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        self.webhooks = GarminWebhookHandler(
            garmin_workouts=self.workouts,
            garmin_247=self.data_247,
        )

    @property
    def name(self) -> str:
        return "garmin"

    @property
    def api_base_url(self) -> str:
        return "https://apis.garmin.com"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Garmin delivers the full data payload inside every webhook (PUSH) and
        # also supports an async backfill flow (PING → callback URL fetch).
        # There is no plain REST polling path for wellness data; all data
        # arrives via the push/backfill mechanism.
        return ProviderCapabilities(supports_push=True, supports_async_export=True, max_historical_days=30)

    def start_historical_sync(self, user_id: UUID, days: int) -> HistoricalSyncResult:
        """Trigger Garmin's webhook-based 30-day backfill.

        The ``days`` parameter is ignored - Garmin limits historical access
        to 30 days before the user's consent date.
        """
        task = start_garmin_full_backfill.delay(str(user_id))
        return HistoricalSyncResult(
            task_id=task.id,
            method="webhook_backfill",
            message=f"Garmin {self.capabilities.max_historical_days}-day backfill started. "
            "Progress available via backfill/status.",
            days=None,
        )
