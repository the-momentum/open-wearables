"""Ultrahuman Ring Air provider strategy."""

from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities, ProviderCoverage
from app.services.providers.ultrahuman.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.ultrahuman.data_247 import Ultrahuman247Data
from app.services.providers.ultrahuman.oauth import UltrahumanOAuth


class UltrahumanStrategy(BaseProviderStrategy):
    """Ultrahuman Ring Air provider implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.oauth = UltrahumanOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.data_247 = Ultrahuman247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Ultrahuman Partner API is REST-only; no public webhook offering as of 2025.
        return ProviderCapabilities(rest_pull=True)

    @property
    def name(self) -> str:
        """Unique identifier for the provider (lowercase)."""
        return "ultrahuman"

    @property
    def api_base_url(self) -> str:
        """Base URL for provider's API.

        Base URL for data endpoints: https://partner.ultrahuman.com/api/partners/v1
        OAuth authorization is on: https://auth.ultrahuman.com
        """
        return "https://partner.ultrahuman.com/api/partners/v1"
