from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.garmin.data_247 import Garmin247Data
from app.services.providers.garmin.oauth import GarminOAuth
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
        return ProviderCapabilities(supports_push=True, supports_async_export=True)
