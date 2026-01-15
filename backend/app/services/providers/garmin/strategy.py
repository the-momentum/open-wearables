from app.services.providers.base_strategy import BaseProviderStrategy
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
