from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_repository import WorkoutRepository
from app.services.providers.apple.provider import AppleProvider
from app.services.providers.base_provider import BaseProviderStrategy


class ProviderFactory:
    """Factory for creating provider instances with injected dependencies."""

    def __init__(self):
        # Initialize repositories
        self.user_repo = UserRepository()
        self.connection_repo = UserConnectionRepository()
        self.workout_repo = WorkoutRepository()

    def get_provider(self, provider_name: str) -> BaseProviderStrategy:
        """Returns a configured provider instance.

        Args:
            provider_name: The name of the provider (e.g., 'garmin', 'apple').

        Returns:
            BaseProviderStrategy: The configured provider instance.

        Raises:
            ValueError: If the provider name is unknown.
        """
        if provider_name == "apple":
            return AppleProvider(self.connection_repo, self.workout_repo)
        
        # TODO: Add other providers (Garmin, Suunto, Polar)
        # if provider_name == "garmin":
        #     return GarminProvider(...)
        
        raise ValueError(f"Unknown provider: {provider_name}")
