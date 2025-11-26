from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.garmin.oauth import GarminOAuth


class GarminStrategy(BaseProviderStrategy):
    """Garmin provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = GarminOAuth(self.user_repo, self.connection_repo)
        # self.workouts = GarminWorkouts(self.workout_repo, self.connection_repo) # To be implemented

    @property
    def name(self) -> str:
        return "garmin"
