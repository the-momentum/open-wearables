from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.suunto.oauth import SuuntoOAuth


class SuuntoStrategy(BaseProviderStrategy):
    """Suunto provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = SuuntoOAuth(self.user_repo, self.connection_repo)

    @property
    def name(self) -> str:
        return "suunto"
