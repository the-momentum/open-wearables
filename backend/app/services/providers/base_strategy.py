from abc import ABC, abstractmethod

from app.models import EventRecord, User
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class BaseProviderStrategy(ABC):
    """Abstract base class for all fitness data providers."""

    def __init__(self):
        """Initialize shared repositories used by all provider components."""
        self.user_repo = UserRepository(User)
        self.connection_repo = UserConnectionRepository()
        self.workout_repo = EventRecordRepository(EventRecord)

        # Components should be initialized by subclasses
        self.oauth: BaseOAuthTemplate | None = None
        self.workouts: BaseWorkoutsTemplate | None = None
        self.data_247: Base247DataTemplate | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the unique name of the provider (e.g., 'garmin', 'suunto')."""
        pass

    @property
    @abstractmethod
    def api_base_url(self) -> str:
        """Returns the base URL for the provider's API."""
        pass

    @property
    def display_name(self) -> str:
        """Returns the display name of the provider (e.g., 'Garmin', 'Apple Health')."""
        return self.name.capitalize()

    @property
    def has_cloud_api(self) -> bool:
        """Returns True if provider uses cloud OAuth API."""
        return self.oauth is not None

    @property
    def icon_url(self) -> str:
        """Returns the URL path to the provider's icon."""
        return f"/static/provider-icons/{self.name}.svg"
