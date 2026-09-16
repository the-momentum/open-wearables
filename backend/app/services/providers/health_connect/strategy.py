from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.health_connect.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS


class HealthConnectStrategy(BaseProviderStrategy):
    """Android Health Connect — data pushed from mobile devices via the SDK.

    The Google Health API cloud path is a separate provider; see
    ``app/services/providers/google_health/strategy.py``.
    """

    @property
    def name(self) -> str:
        return "health_connect"

    @property
    def display_name(self) -> str:
        return "Health Connect"

    @property
    def api_base_url(self) -> str:
        return ""  # Health Connect has no cloud API

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(client_sdk=True)

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )
