"""Base template for 247 data (sleep, recovery, activity samples)."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.sync_247_result import Sync247Result, Sync247Run
from app.utils.dates import parse_datetime_or_default


class Base247DataTemplate(ABC):
    """Base template for fetching and processing 247 data (sleep, recovery, activity).

    This template handles continuous monitoring data that is typically:
    - Collected passively by wearables 24/7
    - Aggregated into daily summaries or time-series samples
    - Includes: sleep sessions, recovery metrics, activity samples (steps, HR, etc.)
    """

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: "BaseOAuthTemplate",
    ):
        self.provider_name = provider_name
        self.api_base_url = api_base_url
        self.oauth = oauth
        self.logger = logging.getLogger(self.__class__.__name__)

    # -------------------------------------------------------------------------
    # Sleep Data
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep data from provider API."""
        pass

    @abstractmethod
    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize provider-specific sleep data to our schema."""
        pass

    def process_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch and normalize sleep data."""
        raw_data = self.get_sleep_data(db, user_id, start_time, end_time)
        return [self.normalize_sleep(item, user_id) for item in raw_data]

    # -------------------------------------------------------------------------
    # Recovery Data
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch recovery data from provider API."""
        pass

    @abstractmethod
    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize provider-specific recovery data to our schema."""
        pass

    def process_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch and normalize recovery data."""
        raw_data = self.get_recovery_data(db, user_id, start_time, end_time)
        return [self.normalize_recovery(item, user_id) for item in raw_data]

    # -------------------------------------------------------------------------
    # Activity Samples (HR, Steps, SpO2, etc.)
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch activity samples (HR, steps, SpO2) from provider API."""
        pass

    @abstractmethod
    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize activity samples into categorized data.

        Returns dict with keys like 'heart_rate', 'steps', 'spo2', etc.
        """
        pass

    def process_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch and normalize activity samples."""
        raw_data = self.get_activity_samples(db, user_id, start_time, end_time)
        return self.normalize_activity_samples(raw_data, user_id)

    # -------------------------------------------------------------------------
    # Daily Activity Statistics
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch aggregated daily activity statistics."""
        pass

    @abstractmethod
    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize daily activity statistics to our schema."""
        pass

    def process_daily_activity(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch and normalize daily activity statistics."""
        raw_data = self.get_daily_activity_statistics(db, user_id, start_date, end_date)
        return [self.normalize_daily_activity(item, user_id) for item in raw_data]

    # -------------------------------------------------------------------------
    # Combined Load
    # -------------------------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> Sync247Result:
        """Fetch and persist every 24/7 data type this provider supports.

        Providers override this and build the result through :class:`Sync247Run`
        so failures stay isolated to one data type. The default is an empty
        result, for providers whose 24/7 data only ever arrives by push.
        """
        return Sync247Result(provider=self.provider_name, note="No pull-based 24/7 sync for this provider")

    def sync_run(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Sync247Run:
        """Start a 24/7 sync run bound to this provider."""
        return Sync247Run(self.provider_name, db, user_id, self.logger, **kwargs)

    def resolve_window(
        self,
        start_time: datetime | str | None,
        end_time: datetime | str | None,
        *,
        default_days: int = 30,
    ) -> tuple[datetime, datetime]:
        """Normalize a sync window: parse ISO strings, apply defaults, force UTC-aware.

        Callers pass windows as datetimes, ISO strings or nothing at all (Celery
        task, sync route, webhook replays). Resolving that in one place keeps a
        naive datetime from reaching a comparison against an aware one.
        """
        end_dt = parse_datetime_or_default(end_time, datetime.now(timezone.utc))
        start_dt = parse_datetime_or_default(start_time, end_dt - timedelta(days=default_days))
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        return start_dt, end_dt

    def load_all_247_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Load all 247 data types in one call."""
        return {
            "sleep": self.process_sleep_data(db, user_id, start_time, end_time),
            "recovery": self.process_recovery_data(db, user_id, start_time, end_time),
            "activity_samples": self.process_activity_samples(db, user_id, start_time, end_time),
            "daily_activity": self.process_daily_activity(db, user_id, start_time, end_time),
        }

    # -------------------------------------------------------------------------
    # Raw API Access (for debugging)
    # -------------------------------------------------------------------------

    def get_raw_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> Any:
        """Get raw sleep data from API without normalization."""
        return self.get_sleep_data(db, user_id, start_time, end_time)

    def get_raw_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> Any:
        """Get raw recovery data from API without normalization."""
        return self.get_recovery_data(db, user_id, start_time, end_time)

    def get_raw_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> Any:
        """Get raw activity samples from API without normalization."""
        return self.get_activity_samples(db, user_id, start_time, end_time)
