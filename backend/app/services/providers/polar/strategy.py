from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.polar.oauth import PolarOAuth
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

    @property
    def name(self) -> str:
        return "polar"

    @property
    def api_base_url(self) -> str:
        return "https://www.polaraccesslink.com"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Polar AccessLink 3.0 uses a transaction-based REST API for data pull
        # and supports a webhook feature that sends a notification when new data
        # is available.  Actual data is fetched via the transaction endpoints.
        return ProviderCapabilities(rest_pull=True, webhook_ping=True)
