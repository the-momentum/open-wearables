"""Dexcom CGM 247 Data implementation for EGV (Estimated Glucose Values)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas import TimeSeriesSampleCreate
from app.schemas.series_types import SeriesType
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service

# Dexcom API limits queries to 90-day windows
MAX_QUERY_DAYS = 90


class Dexcom247Data(Base247DataTemplate):
    """Dexcom CGM implementation for 247 data (EGV glucose readings)."""

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ):
        super().__init__(provider_name, api_base_url, oauth)
        self.connection_repo = UserConnectionRepository()

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make authenticated request to Dexcom API."""
        return make_authenticated_request(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            api_base_url=self.api_base_url,
            provider_name=self.provider_name,
            endpoint=endpoint,
            method="GET",
            params=params,
            headers=headers,
        )

    # -------------------------------------------------------------------------
    # EGV (Estimated Glucose Values) — /v3/users/self/egvs
    # -------------------------------------------------------------------------

    def _fetch_egvs_chunked(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch EGV data, splitting into <=90-day chunks as required by Dexcom API."""
        all_records: list[dict[str, Any]] = []
        chunk_start = start_time

        while chunk_start < end_time:
            chunk_end = min(chunk_start + timedelta(days=MAX_QUERY_DAYS), end_time)

            params = {
                "startDate": chunk_start.strftime("%Y-%m-%dT%H:%M:%S"),
                "endDate": chunk_end.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            try:
                response = self._make_api_request(db, user_id, "/v3/users/self/egvs", params=params)
                records = response.get("records", []) if isinstance(response, dict) else []
                all_records.extend(records)
            except Exception as e:
                self.logger.error(f"Error fetching EGVs for chunk {chunk_start} - {chunk_end}: {e}")
                if all_records:
                    self.logger.warning("Returning partial EGV data due to error")
                    break
                raise

            chunk_start = chunk_end

        return all_records

    def save_egv_data(
        self,
        db: DbSession,
        user_id: UUID,
        records: list[dict[str, Any]],
    ) -> int:
        """Save EGV records to database as blood_glucose time series samples."""
        count = 0
        for record in records:
            value = record.get("value")
            system_time = record.get("systemTime")
            record_id = record.get("recordId")

            if value is None or not system_time:
                continue

            # Skip records with status (indicates sensor error / calibration)
            if record.get("status"):
                continue

            try:
                recorded_at = datetime.fromisoformat(system_time.replace("Z", "+00:00"))
                # If no timezone info, assume UTC
                if recorded_at.tzinfo is None:
                    recorded_at = recorded_at.replace(tzinfo=timezone.utc)

                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(value)),
                    series_type=SeriesType.blood_glucose,
                    external_id=record_id,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save EGV record: {e}")

        return count

    def load_and_save_egvs(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Fetch EGV data from Dexcom API and save to database."""
        records = self._fetch_egvs_chunked(db, user_id, start_time, end_time)
        return self.save_egv_data(db, user_id, records)

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
    ) -> dict[str, int]:
        """Load and save all Dexcom data types (EGV glucose readings).

        Args:
            db: Database session
            user_id: User UUID
            start_time: Start of date range (defaults to 30 days ago)
            end_time: End of date range (defaults to now)
            is_first_sync: Whether this is the first sync (unused for Dexcom)
        """
        # Parse string datetimes
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        results = {"egv_samples_synced": 0}

        try:
            results["egv_samples_synced"] = self.load_and_save_egvs(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync Dexcom EGV data: {e}")

        return results

    # -------------------------------------------------------------------------
    # Abstract method stubs (CGM has no sleep/recovery/activity)
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Not applicable for Dexcom CGM."""
        return []

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Not applicable for Dexcom CGM."""
        return {}

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Not applicable for Dexcom CGM."""
        return []

    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Not applicable for Dexcom CGM."""
        return {}

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Not applicable for Dexcom CGM."""
        return []

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Not applicable for Dexcom CGM."""
        return {}

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Not applicable for Dexcom CGM."""
        return []

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Not applicable for Dexcom CGM."""
        return {}
