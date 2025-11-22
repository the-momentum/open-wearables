from abc import ABC, abstractmethod
from uuid import UUID

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.oauth import OAuthTokenResponse


class BaseOAuthTemplate(ABC):
    """Base template for OAuth 2.0 authentication flow.

    This class implements the Template Method pattern for OAuth operations.
    It defines the skeleton of the OAuth flow while letting subclasses
    implement the specific details for each provider.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        connection_repo: UserConnectionRepository,
    ):
        self.user_repo = user_repo
        self.connection_repo = connection_repo

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Generates the provider's authorization URL.

        Args:
            state: A unique state string to prevent CSRF attacks.

        Returns:
            str: The authorization URL to redirect the user to.
        """
        pass

    @abstractmethod
    def exchange_code_for_token(self, code: str) -> OAuthTokenResponse:
        """Exchanges the authorization code for an access token.

        Args:
            code: The authorization code received from the provider.

        Returns:
            OAuthTokenResponse: The token response containing access_token, refresh_token, etc.
        """
        pass

    def handle_callback(self, db: DbSession, user_id: UUID, code: str) -> None:
        """Handles the OAuth callback, exchanges code, and saves the connection.

        This is a template method that orchestrates the callback handling.

        Args:
            db: The database session.
            user_id: The ID of the user authenticating.
            code: The authorization code received from the provider.
        """
        # Exchange code for token (implemented by subclass)
        token_data = self.exchange_code_for_token(code)

        # Save or update the connection (common logic)
        # Note: This logic might need to be more complex depending on whether
        # we are creating a new connection or updating an existing one.
        # For now, we'll assume the repository handles the upsert logic or we implement it here.
        # This is a placeholder for the actual implementation.
        pass
