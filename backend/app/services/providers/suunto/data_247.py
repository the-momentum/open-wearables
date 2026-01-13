"""Suunto 247 Data implementation for sleep, recovery, and activity samples."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import DataPointSeries, EventRecord, ExternalDeviceMapping
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.repositories.external_mapping_repository import ExternalMappingRepository
from app.schemas import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.series_types import SeriesType
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class Suunto247Data(Base247DataTemplate):
    """Suunto implementation for 247 data (sleep, recovery, activity)."""

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ):
        super().__init__(provider_name, api_base_url, oauth)
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)
        self.connection_repo = UserConnectionRepository()
        self.data_point_repo = DataPointSeriesRepository(DataPointSeries)

    def _get_suunto_headers(self) -> dict[str, str]:
        """Get Suunto-specific headers including subscription key."""
        headers = {}
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

    def _epoch_ms(self, dt: datetime) -> int:
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
        """Fetch data in chunks to avoid 28-day limit."""
        all_data = []
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
                # Log error but continue with other chunks if possible
                # In a real scenario, we might want to re-raise or handle differently
                print(f"Error fetching chunk {current_start} to {current_end}: {e}")

            current_start = current_end

        return all_data

    # -------------------------------------------------------------------------
    # Sleep Data - Suunto /247samples/sleep
    # -------------------------------------------------------------------------

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
        """Normalize Suunto sleep data to our schema."""
        entry_data = raw_sleep.get("entryData", {})
        timestamp = raw_sleep.get("timestamp")

        # Parse bedtime times
        bedtime_start = entry_data.get("BedtimeStart")
        bedtime_end = entry_data.get("BedtimeEnd")

        # Calculate duration in seconds
        duration_seconds = int(entry_data.get("Duration", 0))

        # Sleep stages in seconds (Suunto provides in some unit, assuming seconds/minutes)
        deep_sleep = int(entry_data.get("DeepSleepDuration", 0))
        light_sleep = int(entry_data.get("LightSleepDuration", 0))
        rem_sleep = int(entry_data.get("REMSleepDuration", 0))

        # Calculate awake time
        total_in_bed = duration_seconds
        total_sleep = deep_sleep + light_sleep + rem_sleep
        awake_duration = max(0, total_in_bed - total_sleep)

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
            "feeling": entry_data.get("Feeling"),
            "suunto_sleep_id": entry_data.get("SleepId"),
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
            start_dt = datetime.fromisoformat(normalized_sleep["start_time"].replace("Z", "+00:00"))
        if normalized_sleep.get("end_time"):
            end_dt = datetime.fromisoformat(normalized_sleep["end_time"].replace("Z", "+00:00"))

        if not start_dt or not end_dt:
            return

        # Create EventRecord for sleep
        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Suunto",
            device_id=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=str(normalized_sleep.get("suunto_sleep_id"))
            if normalized_sleep.get("suunto_sleep_id")
            else None,
            provider_name=self.provider_name,  # For external mapping
            user_id=user_id,
        )

        # Create detail with sleep-specific fields
        stages = normalized_sleep.get("stages", {})
        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=normalized_sleep.get("duration_seconds", 0) // 60,
            sleep_efficiency_score=Decimal(str(normalized_sleep.get("efficiency_percent", 0)))
            if normalized_sleep.get("efficiency_percent")
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

    # -------------------------------------------------------------------------
    # Recovery Data - Suunto /247samples/recovery
    # -------------------------------------------------------------------------

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
        """Normalize Suunto recovery data to our schema."""
        entry_data = raw_recovery.get("entryData", {})
        timestamp = raw_recovery.get("timestamp")

        return {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "balance": entry_data.get("Balance"),
            "stress_state": entry_data.get("StressState"),
            "raw": raw_recovery,
        }

    # -------------------------------------------------------------------------
    # Activity Samples - Suunto /247samples/activity
    # -------------------------------------------------------------------------

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch activity samples (HR, steps, SpO2) from Suunto API."""
        return self._fetch_in_chunks(db, user_id, "/247samples/activity", start_time, end_time)

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize Suunto activity samples into categorized data."""
        heart_rate_samples = []
        step_samples = []
        spo2_samples = []
        energy_samples = []
        hrv_samples = []

        for sample in raw_samples:
            timestamp = sample.get("timestamp")
            entry_data = sample.get("entryData", {})

            # Heart Rate
            hr = entry_data.get("HR")
            if hr is not None:
                heart_rate_samples.append(
                    {
                        "timestamp": timestamp,
                        "bpm": int(hr),
                        "context": "active",  # Suunto 247 is continuous monitoring
                    },
                )

            # HR extended (min/max)
            hr_ext = entry_data.get("HRExt", {})
            if hr_ext:
                # Could store min/max separately if needed
                pass

            # Steps
            steps = entry_data.get("StepCount")
            if steps is not None:
                step_samples.append(
                    {
                        "timestamp": timestamp,
                        "count": int(steps),
                    },
                )

            # SpO2
            spo2 = entry_data.get("SpO2")
            if spo2 is not None:
                spo2_samples.append(
                    {
                        "timestamp": timestamp,
                        "percent": float(spo2) * 100 if spo2 <= 1 else float(spo2),  # Handle 0-1 or 0-100
                    },
                )

            # Energy consumption (joules)
            energy = entry_data.get("EnergyConsumption")
            if energy is not None:
                energy_samples.append(
                    {
                        "timestamp": timestamp,
                        "joules": float(energy),
                        "kcal": float(energy) / 4184,  # Convert to kcal
                    },
                )

            # HRV
            hrv = entry_data.get("HRV")
            if hrv is not None and hrv > 0:
                hrv_samples.append(
                    {
                        "timestamp": timestamp,
                        "rmssd_ms": float(hrv),
                    },
                )

        return {
            "heart_rate": heart_rate_samples,
            "steps": step_samples,
            "spo2": spo2_samples,
            "energy": energy_samples,
            "hrv": hrv_samples,
        }

    # -------------------------------------------------------------------------
    # Daily Activity Statistics - Suunto /247/daily-activity-statistics
    # -------------------------------------------------------------------------

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch aggregated daily activity statistics from Suunto API."""
        all_data = []
        current_start = start_date
        chunk_days = 14  # Reduced to 14 days to be safe (limit is 28 days)

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=chunk_days), end_date)

            # Suunto uses ISO 8601 format for this endpoint
            params = {
                "startdate": current_start.strftime("%Y-%m-%dT%H:%M:%S"),
                "enddate": current_end.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            try:
                # Note: This endpoint is under /247 not /247samples
                response = self._make_api_request(db, user_id, "/247/daily-activity-statistics", params=params)
                if isinstance(response, list):
                    all_data.extend(response)
            except Exception as e:
                print(f"Error fetching daily activity chunk {current_start} to {current_end}: {e}")

            current_start = current_end

        return all_data

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Suunto daily activity statistics.

        Suunto returns data grouped by type (stepcount, energyconsumption) with sources.
        """
        stat_name = raw_stats.get("Name")  # 'stepcount' or 'energyconsumption'
        aggregation = raw_stats.get("Aggregation")  # 'sum' or 'avg'
        sources = raw_stats.get("Sources", [])

        # Flatten sources into daily values
        daily_values = []
        for source in sources:
            source_name = source.get("Name")
            samples = source.get("Samples", [])
            for sample in samples:
                value = sample.get("Value")
                time_iso = sample.get("TimeISO8601")
                if value is not None:
                    daily_values.append(
                        {
                            "date": time_iso,
                            "source": source_name,
                            "value": value,
                        },
                    )

        return {
            "type": stat_name,
            "aggregation": aggregation,
            "daily_values": daily_values,
            "raw": raw_stats,
        }

    def save_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_samples: dict[str, list[dict[str, Any]]],
    ) -> int:
        """Save normalized activity samples to database."""
        count = 0

        # Map internal keys to SeriesType
        type_mapping = {
            "heart_rate": SeriesType.heart_rate,
            "steps": SeriesType.steps,
            "spo2": SeriesType.oxygen_saturation,
            "energy": SeriesType.energy,
            # TODO: Suunto provides RMSSD, not SDNN. See GitHub issue for fix.
            # https://www.suunto.com/sports/News-Articles-container-page/how-to-use-hrv-to-optimize-your-recovery/
            "hrv": SeriesType.heart_rate_variability_sdnn,
        }

        for key, samples in normalized_samples.items():
            series_type = type_mapping.get(key)
            if not series_type:
                continue

            for sample in samples:
                timestamp_str = sample.get("timestamp")
                if not timestamp_str:
                    continue

                try:
                    recorded_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except ValueError:
                    continue

                # Extract value based on key
                value = None
                if key == "heart_rate":
                    value = sample.get("bpm")
                elif key == "steps":
                    value = sample.get("count")
                elif key == "spo2":
                    value = sample.get("percent")
                elif key == "energy":
                    value = sample.get("kcal")
                elif key == "hrv":
                    value = sample.get("rmssd_ms")

                if value is None:
                    continue

                try:
                    sample_create = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider_name=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(value)),
                        series_type=series_type,
                        external_id=None,  # Suunto doesn't provide ID for individual samples
                    )
                    self.data_point_repo.create(db, sample_create)
                    count += 1
                except Exception:
                    # Log error but continue
                    pass

        return count

    def save_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_stats: list[dict[str, Any]],
    ) -> int:
        """Save normalized daily activity statistics to database."""
        count = 0

        for stat in normalized_stats:
            stat_type = stat.get("type")
            daily_values = stat.get("daily_values", [])

            series_type = None
            if stat_type == "stepcount":
                series_type = SeriesType.steps
            elif stat_type == "energyconsumption":
                series_type = SeriesType.energy

            if not series_type:
                continue

            for item in daily_values:
                date_str = item.get("date")
                value = item.get("value")

                if not date_str or value is None:
                    continue

                try:
                    recorded_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

                    # Convert energy to kcal if needed
                    final_value = Decimal(str(value))
                    if series_type == SeriesType.energy:
                        final_value = final_value / Decimal("4184")

                    sample_create = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider_name=self.provider_name,
                        recorded_at=recorded_at,
                        value=final_value,
                        series_type=series_type,
                        external_id=None,
                    )
                    self.data_point_repo.create(db, sample_create)
                    count += 1
                except Exception:
                    pass

        return count

    # -------------------------------------------------------------------------
    # Load and Save All Data
    # -------------------------------------------------------------------------

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
            normalized = self.normalize_sleep(item, user_id)
            try:
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
    ) -> dict[str, int]:
        """Load all 247 data types and save to database."""

        # Handle date defaults (last 28 days if not specified)
        if end_time:
            if isinstance(end_time, str):
                try:
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    end_dt = datetime.now()
            else:
                end_dt = end_time
        else:
            end_dt = datetime.now()

        if start_time:
            if isinstance(start_time, str):
                try:
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    start_dt = end_dt - timedelta(days=28)
            else:
                start_dt = start_time
        else:
            start_dt = end_dt - timedelta(days=28)

        results = {
            "sleep_sessions": 0,
            "recovery_samples": 0,
            "activity_samples": 0,
        }

        # Sleep
        try:
            results["sleep_sessions"] = self.load_and_save_sleep(db, user_id, start_dt, end_dt)
        except Exception as e:
            self.logger.error(f"Failed to load sleep data: {e}")

        # Activity Samples
        try:
            raw_activity = self.get_activity_samples(db, user_id, start_dt, end_dt)
            normalized_activity = self.normalize_activity_samples(raw_activity, user_id)
            results["activity_samples"] = self.save_activity_samples(db, user_id, normalized_activity)
        except Exception as e:
            self.logger.error(f"Failed to load activity samples: {e}")

        # Daily Activity Statistics
        try:
            raw_daily = self.get_daily_activity_statistics(db, user_id, start_dt, end_dt)
            normalized_daily = [self.normalize_daily_activity(item, user_id) for item in raw_daily]
            results["daily_activity"] = self.save_daily_activity_statistics(db, user_id, normalized_daily)
        except Exception as e:
            self.logger.error(f"Failed to load daily activity statistics: {e}")

        # Recovery and activity samples would need their own save methods
        # For now, they can be fetched via raw endpoints for debugging

        return results
