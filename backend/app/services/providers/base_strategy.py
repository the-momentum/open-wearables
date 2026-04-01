from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from app.models import EventRecord, User
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class DeliveryMode(str, Enum):
    """High-level data delivery mode for a provider.

    Use ``ProviderCapabilities`` for fine-grained capability flags.
    This enum is useful for quick routing decisions and UI labels.

    * ``PULL``   – OpenWearables polls the provider REST API on a schedule.
    * ``PUSH``   – Provider pushes data directly to our webhook endpoint.
    * ``HYBRID`` – Provider delivers data via webhook *after* an explicit
                   REST backfill request (Garmin-style).
    """

    PULL = "pull"
    PUSH = "push"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class ProviderCapabilities:
    """Fine-grained capability flags for a provider's data delivery model.

    Providers may support multiple modes simultaneously (e.g. Oura supports
    both REST polling and webhook notifications).

    Attributes
    ----------
    supports_pull:
        Provider exposes a REST API that can be polled for historical or
        recent data (``load_data()`` / ``get_workouts()``).
    supports_push:
        Provider can send incoming webhook events to our endpoint.  This
        covers both full-payload webhooks (Garmin) and notification-only
        webhooks (Oura, Strava).
    supports_backfill:
        Provider supports an async backfill API where an explicit REST
        request triggers data delivery via a subsequent webhook.  Garmin
        is the canonical example.
    supports_file_upload:
        Data arrives as a file upload (Apple Health XML, HealthKit package,
        Samsung/Google SDK payload).  No cloud OAuth or webhooks involved.
    webhook_notify_only:
        When ``True`` the webhook payload contains only a lightweight
        notification (user_id + event_type) and the actual data must still
        be fetched via the REST API (``supports_pull`` should also be
        ``True``).  Oura, Strava, Fitbit, Suunto and Polar follow this
        pattern.  When ``False`` (Garmin) the webhook delivers the full
        data payload and no subsequent REST call is needed.
    """

    supports_pull: bool = False
    supports_push: bool = False
    supports_backfill: bool = False
    supports_file_upload: bool = False
    webhook_notify_only: bool = False


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
        self.webhooks: BaseWebhookHandler | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the unique name of the provider (e.g., 'garmin', 'suunto')."""

    @property
    @abstractmethod
    def api_base_url(self) -> str:
        """Returns the base URL for the provider's API."""

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Declares the data delivery capabilities of this provider.

        Each concrete strategy must override this to accurately reflect what
        data delivery modes the provider supports.  The unified webhook router
        and sync scheduler use this to decide how to handle the provider.

        Example::

            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities(supports_pull=True, supports_push=True, webhook_notify_only=True)
        """

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
