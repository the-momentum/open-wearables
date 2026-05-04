from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.strava.oauth import StravaOAuth
from app.services.providers.strava.webhook_handler import StravaWebhookHandler
from app.services.providers.strava.webhook_service import strava_webhook_service
from app.services.providers.strava.workouts import StravaWorkouts


class StravaStrategy(BaseProviderStrategy):
    """Strava provider implementation."""

    def __init__(self):
        super().__init__()

        # Initialize OAuth component
        self.oauth = StravaOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )

        # Initialize workouts component
        self.workouts = StravaWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

        # Strava has no continuous monitoring data (no sleep, HRV, daily summaries)
        self.data_247 = None

        self.webhooks = StravaWebhookHandler(workouts=self.workouts)

    @property
    def name(self) -> str:
        """Unique identifier for the provider (lowercase)."""
        return "strava"

    @property
    def api_base_url(self) -> str:
        """Base URL for the provider's API."""
        return "https://www.strava.com/api/v3"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Strava REST API is used for historical activity backfills.
        # Strava webhook events contain only the object_id and aspect_type;
        # the full activity must still be fetched via GET /activities/{id}.
        return ProviderCapabilities(rest_pull=True, webhook_ping=True, webhook_registration_api=True)

    async def register_webhooks(self, callback_url: str) -> list[dict]:
        return await strava_webhook_service.register_subscriptions(callback_url)
