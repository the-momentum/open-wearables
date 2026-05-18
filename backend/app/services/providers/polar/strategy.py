from app.database import SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.enums import ProviderName
from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.polar.data_247 import Polar247Data
from app.services.providers.polar.oauth import PolarOAuth
from app.services.providers.polar.webhook_handler import PolarWebhookHandler
from app.services.providers.polar.webhook_service import polar_webhook_service
from app.services.providers.polar.workouts import PolarWorkouts


class PolarStrategy(BaseProviderStrategy):
    """Polar provider implementation."""

    def __init__(self):
        super().__init__()
        self.provider_settings_repo = ProviderSettingsRepository()
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

    async def register_webhooks(self, callback_url: str) -> list[dict]:
        result = await polar_webhook_service.register_subscriptions(callback_url)
        if result.get("status") == "created":
            secret = result.get("response", {}).get("signature_secret_key")
            if not secret:
                raise ValueError("Polar webhook registration succeeded but no signature_secret_key was returned.")
            with SessionLocal() as db:
                self.provider_settings_repo.save_webhook_secret(db, ProviderName.POLAR, secret)
        return [result]
