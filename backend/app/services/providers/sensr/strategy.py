from app.services.providers.base_strategy import BaseProviderStrategy


class SensrStrategy(BaseProviderStrategy):
    """Sensr (Sensor Bio) provider implementation.

    Note: this integration is currently a stub to register the provider in the
    system. OAuth + data sync components should be implemented based on the
    Sensr developer API.
    """

    def __init__(self):
        super().__init__()
        # Sensr OAuth/data components to be implemented

    @property
    def name(self) -> str:
        return "sensr"

    @property
    def api_base_url(self) -> str:
        return "https://api.getsensr.io"
