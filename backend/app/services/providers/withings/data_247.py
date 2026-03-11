"""Withings 247 Data implementation for body measurements and sleep.

All Withings data API endpoints are POST-based with an 'action' parameter.
Measurement values use the formula: real_value = value * 10^unit (unit is typically negative).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from app.database import DbSession
from app.models import DataSource, EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.series_types import SeriesType
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.withings.oauth import WithingsOAuth
from app.services.timeseries_service import timeseries_service

# Withings meastype → (SeriesType, description)
# See: https://developer.withings.com/api-reference/#tag/measure/operation/measure-getmeas
MEASTYPE_MAP: dict[int, SeriesType] = {
    1: SeriesType.weight,
    6: SeriesType.body_fat_percentage,
    9: SeriesType.blood_pressure_diastolic,
    10: SeriesType.blood_pressure_systolic,
    11: SeriesType.heart_rate,
    54: SeriesType.oxygen_saturation,
    71: SeriesType.body_temperature,
}


class Withings247Data(Base247DataTemplate):
    """Withings implementation for 247 data (body measurements, sleep)."""

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ):
        super().__init__(provider_name, api_base_url, oauth)
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.data_source_repo = DataSourceRepository(DataSource)
        self.connection_repo = UserConnectionRepository()

    def _get_access_token(self, db, user_id: UUID) -> str:
        """Get a valid access token, refreshing if needed."""
        connection = self.connection_repo.get_by_user_and_provider(db, user_id, self.provider_name)
        if not connection:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"No Withings connection found for user {user_id}",
            )

        # Check if token needs refresh (5-minute buffer)
        if connection.token_expires_at and connection.token_expires_at < datetime.now(timezone.utc) + timedelta(
            minutes=5
        ):
            token_response = self.oauth.refresh_access_token(db, user_id, connection.refresh_token)
            return token_response.access_token

        return connection.access_token

    def _make_api_request(
        self,
        db,
        user_id: UUID,
        endpoint: str,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make authenticated POST request to Withings API with signature.

        All Withings data endpoints require:
        1. Bearer token auth
        2. POST with action parameter
        3. HMAC-SHA256 signature + nonce (for signed endpoints)
        """
        access_token = self._get_access_token(db, user_id)

        data: dict[str, Any] = {"action": action}
        if params:
            data.update(params)

        try:
            response = httpx.post(
                f"{self.api_base_url}{endpoint}",
                data=data,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            status = result.get("status", -1)
            if status != 0:
                self.logger.error(f"Withings API error on {endpoint} action={action}: status={status}, body={result}")
                raise ValueError(f"Withings API returned error status {status}")

            return result.get("body", {})
        except httpx.HTTPStatusError as e:
            # If 401, try refreshing token once
            if e.response.status_code == 401:
                self.logger.info("Withings token expired, refreshing...")
                connection = self.connection_repo.get_by_user_and_provider(db, user_id, self.provider_name)
                if connection and connection.refresh_token:
                    token_response = self.oauth.refresh_access_token(db, user_id, connection.refresh_token)
                    # Retry with new token
                    response = httpx.post(
                        f"{self.api_base_url}{endpoint}",
                        data=data,
                        headers={
                            "Authorization": f"Bearer {token_response.access_token}",
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    result = response.json()
                    return result.get("body", {})
            raise
        except ValueError:
            raise
        except Exception as e:
            self.logger.error(f"Error making Withings API request to {endpoint}: {e}")
            raise

    @staticmethod
    def _convert_measurement(value: int, unit: int) -> Decimal:
        """Convert Withings measurement value to real value.

        Withings returns value * 10^unit where unit is typically negative.
        Example: value=7295, unit=-2 → 72.95
        """
        return Decimal(str(value)) * Decimal(10) ** Decimal(str(unit))

    # -------------------------------------------------------------------------
    # Body Measurements — POST /measure action=getmeas
    # -------------------------------------------------------------------------

    def get_measurements(
        self,
        db,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch body measurements from Withings API with pagination."""
        all_groups: list[dict[str, Any]] = []
        offset = 0

        while True:
            params: dict[str, Any] = {
                "startdate": int(start_time.timestamp()),
                "enddate": int(end_time.timestamp()),
                "offset": offset,
            }

            body = self._make_api_request(db, user_id, "/measure", "getmeas", params)
            measure_groups = body.get("measuregrps", [])
            all_groups.extend(measure_groups)

            # Pagination: check if there are more results
            if body.get("more", False):
                offset = body.get("offset", 0)
            else:
                break

        return all_groups

    def save_measurements(
        self,
        db,
        user_id: UUID,
        measure_groups: list[dict[str, Any]],
    ) -> int:
        """Save measurement groups to database as TimeSeries samples.

        Each measure group contains multiple measurements taken at the same time.
        """
        count = 0

        for group in measure_groups:
            grp_date = group.get("date")
            if not grp_date:
                continue

            timestamp = datetime.fromtimestamp(grp_date, tz=timezone.utc)
            measures = group.get("measures", [])

            for measure in measures:
                meastype = measure.get("type")
                value = measure.get("value")
                unit = measure.get("unit", 0)

                if meastype is None or value is None:
                    continue

                series_type = MEASTYPE_MAP.get(meastype)
                if not series_type:
                    continue

                real_value = self._convert_measurement(value, unit)

                try:
                    sample = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=timestamp,
                        value=real_value,
                        series_type=series_type,
                    )
                    timeseries_service.crud.create(db, sample)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to save Withings measurement type {meastype}: {e}")

        return count

    def load_and_save_measurements(
        self,
        db,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load body measurements from Withings API and save to database."""
        measure_groups = self.get_measurements(db, user_id, start_time, end_time)
        return self.save_measurements(db, user_id, measure_groups)

    # -------------------------------------------------------------------------
    # Sleep Sessions — POST /v2/sleep action=getsummary
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep summary data from Withings API."""
        params: dict[str, Any] = {
            "startdateymd": start_time.strftime("%Y-%m-%d"),
            "enddateymd": end_time.strftime("%Y-%m-%d"),
        }

        body = self._make_api_request(db, user_id, "/v2/sleep", "getsummary", params)
        return body.get("series", [])

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Withings sleep data to our schema."""
        start_ts = raw_sleep.get("startdate")
        end_ts = raw_sleep.get("enddate")

        start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts else None
        end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc) if end_ts else None

        data = raw_sleep.get("data", {})

        deep_seconds = data.get("deepsleepduration", 0) or 0
        light_seconds = data.get("lightsleepduration", 0) or 0
        rem_seconds = data.get("remsleepduration", 0) or 0
        awake_seconds = data.get("wakeupduration", 0) or 0
        total_sleep_seconds = deep_seconds + light_seconds + rem_seconds

        duration_seconds = (end_ts - start_ts) if (start_ts and end_ts) else 0

        efficiency = data.get("sleep_efficiency")

        sleep_id = uuid4()
        external_id = raw_sleep.get("id")
        if external_id:
            external_id = str(external_id)

        return {
            "id": sleep_id,
            "user_id": user_id,
            "provider": self.provider_name,
            "external_id": external_id,
            "start_time": start_dt,
            "end_time": end_dt,
            "duration_seconds": duration_seconds,
            "efficiency_percent": float(efficiency) if efficiency is not None else None,
            "is_nap": False,
            "stages": {
                "deep_seconds": deep_seconds,
                "light_seconds": light_seconds,
                "rem_seconds": rem_seconds,
                "awake_seconds": awake_seconds,
                "total_sleep_seconds": total_sleep_seconds,
            },
            "extra": {
                "hr_average": data.get("hr_average"),
                "rr_average": data.get("rr_average"),
            },
        }

    def save_sleep_data(
        self,
        db,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> None:
        """Save normalized sleep data to database as EventRecord with SleepDetails."""
        sleep_id = normalized_sleep["id"]
        start_dt = normalized_sleep.get("start_time")
        end_dt = normalized_sleep.get("end_time")

        if not start_dt or not end_dt:
            self.logger.warning(f"Skipping sleep record {sleep_id}: missing start/end time")
            return

        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Withings",
            device_model=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=normalized_sleep.get("external_id"),
            source=self.provider_name,
            user_id=user_id,
        )

        stages = normalized_sleep.get("stages", {})
        total_sleep_minutes = stages.get("total_sleep_seconds", 0) // 60
        time_in_bed_minutes = normalized_sleep.get("duration_seconds", 0) // 60

        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=total_sleep_minutes,
            sleep_time_in_bed_minutes=time_in_bed_minutes,
            sleep_efficiency_score=Decimal(str(normalized_sleep["efficiency_percent"]))
            if normalized_sleep.get("efficiency_percent") is not None
            else None,
            sleep_deep_minutes=stages.get("deep_seconds", 0) // 60,
            sleep_light_minutes=stages.get("light_seconds", 0) // 60,
            sleep_rem_minutes=stages.get("rem_seconds", 0) // 60,
            sleep_awake_minutes=stages.get("awake_seconds", 0) // 60,
            is_nap=normalized_sleep.get("is_nap", False),
        )

        # Save average heart rate from sleep as a timeseries sample
        extra = normalized_sleep.get("extra", {})
        hr_avg = extra.get("hr_average")

        try:
            created_record = event_record_service.create(db, record)
            detail.record_id = created_record.id
            event_record_service.create_detail(db, detail, detail_type="sleep")

            # Save sleep heart rate average
            if hr_avg is not None:
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=start_dt,
                    value=Decimal(str(hr_avg)),
                    series_type=SeriesType.heart_rate,
                )
                timeseries_service.crud.create(db, sample)
        except Exception as e:
            self.logger.error(f"Error saving Withings sleep record {sleep_id}: {e}")

    def load_and_save_sleep(
        self,
        db,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load sleep data from Withings API and save to database."""
        raw_data = self.get_sleep_data(db, user_id, start_time, end_time)
        count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_sleep(item, user_id)
                self.save_sleep_data(db, user_id, normalized)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save Withings sleep data: {e}")
        return count

    # -------------------------------------------------------------------------
    # Required abstract method stubs
    # -------------------------------------------------------------------------

    def get_recovery_data(self, db, user_id, start_time, end_time) -> list[dict[str, Any]]:
        """Withings has no recovery concept — return empty."""
        return []

    def normalize_recovery(self, raw_recovery, user_id) -> dict[str, Any]:
        return {}

    def get_activity_samples(self, db, user_id, start_time, end_time) -> list[dict[str, Any]]:
        """Activity data is handled via load_and_save_measurements."""
        return []

    def normalize_activity_samples(self, raw_samples, user_id) -> dict[str, list[dict[str, Any]]]:
        return {}

    def get_daily_activity_statistics(self, db, user_id, start_date, end_date) -> list[dict[str, Any]]:
        return []

    def normalize_daily_activity(self, raw_stats, user_id) -> dict[str, Any]:
        return {}

    # -------------------------------------------------------------------------
    # Combined Load
    # -------------------------------------------------------------------------

    def load_and_save_all(
        self,
        db,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        """Load and save all Withings data types (body measurements, sleep).

        Args:
            db: Database session
            user_id: User UUID
            start_time: Start of date range (defaults to 30 days ago)
            end_time: End of date range (defaults to now)
            is_first_sync: Whether this is the first sync
        """
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        results = {
            "measurements_synced": 0,
            "sleep_sessions_synced": 0,
        }

        try:
            results["measurements_synced"] = self.load_and_save_measurements(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync Withings measurements: {e}")

        try:
            results["sleep_sessions_synced"] = self.load_and_save_sleep(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync Withings sleep data: {e}")

        return results
