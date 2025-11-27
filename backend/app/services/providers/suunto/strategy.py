from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.suunto.oauth import SuuntoOAuth
from app.services.providers.suunto.workouts import SuuntoWorkouts


class SuuntoStrategy(BaseProviderStrategy):
    """Suunto provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = SuuntoOAuth(self.user_repo, self.connection_repo)
        self.workouts = SuuntoWorkouts(self.workout_repo, self.connection_repo, self.oauth)

    @property
    def name(self) -> str:
        return "suunto"
