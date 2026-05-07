from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.oura.data_247 import Oura247Data
from app.services.providers.oura.oauth import OuraOAuth
from app.services.providers.oura.webhook_handler import OuraWebhookHandler
from app.services.providers.oura.webhook_service import oura_webhook_service
from app.services.providers.oura.workouts import OuraWorkouts


class OuraStrategy(BaseProviderStrategy):
    """Oura Ring provider implementation."""

    def __init__(self):
        super().__init__()

        # Initialize OAuth component
        self.oauth = OuraOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )

        # Initialize workouts component
        self.workouts = OuraWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

        # 247 data handler for sleep, readiness, heart rate, activity, SpO2
        self.data_247 = Oura247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

        self.webhooks = OuraWebhookHandler(
            data_247=self.data_247,
            workouts=self.workouts,
        )

    @property
    def name(self) -> str:
        """Unique identifier for the provider (lowercase)."""
        return "oura"

    @property
    def api_base_url(self) -> str:
        """Base URL for the provider's API."""
        return "https://api.ouraring.com"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(rest_pull=True, webhook_ping=True, webhook_registration_api=True)

    async def register_webhooks(self, callback_url: str) -> list[dict]:
        return await oura_webhook_service.register_subscriptions(callback_url)
