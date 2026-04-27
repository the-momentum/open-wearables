from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.suunto.data_247 import Suunto247Data
from app.services.providers.suunto.oauth import SuuntoOAuth
from app.services.providers.suunto.webhook_handler import SuuntoWebhookHandler
from app.services.providers.suunto.workouts import SuuntoWorkouts


class SuuntoStrategy(BaseProviderStrategy):
    """Suunto provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = SuuntoOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.workouts = SuuntoWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        self.data_247 = Suunto247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        self.webhooks = SuuntoWebhookHandler(
            suunto_workouts=self.workouts,
            suunto_247=self.data_247,
        )

    @property
    def name(self) -> str:
        return "suunto"

    @property
    def api_base_url(self) -> str:
        return "https://cloudapi.suunto.com"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Historical sync uses REST (rest_pull); live data via webhooks (webhook_stream).
        return ProviderCapabilities(rest_pull=True, webhook_stream=True)
