from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.polar.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.polar.data_247 import Polar247Data
from app.services.providers.polar.oauth import PolarOAuth
from app.services.providers.polar.webhook_handler import PolarWebhookHandler
from app.services.providers.polar.webhook_service import polar_webhook_service
from app.services.providers.polar.workouts import PolarWorkouts


class PolarStrategy(BaseProviderStrategy):
    """Polar provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = PolarOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.workouts = PolarWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        self.data_247 = Polar247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        self.webhooks = PolarWebhookHandler(workouts=self.workouts, data_247=self.data_247)
        self.webhook_service = polar_webhook_service

    @property
    def name(self) -> str:
        return "polar"

    @property
    def api_base_url(self) -> str:
        return "https://www.polaraccesslink.com"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            rest_pull=True, webhook_ping=True, webhook_registration_api=True, webhook_inbound_secret=True
        )

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES, workout_fields=WORKOUT_FIELDS, sleep_fields=SLEEP_FIELDS, health_scores=HEALTH_SCORES
        )
