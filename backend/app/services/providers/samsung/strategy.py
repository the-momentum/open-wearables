from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.samsung.workouts import SamsungWorkouts


class SamsungStrategy(BaseProviderStrategy):
    """Samsung Health provider implementation.

    Samsung Health is an SDK-based provider (similar to Apple Health) without
    cloud OAuth API. Data is pushed from mobile devices via the SDK.
    """

    def __init__(self):
        super().__init__()
        self.workouts = SamsungWorkouts(self.workout_repo, self.connection_repo)

    @property
    def name(self) -> str:
        return "samsung"

    @property
    def display_name(self) -> str:
        return "Samsung Health"

    @property
    def api_base_url(self) -> str:
        return ""  # Samsung Health doesn't have a cloud API
