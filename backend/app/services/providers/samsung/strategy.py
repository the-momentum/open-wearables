from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.samsung.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS


class SamsungStrategy(BaseProviderStrategy):
    """Samsung Health provider implementation.

    Samsung Health is an SDK-based provider (similar to Apple Health) without
    cloud OAuth API. Metadata only: data pushed from mobile devices via the SDK
    is ingested by the shared pipeline in ``app/services/sdk/``.
    """

    @property
    def name(self) -> str:
        return "samsung"

    @property
    def display_name(self) -> str:
        return "Samsung Health"

    @property
    def api_base_url(self) -> str:
        return ""  # Samsung Health doesn't have a cloud API

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Samsung Health data arrives exclusively via the mobile SDK (no cloud API).
        return ProviderCapabilities(client_sdk=True)

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )
