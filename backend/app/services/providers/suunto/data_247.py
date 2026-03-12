"""Suunto 247 Data implementation for sleep, recovery, and activity samples.

Syncs data from three Suunto Cloud API endpoints:
- /247samples/sleep   → EventRecord (category=sleep) + SleepDetails
- /247samples/recovery → DataPointSeries (recovery_score, resting HR, HRV, SpO2)
- /247samples/activity → DataPointSeries (HR, steps, SpO2, energy, HRV)
- /247/daily-activity-statistics → DataPointSeries (aggregated daily steps/energy)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import DataPointSeries, DataSource, EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.series_types import SeriesType
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service
from app.utils.dates import parse_datetime_or_default, parse_iso_datetime
from app.utils.structured_logging import log_structured

# ---------------------------------------------------------------------------
# Series type mappings for activity samples
# ---------------------------------------------------------------------------
_ACTIVITY_SERIES_MAP: dict[str, SeriesType] = {
    "heart_rate": SeriesType.heart_rate,
    "steps": SeriesType.steps,
    "spo2": SeriesType.oxygen_saturation,
    "energy": SeriesType.energy,
    # Suunto provides RMSSD-based HRV, map to the correct series type
    "hrv": SeriesType.heart_rate_variability_rmssd,
}

# Recovery metrics → SeriesType
# Suunto recovery endpoint provides only Balance (0.0-1.0) and StressState (0-4).
# Balance maps to recovery_score; StressState has no unified equivalent.
_RECOVERY_METRICS: list[tuple[str, SeriesType]] = [
    ("balance", SeriesType.recovery_score),
]

# Value extractors per activity-sample key
_VALUE_EXTRACTORS: dict[str, str] = {
    "heart_rate": "bpm",
    "steps": "count",
    "spo2": "percent",
    "energy": "kcal",
    "hrv": "rmssd_ms",
}

# Daily stats type → SeriesType
_DAILY_STAT_MAP: dict[str, SeriesType] = {
    "stepcount": SeriesType.steps,
    "energyconsumption": SeriesType.energy,
}


class Suunto247Data(Base247DataTemplate):
    """Suunto implementation for 247 data (sleep, recovery, activity)."""

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
        self.data_point_repo = DataPointSeriesRepository(DataPointSeries)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_suunto_headers(self) -> dict[str, str]:
        """Get Suunto-specific headers including subscription key."""
        headers: dict[str, str] = {}
        if self.oauth and hasattr(self.oauth, "credentials"):
            subscription_key = self.oauth.credentials.subscription_key
            if subscription_key:
                headers["Ocp-Apim-Subscription-Key"] = subscription_key
        return headers

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make authenticated request to Suunto API."""
        all_headers = self._get_suunto_headers()
        if headers:
            all_headers.update(headers)

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
            headers=all_headers,
        )

    @staticmethod
    def _epoch_ms(dt: datetime) -> int:
        """Convert datetime to epoch milliseconds."""
        return int(dt.timestamp() * 1000)

    def _fetch_in_chunks(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        start_time: datetime,
        end_time: datetime,
        chunk_days: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch data in chunks to stay within Suunto's 28-day API limit."""
        all_data: list[dict[str, Any]] = []
        current_start = start_time

        while current_start < end_time:
            current_end = min(current_start + timedelta(days=chunk_days), end_time)
            params = {
                "from": self._epoch_ms(current_start),
                "to": self._epoch_ms(current_end),
            }

            try:
                response = self._make_api_request(db, user_id, endpoint, params=params)
                if isinstance(response, list):
                    all_data.extend(response)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Error fetching chunk {current_start} to {current_end}: {e}",
                    provider="suunto",
                    task="fetch_in_chunks",
                )

            current_start = current_end

        return all_data

    # ------------------------------------------------------------------
    # Sleep Data — Suunto /247samples/sleep
    # ------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep data from Suunto API."""
        return self._fetch_in_chunks(db, user_id, "/247samples/sleep", start_time, end_time)

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize a single Suunto sleep entry to our internal dict format."""
        entry_data: dict[str, Any] = raw_sleep.get("entryData", {})
        timestamp = raw_sleep.get("timestamp")

        bedtime_start = entry_data.get("BedtimeStart")
        bedtime_end = entry_data.get("BedtimeEnd")

        # Suunto provides durations in seconds
        duration_seconds = int(entry_data.get("Duration", 0))
        deep_sleep = int(entry_data.get("DeepSleepDuration", 0))
        light_sleep = int(entry_data.get("LightSleepDuration", 0))
        rem_sleep = int(entry_data.get("REMSleepDuration", 0))
        awake_duration = max(0, duration_seconds - deep_sleep - light_sleep - rem_sleep)

        return {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "start_time": bedtime_start,
            "end_time": bedtime_end,
            "duration_seconds": duration_seconds,
            "efficiency_percent": entry_data.get("SleepQualityScore"),
            "is_nap": entry_data.get("IsNap", False),
            "stages": {
                "deep_seconds": deep_sleep,
                "light_seconds": light_sleep,
                "rem_seconds": rem_sleep,
                "awake_seconds": awake_duration,
            },
            "avg_heart_rate_bpm": entry_data.get("HRAvg"),
            "min_heart_rate_bpm": entry_data.get("HRMin"),
            "avg_hrv_ms": entry_data.get("AvgHRV"),
            "max_spo2_percent": entry_data.get("MaxSpo2"),
            "suunto_sleep_id": entry_data.get("SleepId"),
        }

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> None:
        """Save normalized sleep data as EventRecord + SleepDetails."""
        sleep_id: UUID = normalized_sleep["id"]

        start_dt = parse_iso_datetime(normalized_sleep.get("start_time"))
        end_dt = parse_iso_datetime(normalized_sleep.get("end_time"))

        if not start_dt or not end_dt:
            log_structured(
                self.logger,
                "warning",
                f"Skipping sleep record {sleep_id}: missing start/end time",
                provider="suunto",
                task="save_sleep_data",
            )
            return

        # EventRecord
        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Suunto",
            device_model=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=str(normalized_sleep["suunto_sleep_id"]) if normalized_sleep.get("suunto_sleep_id") else None,
            source=self.provider_name,
            user_id=user_id,
        )

        # SleepDetails
        stages = normalized_sleep.get("stages", {})
        total_sleep_seconds = (
            stages.get("deep_seconds", 0) + stages.get("light_seconds", 0) + stages.get("rem_seconds", 0)
        )
        time_in_bed_minutes = normalized_sleep.get("duration_seconds", 0) // 60

        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=total_sleep_seconds // 60,
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

        try:
            created_record = event_record_service.create(db, record)
            # Use the ID of the actually created/returned record (handles duplicates)
            detail.record_id = created_record.id
            event_record_service.create_detail(db, detail, detail_type="sleep")
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Error saving sleep record {sleep_id}: {e}",
                provider="suunto",
                task="save_sleep_data",
            )

    # ------------------------------------------------------------------
    # Recovery Data — Suunto /247samples/recovery
    # ------------------------------------------------------------------

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch recovery data from Suunto API."""
        return self._fetch_in_chunks(db, user_id, "/247samples/recovery", start_time, end_time)

    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Suunto recovery data to our schema.

        Suunto recovery provides:
        - Balance: body energy level 0.0-1.0 → scaled to 0-100 for recovery_score
        - StressState: 0-4 integer (no unified equivalent, stored for reference)
        """
        entry_data: dict[str, Any] = raw_recovery.get("entryData", {})
        timestamp = raw_recovery.get("timestamp")

        # Scale balance from 0.0-1.0 to 0-100 to match recovery_score convention
        balance_raw = entry_data.get("Balance")
        balance_scaled = float(balance_raw) * 100 if balance_raw is not None else None

        return {
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "balance": balance_scaled,
        }

    def save_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_recovery: dict[str, Any],
    ) -> int:
        """Save normalized recovery data as DataPointSeries records.

        Maps Suunto recovery fields to unified SeriesType values.
        Returns the number of samples saved.
        """
        if not normalized_recovery:
            return 0

        timestamp_raw = normalized_recovery.get("timestamp")
        if not timestamp_raw:
            return 0

        recorded_at = parse_iso_datetime(timestamp_raw) if isinstance(timestamp_raw, str) else timestamp_raw
        if not recorded_at:
            return 0

        count = 0
        for field_name, series_type in _RECOVERY_METRICS:
            value = normalized_recovery.get(field_name)
            if value is None:
                continue
            try:
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(value)),
                    series_type=series_type,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save recovery {field_name}: {e}",
                    provider="suunto",
                    task="save_recovery_data",
                )
        return count

    def load_and_save_recovery(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load recovery data from API and save to database.

        Returns total number of data point samples saved.
        """
        raw_data = self.get_recovery_data(db, user_id, start_time, end_time)
        total_count = 0

        for item in raw_data:
            try:
                normalized = self.normalize_recovery(item, user_id)
                if normalized:
                    total_count += self.save_recovery_data(db, user_id, normalized)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save recovery data: {e}",
                    provider="suunto",
                    task="load_and_save_recovery",
                )

        return total_count

    # ------------------------------------------------------------------
    # Activity Samples — Suunto /247samples/activity
    # ------------------------------------------------------------------

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch activity samples (HR, steps, SpO2, energy, HRV) from Suunto API."""
        return self._fetch_in_chunks(db, user_id, "/247samples/activity", start_time, end_time)

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize Suunto activity samples into categorized lists."""
        categorized: dict[str, list[dict[str, Any]]] = {
            "heart_rate": [],
            "steps": [],
            "spo2": [],
            "energy": [],
            "hrv": [],
        }

        for sample in raw_samples:
            timestamp = sample.get("timestamp")
            if not timestamp:
                continue
            entry_data: dict[str, Any] = sample.get("entryData", {})

            # Heart Rate
            hr = entry_data.get("HR")
            if hr is not None:
                categorized["heart_rate"].append({"timestamp": timestamp, "bpm": int(hr)})

            # Steps
            steps = entry_data.get("StepCount")
            if steps is not None:
                categorized["steps"].append({"timestamp": timestamp, "count": int(steps)})

            # SpO2 — Suunto returns 0-1 range, convert to percent
            spo2 = entry_data.get("SpO2")
            if spo2 is not None:
                percent = float(spo2) * 100 if spo2 <= 1 else float(spo2)
                categorized["spo2"].append({"timestamp": timestamp, "percent": percent})

            # Energy consumption — Suunto provides joules, convert to kcal
            energy = entry_data.get("EnergyConsumption")
            if energy is not None:
                categorized["energy"].append({"timestamp": timestamp, "kcal": float(energy) / 4184})

            # HRV (RMSSD)
            hrv = entry_data.get("HRV")
            if hrv is not None and hrv > 0:
                categorized["hrv"].append({"timestamp": timestamp, "rmssd_ms": float(hrv)})

        return categorized

    def save_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_samples: dict[str, list[dict[str, Any]]],
    ) -> int:
        """Save normalized activity samples to database using bulk_create for efficiency."""
        all_samples: list[TimeSeriesSampleCreate] = []

        for key, samples in normalized_samples.items():
            series_type = _ACTIVITY_SERIES_MAP.get(key)
            if not series_type:
                continue

            value_field = _VALUE_EXTRACTORS.get(key)
            if not value_field:
                continue

            for sample in samples:
                timestamp_str = sample.get("timestamp")
                if not timestamp_str:
                    continue

                recorded_at = parse_iso_datetime(timestamp_str)
                if not recorded_at:
                    continue

                value = sample.get(value_field)
                if value is None:
                    continue

                all_samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    ),
                )

        if all_samples:
            timeseries_service.bulk_create_samples(db, all_samples)

        return len(all_samples)

    # ------------------------------------------------------------------
    # Daily Activity Statistics — Suunto /247/daily-activity-statistics
    # ------------------------------------------------------------------

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch aggregated daily activity statistics from Suunto API.

        This endpoint uses ISO-8601 date params (not epoch ms) and lives
        under /247 rather than /247samples.
        """
        all_data: list[dict[str, Any]] = []
        current_start = start_date
        chunk_days = 14  # Conservative vs 28-day API limit

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=chunk_days), end_date)
            params = {
                "startdate": current_start.strftime("%Y-%m-%dT%H:%M:%S"),
                "enddate": current_end.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            try:
                response = self._make_api_request(db, user_id, "/247/daily-activity-statistics", params=params)
                if isinstance(response, list):
                    all_data.extend(response)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Error fetching daily activity chunk {current_start} to {current_end}: {e}",
                    provider="suunto",
                    task="get_daily_activity_statistics",
                )

            current_start = current_end

        return all_data

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Suunto daily activity statistics.

        Suunto returns data grouped by type (stepcount / energyconsumption) with sources.
        """
        stat_name: str | None = raw_stats.get("Name")
        sources: list[dict[str, Any]] = raw_stats.get("Sources", [])

        daily_values: list[dict[str, Any]] = []
        for source in sources:
            for sample in source.get("Samples", []):
                value = sample.get("Value")
                time_iso = sample.get("TimeISO8601")
                if value is not None and time_iso is not None:
                    daily_values.append({"date": time_iso, "value": value})

        return {"type": stat_name, "daily_values": daily_values}

    def save_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_stats: list[dict[str, Any]],
    ) -> int:
        """Save daily activity statistics as DataPointSeries (bulk)."""
        all_samples: list[TimeSeriesSampleCreate] = []

        for stat in normalized_stats:
            series_type = _DAILY_STAT_MAP.get(stat.get("type", ""))
            if not series_type:
                continue

            for item in stat.get("daily_values", []):
                date_str = item.get("date")
                value = item.get("value")
                if not date_str or value is None:
                    continue

                recorded_at = parse_iso_datetime(date_str)
                if not recorded_at:
                    continue

                final_value = Decimal(str(value))
                # Suunto provides energy in joules — convert to kcal
                if series_type == SeriesType.energy:
                    final_value = final_value / Decimal("4184")

                all_samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        value=final_value,
                        series_type=series_type,
                    ),
                )

        if all_samples:
            timeseries_service.bulk_create_samples(db, all_samples)

        return len(all_samples)

    # ------------------------------------------------------------------
    # Orchestration — load + save all data types
    # ------------------------------------------------------------------

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
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save sleep data: {e}",
                    provider="suunto",
                    task="load_and_save_sleep",
                )
        return count

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        """Load all 247 data types and save to database."""
        now = datetime.now()
        end_dt = parse_datetime_or_default(end_time, now)
        start_dt = parse_datetime_or_default(start_time, end_dt - timedelta(days=28))

        results: dict[str, int] = {
            "sleep_sessions_synced": 0,
            "recovery_samples_synced": 0,
            "activity_samples_synced": 0,
            "daily_activity_synced": 0,
        }

        # 1. Sleep sessions → EventRecord + SleepDetails
        try:
            results["sleep_sessions_synced"] = self.load_and_save_sleep(db, user_id, start_dt, end_dt)
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Failed to sync sleep data: {e}",
                provider="suunto",
                task="load_and_save_all",
            )

        # 2. Recovery → DataPointSeries (recovery_score, resting HR, HRV, …)
        try:
            results["recovery_samples_synced"] = self.load_and_save_recovery(db, user_id, start_dt, end_dt)
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Failed to sync recovery data: {e}",
                provider="suunto",
                task="load_and_save_all",
            )

        # 3. Activity samples → DataPointSeries (HR, steps, SpO2, energy, HRV)
        try:
            raw_activity = self.get_activity_samples(db, user_id, start_dt, end_dt)
            normalized_activity = self.normalize_activity_samples(raw_activity, user_id)
            results["activity_samples_synced"] = self.save_activity_samples(db, user_id, normalized_activity)
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Failed to sync activity samples: {e}",
                provider="suunto",
                task="load_and_save_all",
            )

        # 4. Daily aggregated statistics → DataPointSeries (steps, energy)
        try:
            raw_daily = self.get_daily_activity_statistics(db, user_id, start_dt, end_dt)
            normalized_daily = [self.normalize_daily_activity(item, user_id) for item in raw_daily]
            results["daily_activity_synced"] = self.save_daily_activity_statistics(db, user_id, normalized_daily)
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Failed to sync daily activity statistics: {e}",
                provider="suunto",
                task="load_and_save_all",
            )

        return results
