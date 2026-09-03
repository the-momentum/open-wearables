from app.services.providers.base_strategy import (
    BaseProviderStrategy,
    ProviderCapabilities,
    ProviderCoverage,
)
from app.services.providers.zepp.coverage import (
    HEALTH_SCORES,
    SLEEP_FIELDS,
    TIMESERIES,
    WORKOUT_FIELDS,
)
from app.services.providers.zepp.data_247 import Zepp247Data
from app.services.providers.zepp.workouts import ZeppWorkouts


class ZeppStrategy(BaseProviderStrategy):
    """Amazfit / Zepp provider implementation."""

    def __init__(self) -> None:
        super().__init__()

        # Zepp uses Direct App Token / User ID authentication, not web OAuth2
        self.oauth = None

        self.workouts = ZeppWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=None,
        )

        self.data_247 = Zepp247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=None,
        )

    @property
    def name(self) -> str:
        return "zepp"

    @property
    def display_name(self) -> str:
        return "Amazfit / Zepp"

    @property
    def api_base_url(self) -> str:
        return "https://api-mifit-us3.zepp.com"

    @property
    def has_cloud_api(self) -> bool:
        return True

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            rest_pull=True,
            max_historical_days=365,
        )

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )
