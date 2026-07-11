from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.withings.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.notify_service import WithingsNotifyService
from app.services.providers.withings.oauth import WithingsOAuth
from app.services.providers.withings.webhook_handler import WithingsWebhookHandler
from app.services.providers.withings.workouts import WithingsWorkouts


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
        self.webhook_service = WithingsNotifyService(
            connection_repo=self.connection_repo,
            oauth=self.oauth,
        )

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
