from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.gadgetbridge.coverage import (
    HEALTH_SCORES,
    MEAL_FIELDS,
    SLEEP_FIELDS,
    TIMESERIES,
    WORKOUT_FIELDS,
)


class GadgetbridgeStrategy(BaseProviderStrategy):
    """Local Gadgetbridge exports delivered through the shared SDK ingestion API."""

    @property
    def name(self) -> str:
        return "gadgetbridge"

    @property
    def display_name(self) -> str:
        return "Gadgetbridge"

    @property
    def api_base_url(self) -> str:
        return ""

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(client_sdk=True)

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            meal_fields=MEAL_FIELDS,
            health_scores=HEALTH_SCORES,
        )
