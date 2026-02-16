"""Whoop 247 Data implementation for sleep, recovery, and activity samples."""

from contextlib import suppress
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import DataPointSeries, DataSource, EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.series_types import SeriesType, get_series_type_id
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service


class Whoop247Data(Base247DataTemplate):
    """Whoop implementation for 247 data (sleep, recovery, activity)."""

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

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make authenticated request to Whoop API."""
        print(f"Making API request to {endpoint} with params: {params}")
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
    # Sleep Data - Whoop /v2/activity/sleep
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep data from Whoop API via v2 endpoint with pagination."""
        all_sleep_data = []
        next_token = None
        max_limit = 25  # Whoop API limit

        # Convert datetimes to ISO 8601 strings
        start_iso = start_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        while True:
            params: dict[str, Any] = {
                "start": start_iso,
                "end": end_iso,
                "limit": max_limit,
            }

            if next_token:
                params["nextToken"] = next_token

            try:
                response = self._make_api_request(db, user_id, "/v2/activity/sleep", params=params)

                # Extract records from response
                records = response.get("records", []) if isinstance(response, dict) else []
                all_sleep_data.extend(records)

                # Check for next page
                next_token = response.get("next_token") if isinstance(response, dict) else None

                # Stop if no more records or no next token
                if not records or not next_token:
                    break

            except Exception as e:
                self.logger.error(f"Error fetching Whoop sleep data: {e}")
                # If we got some data, return what we have; otherwise re-raise
                if all_sleep_data:
                    self.logger.warning(f"Returning partial sleep data due to error: {e}")
                    break
                raise

        return all_sleep_data

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Whoop sleep data to our schema."""
        # Extract basic fields
        sleep_id = raw_sleep.get("id")
        start_time = raw_sleep.get("start")
        end_time = raw_sleep.get("end")
        nap = raw_sleep.get("nap", False)
        cycle_id = raw_sleep.get("cycle_id")

        # Extract score data (may be None if not scored yet)
        score = raw_sleep.get("score", {}) or {}
        stage_summary = score.get("stage_summary", {}) or {}

        # Time conversions: Whoop provides durations in milliseconds
        # Convert to seconds for our schema
        total_in_bed_ms = stage_summary.get("total_in_bed_time_milli", 0)
        total_awake_ms = stage_summary.get("total_awake_time_milli", 0)
        total_light_ms = stage_summary.get("total_light_sleep_time_milli", 0)
        total_slow_wave_ms = stage_summary.get("total_slow_wave_sleep_time_milli", 0)
        total_rem_ms = stage_summary.get("total_rem_sleep_time_milli", 0)

        # Convert milliseconds to seconds
        duration_seconds = int(total_in_bed_ms / 1000) if total_in_bed_ms else 0
        deep_seconds = int(total_slow_wave_ms / 1000) if total_slow_wave_ms else 0
        light_seconds = int(total_light_ms / 1000) if total_light_ms else 0
        rem_seconds = int(total_rem_ms / 1000) if total_rem_ms else 0
        awake_seconds = int(total_awake_ms / 1000) if total_awake_ms else 0

        # If duration is 0 but we have start/end times, calculate from timestamps
        if duration_seconds == 0 and start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                duration_seconds = int((end_dt - start_dt).total_seconds())
            except (ValueError, AttributeError):
                pass

        # Efficiency percentage
        efficiency = score.get("sleep_efficiency_percentage")

        # Generate UUID for our internal ID (use Whoop ID if it's a valid UUID string)
        internal_id = uuid4()
        if sleep_id:
            with suppress(ValueError, TypeError):
                internal_id = UUID(sleep_id)

        return {
            "id": internal_id,
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": start_time or end_time,
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration_seconds,
            "efficiency_percent": float(efficiency) if efficiency is not None else None,
            "is_nap": nap,
            "stages": {
                "deep_seconds": deep_seconds,
                "light_seconds": light_seconds,
                "rem_seconds": rem_seconds,
                "awake_seconds": awake_seconds,
            },
            "whoop_sleep_id": sleep_id,
            "whoop_cycle_id": cycle_id,
            "raw": raw_sleep,  # Keep raw for debugging
        }

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> None:
        """Save normalized sleep data to database as EventRecord with SleepDetails."""
        sleep_id = normalized_sleep["id"]

        # Parse start and end times
        start_dt = None
        end_dt = None
        if normalized_sleep.get("start_time"):
            start_time = normalized_sleep["start_time"]
            if isinstance(start_time, str):
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            elif isinstance(start_time, datetime):
                start_dt = start_time

        if normalized_sleep.get("end_time"):
            end_time = normalized_sleep["end_time"]
            if isinstance(end_time, str):
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            elif isinstance(end_time, datetime):
                end_dt = end_time

        if not start_dt or not end_dt:
            self.logger.warning(f"Skipping sleep record {sleep_id}: missing start/end time")
            return

        # Create EventRecord for sleep
        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Whoop",
            device_model=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=str(normalized_sleep.get("whoop_sleep_id")) if normalized_sleep.get("whoop_sleep_id") else None,
            source=self.provider_name,
            user_id=user_id,
        )

        # Create detail with sleep-specific fields
        stages = normalized_sleep.get("stages", {})
        # Calculate total sleep time (deep + light + REM)
        total_sleep_seconds = (
            stages.get("deep_seconds", 0) + stages.get("light_seconds", 0) + stages.get("rem_seconds", 0)
        )
        total_sleep_minutes = total_sleep_seconds // 60

        # Time in bed (total duration)
        time_in_bed_minutes = normalized_sleep.get("duration_seconds", 0) // 60

        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=total_sleep_minutes,
            sleep_time_in_bed_minutes=time_in_bed_minutes,
            sleep_efficiency_score=Decimal(str(normalized_sleep.get("efficiency_percent", 0)))
            if normalized_sleep.get("efficiency_percent") is not None
            else None,
            sleep_deep_minutes=stages.get("deep_seconds", 0) // 60,
            sleep_light_minutes=stages.get("light_seconds", 0) // 60,
            sleep_rem_minutes=stages.get("rem_seconds", 0) // 60,
            sleep_awake_minutes=stages.get("awake_seconds", 0) // 60,
            is_nap=normalized_sleep.get("is_nap", False),
        )

        try:
            # Create record first
            created_record = event_record_service.create(db, record)

            # Ensure we use the ID of the actually created/retrieved record
            # This handles the case where an existing record was returned
            detail.record_id = created_record.id

            # Create detail
            event_record_service.create_detail(db, detail, detail_type="sleep")
        except Exception as e:
            self.logger.error(f"Error saving sleep record {sleep_id}: {e}")
            # Rollback is handled by the service/repository or session manager
            # But we should ensure we don't break the entire sync loop
            pass

    def load_and_save_sleep(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load sleep data from API and save to database."""
        raw_data = self.get_sleep_data(db, user_id, start_time, end_time)
        count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_sleep(item, user_id)
                self.save_sleep_data(db, user_id, normalized)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save sleep data: {e}")
        return count

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        """Load and save all 247 data types (sleep, recovery, activity).

        Args:
            db: Database session
            user_id: User UUID
            start_time: Start of date range (defaults to 30 days ago)
            end_time: End of date range (defaults to now)
            is_first_sync: Whether this is the first sync (unused, for API compatibility)
        """
        # Handle date defaults (last 30 days if not specified)
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        if not start_time:
            start_time = datetime.now() - timedelta(days=30)
        if not end_time:
            end_time = datetime.now()

        results = {
            "sleep_sessions_synced": 0,
            "recovery_samples_synced": 0,
            "activity_samples_synced": 0,
            "body_measurement_samples_synced": 0,
        }

        try:
            results["sleep_sessions_synced"] = self.load_and_save_sleep(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync sleep data: {e}")

        try:
            results["recovery_samples_synced"] = self.load_and_save_recovery(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync recovery data: {e}")

        try:
            results["body_measurement_samples_synced"] = self.load_and_save_body_measurement(db, user_id)
        except Exception as e:
            self.logger.error(f"Failed to sync body measurement data: {e}")

        return results

    # -------------------------------------------------------------------------
    # Body Measurement Data (Height/Weight)
    # -------------------------------------------------------------------------

    def get_body_measurement(
        self,
        db: DbSession,
        user_id: UUID,
    ) -> dict[str, Any]:
        """Fetch body measurements from Whoop API.

        Returns height_meter, weight_kilogram, and max_heart_rate.
        See: https://developer.whoop.com/api/#tag/Body-Measurement
        """
        try:
            response = self._make_api_request(db, user_id, "/v2/user/measurement/body")
            return response if isinstance(response, dict) else {}
        except Exception as e:
            self.logger.error(f"Error fetching Whoop body measurement: {e}")
            return {}

    def _get_latest_value(
        self,
        db: DbSession,
        user_id: UUID,
        series_type: SeriesType,
    ) -> Decimal | None:
        """Get the most recent value for a series type for this user/provider."""
        type_id = get_series_type_id(series_type)
        result = (
            db.query(DataPointSeries.value)
            .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                DataSource.source == self.provider_name,
                DataPointSeries.series_type_definition_id == type_id,
            )
            .order_by(DataPointSeries.recorded_at.desc())
            .first()
        )
        return result[0] if result else None

    def load_and_save_body_measurement(
        self,
        db: DbSession,
        user_id: UUID,
    ) -> int:
        """Fetch body measurements and save height/weight to data_point_series.

        Only saves if the value has changed from the most recent entry.
        Returns the number of samples saved.
        """
        body = self.get_body_measurement(db, user_id)
        if not body:
            return 0

        count = 0
        recorded_at = datetime.now(timezone.utc)

        # Save height (convert meters to centimeters) if changed
        height_meter = body.get("height_meter")
        if height_meter is not None:
            try:
                height_cm = Decimal(str(height_meter)) * 100
                latest_height = self._get_latest_value(db, user_id, SeriesType.height)

                if latest_height is None or abs(latest_height - height_cm) > Decimal("0.01"):
                    sample = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        value=height_cm,
                        series_type=SeriesType.height,
                    )
                    timeseries_service.crud.create(db, sample)
                    count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save height data: {e}")

        # Save weight (already in kilograms) if changed
        weight_kg = body.get("weight_kilogram")
        if weight_kg is not None:
            try:
                weight = Decimal(str(weight_kg))
                latest_weight = self._get_latest_value(db, user_id, SeriesType.weight)

                if latest_weight is None or abs(latest_weight - weight) > Decimal("0.01"):
                    sample = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        value=weight,
                        series_type=SeriesType.weight,
                    )
                    timeseries_service.crud.create(db, sample)
                    count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save weight data: {e}")

        return count

    # -------------------------------------------------------------------------
    # Recovery Data
    # -------------------------------------------------------------------------

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch recovery data from Whoop API via v2 endpoint with pagination.

        Returns list of recovery records containing recovery_score, resting_heart_rate,
        hrv_rmssd_milli, spo2_percentage, and skin_temp_celsius.
        """
        all_recovery_data = []
        next_token = None
        max_limit = 25  # Whoop API limit

        # Convert datetimes to ISO 8601 strings
        start_iso = start_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        while True:
            params: dict[str, Any] = {
                "start": start_iso,
                "end": end_iso,
                "limit": max_limit,
            }

            if next_token:
                params["nextToken"] = next_token

            try:
                response = self._make_api_request(db, user_id, "/v2/recovery", params=params)

                # Extract records from response
                records = response.get("records", []) if isinstance(response, dict) else []
                all_recovery_data.extend(records)

                # Check for next page
                next_token = response.get("next_token") if isinstance(response, dict) else None

                # Stop if no more records or no next token
                if not records or not next_token:
                    break

            except Exception as e:
                self.logger.error(f"Error fetching Whoop recovery data: {e}")
                # If we got some data, return what we have; otherwise re-raise
                if all_recovery_data:
                    self.logger.warning(f"Returning partial recovery data due to error: {e}")
                    break
                raise

        return all_recovery_data

    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Whoop recovery data to our schema.

        Extracts recovery metrics from the score object:
        - recovery_score (0-100)
        - resting_heart_rate (bpm)
        - hrv_rmssd_milli (ms)
        - spo2_percentage (%)
        - skin_temp_celsius (°C)
        """
        cycle_id = raw_recovery.get("cycle_id")
        sleep_id = raw_recovery.get("sleep_id")
        created_at = raw_recovery.get("created_at")
        score_state = raw_recovery.get("score_state")

        # Extract score data (may be None if not scored yet)
        score = raw_recovery.get("score", {}) or {}

        # Only process scored records
        if score_state != "SCORED":
            return {}

        # Parse timestamp
        timestamp = None
        if created_at:
            try:
                timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

        return {
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "cycle_id": cycle_id,
            "sleep_id": sleep_id,
            "recovery_score": score.get("recovery_score"),
            "resting_heart_rate": score.get("resting_heart_rate"),
            "hrv_rmssd_milli": score.get("hrv_rmssd_milli"),
            "spo2_percentage": score.get("spo2_percentage"),
            "skin_temp_celsius": score.get("skin_temp_celsius"),
            "raw": raw_recovery,
        }

    def save_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_recovery: dict[str, Any],
    ) -> int:
        """Save normalized recovery data to database as DataPointSeries.

        Saves up to 5 metrics per recovery record:
        - recovery_score
        - resting_heart_rate
        - heart_rate_variability_rmssd (from hrv_rmssd_milli)
        - oxygen_saturation (from spo2_percentage)
        - skin_temperature (from skin_temp_celsius)

        Returns the number of samples saved.
        """
        if not normalized_recovery:
            return 0

        timestamp = normalized_recovery.get("timestamp")
        if not timestamp:
            return 0

        count = 0

        # Map WHOOP fields to SeriesType
        metrics = [
            ("recovery_score", SeriesType.recovery_score),
            ("resting_heart_rate", SeriesType.resting_heart_rate),
            ("hrv_rmssd_milli", SeriesType.heart_rate_variability_rmssd),
            ("spo2_percentage", SeriesType.oxygen_saturation),
            ("skin_temp_celsius", SeriesType.skin_temperature),
        ]

        for field_name, series_type in metrics:
            value = normalized_recovery.get(field_name)
            if value is not None:
                try:
                    sample = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=timestamp,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                    timeseries_service.crud.create(db, sample)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to save recovery {field_name}: {e}")

        return count

    def load_and_save_recovery(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load recovery data from API and save to database.

        Returns the total number of data point samples saved.
        """
        raw_data = self.get_recovery_data(db, user_id, start_time, end_time)
        total_count = 0

        for item in raw_data:
            try:
                normalized = self.normalize_recovery(item, user_id)
                if normalized:  # Skip unscored records
                    total_count += self.save_recovery_data(db, user_id, normalized)
            except Exception as e:
                self.logger.warning(f"Failed to save recovery data: {e}")

        return total_count

    # -------------------------------------------------------------------------
    # Activity Samples
    # -------------------------------------------------------------------------

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch activity samples from Whoop API."""
        return []

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize activity samples into categorized data."""
        return {}

    # -------------------------------------------------------------------------
    # Daily Activity Statistics
    # -------------------------------------------------------------------------

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch aggregated daily activity statistics."""
        return []

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize daily activity statistics to our schema."""
        return {}
