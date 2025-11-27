from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.polar.oauth import PolarOAuth
from app.services.providers.polar.workouts import PolarWorkouts


class PolarStrategy(BaseProviderStrategy):
    """Polar provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = PolarOAuth(self.user_repo, self.connection_repo)
        self.workouts = PolarWorkouts(self.workout_repo, self.connection_repo, self.oauth)

    @property
    def name(self) -> str:
        return "polar"
