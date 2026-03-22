from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.sensorbio.data_247 import SensorBio247Data
from app.services.providers.sensorbio.oauth import SensorBioOAuth
from app.services.providers.sensorbio.workouts import SensorBioWorkouts


class SensorBioStrategy(BaseProviderStrategy):
    """Sensor Bio provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = SensorBioOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.workouts = SensorBioWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )
        self.data_247 = SensorBio247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

    @property
    def name(self) -> str:
        return "sensorbio"

    @property
    def display_name(self) -> str:
        return "Sensor Bio"

    @property
    def api_base_url(self) -> str:
        return "https://api.sensorbio.com"
