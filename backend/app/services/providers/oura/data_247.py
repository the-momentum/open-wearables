"""Oura Ring 247 Data implementation for sleep, readiness, activity, and SpO2."""

from contextlib import suppress
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.database import DbSession
from app.models import DataSource, EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.series_types import SeriesType
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service


class Oura247Data(Base247DataTemplate):
    """Oura Ring implementation for 247 data (sleep, readiness, activity, SpO2)."""

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ) -> None:
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
        """Make authenticated request to Oura API."""
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

    def _paginate(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch all pages from an Oura list endpoint using next_token pagination.

        Oura list endpoints return: {"data": [...], "next_token": "..."}
        """
        all_records: list[dict[str, Any]] = []

        while True:
            try:
                response = self._make_api_request(db, user_id, endpoint, params=params)
                records = response.get("data", []) if isinstance(response, dict) else []
                all_records.extend(records)

                next_token = response.get("next_token") if isinstance(response, dict) else None
                if not records or not next_token:
                    break

                # Oura uses next_token as a query param for the next page
                params = dict(params)
                params["next_token"] = next_token

            except Exception as e:
                self.logger.error(f"Error fetching {endpoint}: {e}")
                if all_records:
                    self.logger.warning(f"Returning partial data from {endpoint} due to error: {e}")
                    break
                raise

        return all_records

    # -------------------------------------------------------------------------
    # Sleep Sessions — /v2/usercollection/sleep
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep sessions from Oura API with pagination."""
        params: dict[str, Any] = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/sleep", params)

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Oura sleep data to our schema."""
        sleep_id_str = raw_sleep.get("id")
        bedtime_start = raw_sleep.get("bedtime_start")
        bedtime_end = raw_sleep.get("bedtime_end")
        sleep_type = raw_sleep.get("type", "")
        is_nap = sleep_type not in ("long_sleep",)

        # Durations are in seconds (Oura native unit — no conversion needed)
        time_in_bed = raw_sleep.get("time_in_bed", 0) or 0
        total_sleep_duration = raw_sleep.get("total_sleep_duration", 0) or 0
        deep_sleep = raw_sleep.get("deep_sleep_duration", 0) or 0
        light_sleep = raw_sleep.get("light_sleep_duration", 0) or 0
        rem_sleep = raw_sleep.get("rem_sleep_duration", 0) or 0
        awake_duration = raw_sleep.get("awake_duration", 0) or 0

        efficiency = raw_sleep.get("efficiency")

        # Generate a stable UUID from the Oura ID
        internal_id = uuid4()
        if sleep_id_str:
            with suppress(ValueError, TypeError):
                internal_id = UUID(sleep_id_str)

        return {
            "id": internal_id,
            "user_id": user_id,
            "provider": self.provider_name,
            "external_id": sleep_id_str,
            "start_time": bedtime_start,
            "end_time": bedtime_end,
            "duration_seconds": time_in_bed,
            "efficiency_percent": float(efficiency) if efficiency is not None else None,
            "is_nap": is_nap,
            "stages": {
                "deep_seconds": deep_sleep,
                "light_seconds": light_sleep,
                "rem_seconds": rem_sleep,
                "awake_seconds": awake_duration,
                "total_sleep_seconds": total_sleep_duration,
            },
            "raw": raw_sleep,
        }

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> bool:
        """Save normalized sleep data to database as EventRecord with SleepDetails.

        Returns True if the record was saved successfully, False otherwise.
        """
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
            return False

        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Oura Ring",
            device_model=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=str(normalized_sleep.get("external_id")) if normalized_sleep.get("external_id") else None,
            source=self.provider_name,
            user_id=user_id,
        )

        stages = normalized_sleep.get("stages", {})
        total_sleep_seconds = stages.get("total_sleep_seconds", 0)
        total_sleep_minutes = total_sleep_seconds // 60
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
            created_record = event_record_service.create(db, record)
            detail.record_id = created_record.id
            event_record_service.create_detail(db, detail, detail_type="sleep")
            return True
        except Exception as e:
            self.logger.error(f"Error saving sleep record {sleep_id}: {e}")
            return False

    def load_and_save_sleep(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load sleep data from Oura API and save to database."""
        raw_data = self.get_sleep_data(db, user_id, start_time, end_time)
        count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_sleep(item, user_id)
                if self.save_sleep_data(db, user_id, normalized):
                    count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save sleep data: {e}")
        return count

    # -------------------------------------------------------------------------
    # Daily Readiness — /v2/usercollection/daily_readiness
    # -------------------------------------------------------------------------

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily readiness data from Oura API with pagination."""
        params: dict[str, Any] = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/daily_readiness", params)

    def normalize_recovery(
        self,
        raw_readiness: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Oura readiness data to our schema."""
        timestamp_str = raw_readiness.get("timestamp")
        timestamp = None
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                self.logger.warning(f"Skipping readiness record with malformed timestamp: {timestamp_str}")
                timestamp = None

        return {
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "score": raw_readiness.get("score"),
            "temperature_deviation": raw_readiness.get("temperature_deviation"),
        }

    def save_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_readiness: dict[str, Any],
    ) -> int:
        """Save normalized readiness data to database as DataPointSeries.

        Saves:
        - score → SeriesType.recovery_score
        - temperature_deviation → SeriesType.body_temperature (skip if 0)

        Returns the number of samples saved.
        """
        if not normalized_readiness:
            return 0

        timestamp = normalized_readiness.get("timestamp")
        if not timestamp:
            return 0

        count = 0

        # Recovery score
        score = normalized_readiness.get("score")
        if score is not None:
            try:
                sample = TimeSeriesSampleCreate(
                    id=uuid5(NAMESPACE_URL, f"oura:recovery_score:{user_id}:{timestamp.isoformat()}"),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=timestamp,
                    value=Decimal(str(score)),
                    series_type=SeriesType.recovery_score,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save readiness score: {e}")

        # Temperature deviation (skip if 0 or None)
        temp_deviation = normalized_readiness.get("temperature_deviation")
        if temp_deviation is not None and temp_deviation != 0:
            try:
                sample = TimeSeriesSampleCreate(
                    id=uuid5(NAMESPACE_URL, f"oura:body_temperature:{user_id}:{timestamp.isoformat()}"),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=timestamp,
                    value=Decimal(str(temp_deviation)),
                    series_type=SeriesType.body_temperature,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save temperature deviation: {e}")

        return count

    def load_and_save_recovery(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load daily readiness from Oura API and save to database."""
        raw_data = self.get_recovery_data(db, user_id, start_time, end_time)
        total_count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_recovery(item, user_id)
                if normalized:
                    total_count += self.save_recovery_data(db, user_id, normalized)
            except Exception as e:
                self.logger.warning(f"Failed to save readiness data: {e}")
        return total_count

    # -------------------------------------------------------------------------
    # Daily Activity — /v2/usercollection/daily_activity
    # -------------------------------------------------------------------------

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily activity data from Oura API with pagination."""
        params: dict[str, Any] = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/daily_activity", params)

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize activity samples — not used directly; save handled separately."""
        return {}

    def save_activity_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_activity: dict[str, Any],
    ) -> int:
        """Save activity record to database as DataPointSeries.

        Saves:
        - steps → SeriesType.steps
        - active_calories → SeriesType.energy
        - total_calories → SeriesType.basal_energy

        Returns the number of samples saved.
        """
        timestamp_str = raw_activity.get("timestamp")
        if not timestamp_str:
            # Fall back to day string
            day_str = raw_activity.get("day")
            if day_str:
                timestamp_str = f"{day_str}T00:00:00+00:00"

        if not timestamp_str:
            return 0

        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return 0

        count = 0
        metrics = [
            ("steps", SeriesType.steps),
            ("active_calories", SeriesType.energy),
            ("total_calories", SeriesType.basal_energy),
        ]

        for field_name, series_type in metrics:
            value = raw_activity.get(field_name)
            if value is not None:
                try:
                    sample = TimeSeriesSampleCreate(
                        id=uuid5(NAMESPACE_URL, f"oura:{field_name}:{user_id}:{timestamp.isoformat()}"),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=timestamp,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                    timeseries_service.crud.create(db, sample)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to save activity {field_name}: {e}")

        return count

    def load_and_save_activity(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load daily activity from Oura API and save to database."""
        raw_data = self.get_activity_samples(db, user_id, start_time, end_time)
        total_count = 0
        for item in raw_data:
            try:
                total_count += self.save_activity_data(db, user_id, item)
            except Exception as e:
                self.logger.warning(f"Failed to save activity data: {e}")
        return total_count

    # -------------------------------------------------------------------------
    # Daily SpO2 — /v2/usercollection/daily_spo2
    # -------------------------------------------------------------------------

    def get_spo2_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily SpO2 data from Oura API with pagination."""
        params: dict[str, Any] = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/daily_spo2", params)

    def save_spo2_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_spo2: dict[str, Any],
    ) -> int:
        """Save SpO2 record to database as DataPointSeries.

        Saves:
        - spo2_percentage.average → SeriesType.oxygen_saturation
        - breathing_disturbance_index → SeriesType.sleeping_breathing_disturbances

        Returns the number of samples saved.
        """
        day_str = raw_spo2.get("day")
        if not day_str:
            return 0

        try:
            timestamp = datetime.fromisoformat(f"{day_str}T00:00:00+00:00")
        except (ValueError, AttributeError):
            return 0

        count = 0

        # SpO2 average
        spo2_percentage = raw_spo2.get("spo2_percentage") or {}
        spo2_avg = spo2_percentage.get("average") if isinstance(spo2_percentage, dict) else None
        if spo2_avg is not None:
            try:
                sample = TimeSeriesSampleCreate(
                    id=uuid5(NAMESPACE_URL, f"oura:oxygen_saturation:{user_id}:{timestamp.isoformat()}"),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=timestamp,
                    value=Decimal(str(spo2_avg)),
                    series_type=SeriesType.oxygen_saturation,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save SpO2 average: {e}")

        # Breathing disturbance index
        bdi = raw_spo2.get("breathing_disturbance_index")
        if bdi is not None:
            try:
                sample = TimeSeriesSampleCreate(
                    id=uuid5(NAMESPACE_URL, f"oura:breathing_disturbance:{user_id}:{timestamp.isoformat()}"),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=timestamp,
                    value=Decimal(str(bdi)),
                    series_type=SeriesType.sleeping_breathing_disturbances,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save breathing disturbance index: {e}")

        return count

    def load_and_save_spo2(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load daily SpO2 from Oura API and save to database."""
        raw_data = self.get_spo2_data(db, user_id, start_time, end_time)
        total_count = 0
        for item in raw_data:
            try:
                total_count += self.save_spo2_data(db, user_id, item)
            except Exception as e:
                self.logger.warning(f"Failed to save SpO2 data: {e}")
        return total_count

    # -------------------------------------------------------------------------
    # Heart Rate (optional) — /v2/usercollection/heartrate
    # -------------------------------------------------------------------------

    def get_heart_rate_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch heart rate data from Oura API. Uses ISO8601 datetime params."""
        start_iso = start_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        params: dict[str, Any] = {
            "start_datetime": start_iso,
            "end_datetime": end_iso,
        }
        return self._paginate(db, user_id, "/v2/usercollection/heartrate", params)

    def save_heart_rate_data(
        self,
        db: DbSession,
        user_id: UUID,
        records: list[dict[str, Any]],
    ) -> int:
        """Save heart rate records to database as DataPointSeries."""
        count = 0
        for record in records:
            bpm = record.get("bpm")
            timestamp_str = record.get("timestamp")
            if bpm is None or not timestamp_str:
                continue
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                sample = TimeSeriesSampleCreate(
                    id=uuid5(NAMESPACE_URL, f"oura:heart_rate:{user_id}:{timestamp.isoformat()}"),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=timestamp,
                    value=Decimal(str(bpm)),
                    series_type=SeriesType.heart_rate,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save heart rate record: {e}")
        return count

    def load_and_save_heart_rate(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load heart rate data from Oura API and save to database.

        Only syncs the last 24h to avoid overwhelming the database.
        """
        # Clamp to last 24h max
        clamped_start = max(start_time, end_time - timedelta(hours=24))
        try:
            raw_data = self.get_heart_rate_data(db, user_id, clamped_start, end_time)
            return self.save_heart_rate_data(db, user_id, raw_data)
        except Exception as e:
            self.logger.error(f"Failed to sync heart rate data: {e}")
            return 0

    # -------------------------------------------------------------------------
    # Required abstract method stubs (not used directly for Oura)
    # -------------------------------------------------------------------------

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Not used directly — activity data is handled by load_and_save_activity."""
        return []

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Not used directly — activity data is handled by save_activity_data."""
        return {}

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
        """Load and save all Oura data types (sleep, readiness, activity, SpO2, heart rate).

        Args:
            db: Database session
            user_id: User UUID
            start_time: Start of date range (defaults to 30 days ago)
            end_time: End of date range (defaults to now)
            is_first_sync: Whether this is the first sync (accepted for API compatibility)
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

        results = {
            "sleep_sessions_synced": 0,
            "recovery_samples_synced": 0,
            "activity_samples_synced": 0,
            "spo2_samples_synced": 0,
            "heart_rate_samples_synced": 0,
        }

        try:
            results["sleep_sessions_synced"] = self.load_and_save_sleep(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync Oura sleep data: {e}")

        try:
            results["recovery_samples_synced"] = self.load_and_save_recovery(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync Oura readiness data: {e}")

        try:
            results["activity_samples_synced"] = self.load_and_save_activity(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync Oura activity data: {e}")

        try:
            results["spo2_samples_synced"] = self.load_and_save_spo2(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync Oura SpO2 data: {e}")

        try:
            results["heart_rate_samples_synced"] = self.load_and_save_heart_rate(
                db, user_id, start_time, end_time
            )
        except Exception as e:
            self.logger.error(f"Failed to sync Oura heart rate data: {e}")

        return results
