from app.services.providers.apple.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.apple.workouts import AppleWorkouts
from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage


class AppleStrategy(BaseProviderStrategy):
    """Apple Health provider implementation."""

    def __init__(self):
        super().__init__()
        self.workouts = AppleWorkouts(self.workout_repo, self.connection_repo)

    @property
    def name(self) -> str:
        return "apple"

    @property
    def display_name(self) -> str:
        return "Apple Health"

    @property
    def api_base_url(self) -> str:
        return ""  # Apple Health doesn't have a cloud API

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Apple Health data arrives exclusively via XML export or HealthKit SDK.
        # No cloud OAuth, no REST polling, no server-side webhooks.
        return ProviderCapabilities(client_sdk=True, file_import=True)

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )
