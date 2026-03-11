from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.oauth import WithingsOAuth


class WithingsStrategy(BaseProviderStrategy):
    """Withings provider implementation."""

    def __init__(self):
        super().__init__()

        self.oauth = WithingsOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )

        self.data_247 = Withings247Data(
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

    @property
    def name(self) -> str:
        return "withings"

    @property
    def api_base_url(self) -> str:
        return "https://wbsapi.withings.net"

    @property
    def display_name(self) -> str:
        return "Withings"
