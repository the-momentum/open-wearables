from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.sensr.data_247 import Sensr247Data
from app.services.providers.sensr.oauth import SensrOAuth
from app.services.providers.sensr.workouts import SensrWorkouts


class SensrStrategy(BaseProviderStrategy):
    """Sensor Bio provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = SensrOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.workouts = SensrWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        self.data_247 = Sensr247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

    @property
    def name(self) -> str:
        return "sensr"

    @property
    def display_name(self) -> str:
        return "Sensor Bio"

    @property
    def api_base_url(self) -> str:
        return "https://api.getsensr.io"
