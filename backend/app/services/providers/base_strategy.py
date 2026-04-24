from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from celery import current_app as celery_app

from app.models import EventRecord, User
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LiveSyncMode
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.utils.exceptions import UnsupportedProviderError


@dataclass
class HistoricalSyncResult:
    """Result of dispatching a historical sync task."""

    task_id: str
    method: Literal["pull_api", "webhook_backfill"]
    message: str
    days: int | None
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class ProviderCapabilities:
    """Fine-grained capability flags for a provider's data delivery model.

    Attributes
    ----------
    rest_pull:
        Provider exposes a REST API that can be polled for historical or
        recent data (``load_data()`` / ``get_workouts()``).
    client_sdk:
        Data arrives via our mobile SDK endpoint (Samsung Health, Google
        Health Connect, Apple HealthKit).
    file_import:
        Data arrives as a file export from the user's device (Apple Health
        XML). May coexist with ``client_sdk`` for Apple.
    webhook_callback: [request & push]
        We initiate a REST request to start a data export; the provider
        delivers the result to our webhook asynchronously.
        Used for historical backfill. Currently only Garmin.
    webhook_stream [push full-payload]:
        Provider pushes the complete data payload to our webhook inline.
        Live sync runs exclusively from webhooks;
    webhook_ping [notify & pull]:
        Provider sends a lightweight ping to our webhook.
        Actual data must be fetched via REST (``rest_pull`` must be
        ``True``). Oura, Strava, Fitbit, Polar.
    """

    rest_pull: bool = False
    client_sdk: bool = False
    file_import: bool = False
    webhook_callback: bool = False
    webhook_stream: bool = False
    webhook_ping: bool = False
    max_historical_days: int | None = None
    """Hard limit on how many days of history the provider allows. None = no known limit."""

    def __post_init__(self) -> None:
        if self.webhook_stream and self.webhook_ping:
            raise ValueError("webhook_stream and webhook_ping are mutually exclusive")
        if self.webhook_ping and not self.rest_pull:
            raise ValueError("webhook_ping requires rest_pull=True (data must be fetched via REST after the ping)")


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
        data delivery modes the provider supports. The unified webhook router
        and sync scheduler use this to decide how to handle the provider.

        Example::

            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities(
                    rest_pull=True,
                    webhook_ping=True,
                )
        """

    def start_historical_sync(self, user_id: UUID, days: int) -> HistoricalSyncResult:
        """Dispatch an async historical data sync.

        Default implementation works for pull-based providers. Override for
        providers that use a different mechanism (e.g. Garmin webhook backfill).

        Raises UnsupportedProviderError for providers that don't support historical sync.
        """
        if not self.capabilities.rest_pull:
            raise UnsupportedProviderError(self.name, "historical sync")

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        task = celery_app.send_task(
            "app.integrations.celery.tasks.sync_vendor_data_task.sync_vendor_data",
            kwargs={
                "user_id": str(user_id),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "providers": [self.name],
                "is_historical": True,
            },
        )

        return HistoricalSyncResult(
            task_id=task.id,
            method="pull_api",
            message=f"Historical sync queued for {days} days of {self.name} data.",
            days=days,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

    @property
    def display_name(self) -> str:
        """Returns the display name of the provider (e.g., 'Garmin', 'Apple Health')."""
        return self.name.capitalize()

    @property
    def has_cloud_api(self) -> bool:
        """Returns True if provider uses cloud OAuth API."""
        return self.oauth is not None

    @property
    def live_sync_configurable(self) -> bool:
        """True when the admin can choose between pull and webhook live sync.

        Requires rest_pull (periodic fallback exists) plus at least one
        webhook delivery mode (webhook_stream or webhook_ping).
        """
        caps = self.capabilities
        return caps.rest_pull and (caps.webhook_stream or caps.webhook_ping)

    @property
    def default_live_sync_mode(self) -> LiveSyncMode | None:
        """Derive the default live_sync_mode from this provider's capabilities.

        Rules (in priority order):
        - rest_pull → PULL (REST polling is the safe default even if webhooks exist)
        - client_sdk only → None (no server-side sync)
        - webhook_* only, no rest_pull → WEBHOOK
        """
        caps = self.capabilities
        if caps.rest_pull:
            return LiveSyncMode.PULL
        if caps.client_sdk:
            return None
        if caps.webhook_ping or caps.webhook_stream:
            return LiveSyncMode.WEBHOOK
        return None

    @property
    def icon_url(self) -> str:
        """Returns the URL path to the provider's icon."""
        return f"/static/provider-icons/{self.name}.svg"
