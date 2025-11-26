from app.services.providers.apple.workouts import AppleWorkouts
from app.services.providers.base_strategy import BaseProviderStrategy


class AppleStrategy(BaseProviderStrategy):
    """Apple Health provider implementation."""

    def __init__(self):
        super().__init__()
        self.workouts = AppleWorkouts(self.workout_repo, self.connection_repo)

    @property
    def name(self) -> str:
        return "apple"
