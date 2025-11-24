from abc import ABC, abstractmethod

from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class BaseProviderStrategy(ABC):
    """Abstract base class for all fitness data providers.

    This class defines the interface that all providers (e.g., Garmin, Apple, Suunto)
    must implement. It uses the Strategy pattern to allow selecting the appropriate
    provider implementation at runtime.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the unique name of the provider (e.g., 'garmin', 'apple')."""
        pass

    @property
    @abstractmethod
    def oauth(self) -> BaseOAuthTemplate | None:
        """Returns the OAuth handler for this provider.

        Returns:
            BaseOAuthTemplate: The OAuth handler if the provider supports OAuth.
            None: If the provider does not support OAuth (e.g., Apple Health local).
        """
        pass

    @property
    @abstractmethod
    def workouts(self) -> BaseWorkoutsTemplate | None:
        """Returns the Workouts handler for this provider.

        Returns:
            BaseWorkoutsTemplate: The Workouts handler if the provider supports workouts.
            None: If the provider does not support workouts.
        """
        pass
