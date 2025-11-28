from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.suunto.oauth import SuuntoOAuth
from app.services.providers.suunto.workouts import SuuntoWorkouts


class SuuntoStrategy(BaseProviderStrategy):
    """Suunto provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = SuuntoOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
        )
        self.workouts = SuuntoWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

    @property
    def name(self) -> str:
        return "suunto"

    @property
    def api_base_url(self) -> str:
        return "https://cloudapi.suunto.com"
