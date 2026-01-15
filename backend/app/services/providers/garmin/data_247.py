"""Garmin 247 Data implementation for sleep, dailies, epochs, and body composition."""

import logging
from datetime import datetime, timedelta, timezone
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


class Garmin247Data(Base247DataTemplate):
    """Garmin implementation for 247 data (sleep, dailies, epochs, body composition).

    Garmin Health API constraints:
    - All timestamps are UTC Unix seconds
    - Maximum query range: 24 hours per request
    - Data retention: ~7 days (backfill service can retrieve up to 5 years)
    - Parameters: uploadStartTimeInSeconds, uploadEndTimeInSeconds
    """

    CHUNK_HOURS = 24  # Garmin API max range per request
    DEFAULT_BACKFILL_DAYS = 7  # Default retention period

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
        self.logger = logging.getLogger(self.__class__.__name__)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _epoch_seconds(self, dt: datetime) -> int:
        """Convert datetime to UTC Unix timestamp (seconds)."""
        return int(dt.timestamp())

    def _from_epoch_seconds(self, ts: int) -> datetime:
        """Convert UTC Unix timestamp (seconds) to datetime."""
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make authenticated request to Garmin Wellness API."""
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
        )

    def _fetch_in_chunks(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        start_time: datetime,
        end_time: datetime,
        chunk_hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Fetch data in 24-hour chunks to comply with Garmin API limits.

        Args:
            db: Database session
            user_id: User ID
            endpoint: API endpoint path
            start_time: Start of date range
            end_time: End of date range
            chunk_hours: Size of each chunk in hours (default 24)

        Returns:
            List of all fetched records combined from all chunks
        """
        all_data: list[dict[str, Any]] = []
        current_start = start_time

        while current_start < end_time:
            current_end = min(current_start + timedelta(hours=chunk_hours), end_time)

            params = {
                "uploadStartTimeInSeconds": self._epoch_seconds(current_start),
                "uploadEndTimeInSeconds": self._epoch_seconds(current_end),
            }

            try:
                response = self._make_api_request(db, user_id, endpoint, params=params)
                if isinstance(response, list):
                    all_data.extend(response)
                elif response:
                    all_data.append(response)
            except Exception as e:
                self.logger.warning(
                    f"Error fetching {endpoint} chunk ({current_start.isoformat()} to {current_end.isoformat()}): {e}"
                )

            current_start = current_end

        return all_data

    # -------------------------------------------------------------------------
    # Sleep Data - /wellness-api/rest/sleeps
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep data from Garmin /wellness-api/rest/sleeps."""
        return self._fetch_in_chunks(db, user_id, "/wellness-api/rest/sleeps", start_time, end_time)

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Garmin sleep data to internal schema."""
        start_ts = raw_sleep.get("startTimeInSeconds", 0)
        duration = raw_sleep.get("durationInSeconds", 0)
        end_ts = start_ts + duration

        start_dt = self._from_epoch_seconds(start_ts)
        end_dt = self._from_epoch_seconds(end_ts)

        # Sleep stages (in seconds)
        deep_seconds = raw_sleep.get("deepSleepDurationInSeconds") or 0
        light_seconds = raw_sleep.get("lightSleepDurationInSeconds") or 0
        rem_seconds = raw_sleep.get("remSleepDurationInSeconds") or 0
        awake_seconds = raw_sleep.get("awakeDurationInSeconds") or 0

        # Extract sleep score if available
        sleep_score = None
        overall_score = raw_sleep.get("overallSleepScore")
        if overall_score and isinstance(overall_score, dict):
            sleep_score = overall_score.get("value") or overall_score.get("qualifierKey")

        return {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "duration_seconds": duration,
            "stages": {
                "deep_seconds": deep_seconds,
                "light_seconds": light_seconds,
                "rem_seconds": rem_seconds,
                "awake_seconds": awake_seconds,
            },
            "avg_heart_rate_bpm": raw_sleep.get("averageHeartRate"),
            "min_heart_rate_bpm": raw_sleep.get("lowestHeartRate"),
            "avg_respiration": raw_sleep.get("respirationAvg"),
            "avg_spo2_percent": raw_sleep.get("avgOxygenSaturation"),
            "sleep_score": sleep_score,
            "validation": raw_sleep.get("validation"),
            "garmin_summary_id": raw_sleep.get("summaryId"),
            "raw": raw_sleep,
        }

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> None:
        """Save normalized sleep data as EventRecord + EventRecordDetail."""
        sleep_id = normalized_sleep["id"]

        # Parse start and end times
        start_dt = None
        end_dt = None
        if normalized_sleep.get("start_time"):
            start_dt = datetime.fromisoformat(normalized_sleep["start_time"].replace("Z", "+00:00"))
        if normalized_sleep.get("end_time"):
            end_dt = datetime.fromisoformat(normalized_sleep["end_time"].replace("Z", "+00:00"))

        if not start_dt or not end_dt:
            self.logger.warning(f"Missing start/end time for sleep {sleep_id}")
            return

        # Create EventRecord for sleep
        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Garmin",
            device_id=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=normalized_sleep.get("garmin_summary_id"),
            provider_name=self.provider_name,
            user_id=user_id,
        )

        # Create detail with sleep-specific fields
        stages = normalized_sleep.get("stages", {})
        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=normalized_sleep.get("duration_seconds", 0) // 60,
            sleep_efficiency_score=Decimal(str(normalized_sleep.get("sleep_score", 0)))
            if normalized_sleep.get("sleep_score")
            else None,
            sleep_deep_minutes=stages.get("deep_seconds", 0) // 60,
            sleep_light_minutes=stages.get("light_seconds", 0) // 60,
            sleep_rem_minutes=stages.get("rem_seconds", 0) // 60,
            sleep_awake_minutes=stages.get("awake_seconds", 0) // 60,
            is_nap=False,  # Garmin doesn't distinguish naps in the same way
            heart_rate_avg=Decimal(str(normalized_sleep["avg_heart_rate_bpm"]))
            if normalized_sleep.get("avg_heart_rate_bpm")
            else None,
            heart_rate_min=normalized_sleep.get("min_heart_rate_bpm"),
        )

        try:
            created_record = event_record_service.create(db, record)
            detail.record_id = created_record.id
            event_record_service.create_detail(db, detail, detail_type="sleep")
        except Exception as e:
            self.logger.error(f"Error saving sleep record {sleep_id}: {e}")

    # -------------------------------------------------------------------------
    # Dailies Data - /wellness-api/rest/dailies
    # -------------------------------------------------------------------------

    def get_dailies_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily summaries from Garmin /wellness-api/rest/dailies."""
        return self._fetch_in_chunks(db, user_id, "/wellness-api/rest/dailies", start_time, end_time)

    def normalize_dailies(
        self,
        raw_daily: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Garmin daily summary to internal schema."""
        return {
            "user_id": user_id,
            "calendar_date": raw_daily.get("calendarDate"),
            "start_time_seconds": raw_daily.get("startTimeInSeconds"),
            "steps": raw_daily.get("steps"),
            "distance_meters": raw_daily.get("distanceInMeters"),
            "active_calories": raw_daily.get("activeKilocalories"),
            "bmr_calories": raw_daily.get("bmrKilocalories"),
            "floors_climbed": raw_daily.get("floorsClimbed"),
            "min_heart_rate": raw_daily.get("minHeartRateInBeatsPerMinute"),
            "max_heart_rate": raw_daily.get("maxHeartRateInBeatsPerMinute"),
            "avg_heart_rate": raw_daily.get("averageHeartRateInBeatsPerMinute"),
            "resting_heart_rate": raw_daily.get("restingHeartRateInBeatsPerMinute"),
            "avg_stress": raw_daily.get("averageStressLevel"),
            "max_stress": raw_daily.get("maxStressLevel"),
            "moderate_intensity_minutes": (raw_daily.get("moderateIntensityDurationInSeconds") or 0) // 60,
            "vigorous_intensity_minutes": (raw_daily.get("vigorousIntensityDurationInSeconds") or 0) // 60,
            "body_battery_charged": raw_daily.get("bodyBatteryChargedValue"),
            "body_battery_drained": raw_daily.get("bodyBatteryDrainedValue"),
            "body_battery_highest": raw_daily.get("bodyBatteryHighestValue"),
            "body_battery_lowest": raw_daily.get("bodyBatteryLowestValue"),
            "heart_rate_samples": raw_daily.get("timeOffsetHeartRateSamples"),
            "garmin_summary_id": raw_daily.get("summaryId"),
        }

    def save_dailies_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_daily: dict[str, Any],
    ) -> int:
        """Save daily data to DataPointSeries (multiple series types)."""
        count = 0
        calendar_date = normalized_daily.get("calendar_date")
        start_ts = normalized_daily.get("start_time_seconds")

        if not calendar_date and not start_ts:
            return 0

        # Use start timestamp or parse calendar date (noon UTC as reference time)
        if start_ts:
            recorded_at = self._from_epoch_seconds(start_ts)
        elif calendar_date:
            try:
                recorded_at = datetime.strptime(calendar_date, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
            except ValueError:
                return 0
        else:
            return 0

        # Save individual metrics as DataPointSeries
        series_mappings: list[tuple[str, SeriesType]] = [
            ("steps", SeriesType.steps),
            ("active_calories", SeriesType.energy),
            ("resting_heart_rate", SeriesType.resting_heart_rate),
            ("floors_climbed", SeriesType.flights_climbed),
            ("distance_meters", SeriesType.distance_walking_running),
        ]

        for field, series_type in series_mappings:
            value = normalized_daily.get(field)
            if value is not None:
                try:
                    sample = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider_name=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(value)),
                        series_type=series_type,
                        external_id=normalized_daily.get("garmin_summary_id"),
                    )
                    self.data_point_repo.create(db, sample)
                    count += 1
                except Exception as e:
                    self.logger.debug(f"Failed to save {field}: {e}")

        # Save heart rate samples if present
        hr_samples = normalized_daily.get("heart_rate_samples")
        if hr_samples and isinstance(hr_samples, dict):
            count += self._save_heart_rate_samples(db, user_id, start_ts or 0, hr_samples)

        return count

    def _save_heart_rate_samples(
        self,
        db: DbSession,
        user_id: UUID,
        base_timestamp: int,
        hr_samples: dict[str, int],
    ) -> int:
        """Save individual heart rate samples from daily summary.

        Args:
            db: Database session
            user_id: User ID
            base_timestamp: Base Unix timestamp (start of day)
            hr_samples: Dict of offset_seconds -> heart_rate_bpm

        Returns:
            Number of samples saved
        """
        count = 0
        base_dt = self._from_epoch_seconds(base_timestamp) if base_timestamp else None

        if not base_dt:
            return 0

        for offset_str, hr_value in hr_samples.items():
            try:
                offset_seconds = int(offset_str)
                recorded_at = base_dt + timedelta(seconds=offset_seconds)

                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_name=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(hr_value)),
                    series_type=SeriesType.heart_rate,
                )
                self.data_point_repo.create(db, sample)
                count += 1
            except Exception:
                pass

        return count

    # -------------------------------------------------------------------------
    # Epochs Data - /wellness-api/rest/epochs (15-minute granularity)
    # -------------------------------------------------------------------------

    def get_epochs_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch epoch data from Garmin /wellness-api/rest/epochs."""
        return self._fetch_in_chunks(db, user_id, "/wellness-api/rest/epochs", start_time, end_time)

    def normalize_epochs(
        self,
        raw_epochs: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize epoch data into categorized samples.

        Args:
            raw_epochs: List of raw epoch data from API
            user_id: User ID

        Returns:
            Dict with keys like 'heart_rate', 'steps', etc.
        """
        heart_rate_samples: list[dict[str, Any]] = []
        step_samples: list[dict[str, Any]] = []
        energy_samples: list[dict[str, Any]] = []

        for epoch in raw_epochs:
            start_ts = epoch.get("startTimeInSeconds", 0)
            if not start_ts:
                continue

            recorded_at = self._from_epoch_seconds(start_ts)

            # Heart rate
            mean_hr = epoch.get("meanHeartRateInBeatsPerMinute")
            if mean_hr:
                heart_rate_samples.append(
                    {
                        "timestamp": recorded_at.isoformat(),
                        "value": mean_hr,
                    }
                )

            # Steps
            steps = epoch.get("steps")
            if steps is not None:
                step_samples.append(
                    {
                        "timestamp": recorded_at.isoformat(),
                        "value": steps,
                    }
                )

            # Active calories
            calories = epoch.get("activeKilocalories")
            if calories is not None:
                energy_samples.append(
                    {
                        "timestamp": recorded_at.isoformat(),
                        "value": calories,
                    }
                )

        return {
            "heart_rate": heart_rate_samples,
            "steps": step_samples,
            "energy": energy_samples,
        }

    def save_epochs_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_epochs: dict[str, list[dict[str, Any]]],
    ) -> int:
        """Save epoch samples to DataPointSeries."""
        count = 0
        type_mapping: dict[str, SeriesType] = {
            "heart_rate": SeriesType.heart_rate,
            "steps": SeriesType.steps,
            "energy": SeriesType.energy,
        }

        for key, samples in normalized_epochs.items():
            series_type = type_mapping.get(key)
            if not series_type:
                continue

            for sample in samples:
                timestamp_str = sample.get("timestamp")
                value = sample.get("value")

                if not timestamp_str or value is None:
                    continue

                try:
                    recorded_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    sample_create = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider_name=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                    self.data_point_repo.create(db, sample_create)
                    count += 1
                except Exception:
                    pass

        return count

    # -------------------------------------------------------------------------
    # Body Composition - /wellness-api/rest/bodyComps
    # -------------------------------------------------------------------------

    def get_body_composition(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch body composition from Garmin /wellness-api/rest/bodyComps."""
        return self._fetch_in_chunks(db, user_id, "/wellness-api/rest/bodyComps", start_time, end_time)

    def save_body_composition(
        self,
        db: DbSession,
        user_id: UUID,
        raw_body_comp: dict[str, Any],
    ) -> int:
        """Save body composition metrics to DataPointSeries."""
        count = 0
        measurement_ts = raw_body_comp.get("measurementTimeInSeconds", 0)

        if not measurement_ts:
            return 0

        recorded_at = self._from_epoch_seconds(measurement_ts)
        summary_id = raw_body_comp.get("summaryId")

        # Weight (convert grams to kg)
        weight_grams = raw_body_comp.get("weightInGrams")
        if weight_grams:
            try:
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_name=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(weight_grams)) / 1000,  # Convert to kg
                    series_type=SeriesType.weight,
                    external_id=summary_id,
                )
                self.data_point_repo.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.debug(f"Failed to save weight: {e}")

        # Body fat percentage
        body_fat = raw_body_comp.get("bodyFatInPercent")
        if body_fat:
            try:
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_name=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(body_fat)),
                    series_type=SeriesType.body_fat_percentage,
                    external_id=summary_id,
                )
                self.data_point_repo.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.debug(f"Failed to save body fat: {e}")

        # BMI
        bmi = raw_body_comp.get("bodyMassIndex")
        if bmi:
            try:
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_name=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(bmi)),
                    series_type=SeriesType.body_mass_index,
                    external_id=summary_id,
                )
                self.data_point_repo.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.debug(f"Failed to save BMI: {e}")

        return count

    # -------------------------------------------------------------------------
    # HRV (Heart Rate Variability) - /wellness-api/rest/hrv
    # -------------------------------------------------------------------------

    def save_hrv_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_hrv: dict[str, Any],
    ) -> int:
        """Save HRV (Heart Rate Variability) data to DataPointSeries.

        Garmin HRV data includes:
        - lastNightAvg: Average HRV during sleep (ms)
        - lastNight5MinHigh: Highest 5-min HRV average during sleep (ms)
        - hrvValues: Individual HRV readings at time offsets (seconds: ms)
        - startTimeInSeconds: Start timestamp
        - durationInSeconds: Duration of measurement period

        Args:
            db: Database session
            user_id: User ID
            raw_hrv: Raw HRV data from Garmin API

        Returns:
            Number of records saved
        """
        count = 0
        start_ts = raw_hrv.get("startTimeInSeconds", 0)
        summary_id = raw_hrv.get("summaryId")
        calendar_date = raw_hrv.get("calendarDate")

        if not start_ts:
            self.logger.warning("HRV data missing startTimeInSeconds")
            return 0

        # Save lastNightAvg as the main HRV value for the night
        last_night_avg = raw_hrv.get("lastNightAvg")
        if last_night_avg is not None:
            try:
                # Use the start time as recorded_at for the nightly average
                recorded_at = self._from_epoch_seconds(start_ts)
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_name=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(last_night_avg)),
                    series_type=SeriesType.heart_rate_variability_sdnn,
                    external_id=summary_id,
                )
                self.data_point_repo.create(db, sample)
                count += 1
                self.logger.debug(f"Saved HRV nightly avg={last_night_avg}ms for {calendar_date}")
            except Exception as e:
                self.logger.debug(f"Failed to save HRV lastNightAvg: {e}")

        # Optionally save individual HRV readings from hrvValues
        # These are keyed by time offset in seconds from start_ts
        hrv_values = raw_hrv.get("hrvValues", {})
        if hrv_values and isinstance(hrv_values, dict):
            for offset_str, hrv_ms in hrv_values.items():
                try:
                    offset_seconds = int(offset_str)
                    recorded_at = self._from_epoch_seconds(start_ts + offset_seconds)
                    sample = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider_name=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(hrv_ms)),
                        series_type=SeriesType.heart_rate_variability_sdnn,
                        external_id=f"{summary_id}:{offset_str}" if summary_id else None,
                    )
                    self.data_point_repo.create(db, sample)
                    count += 1
                except Exception as e:
                    self.logger.debug(f"Failed to save HRV value at offset {offset_str}: {e}")

        return count

    # -------------------------------------------------------------------------
    # Abstract Method Implementations (from Base247DataTemplate)
    # -------------------------------------------------------------------------

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Garmin doesn't have a dedicated recovery endpoint - return empty.

        Recovery-like data (body battery, stress) is included in dailies.
        """
        return []

    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Garmin doesn't have dedicated recovery data."""
        return {}

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Use epochs for activity samples."""
        return self.get_epochs_data(db, user_id, start_time, end_time)

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Delegate to normalize_epochs."""
        return self.normalize_epochs(raw_samples, user_id)

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Use dailies for daily stats."""
        return self.get_dailies_data(db, user_id, start_date, end_date)

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Delegate to normalize_dailies."""
        return self.normalize_dailies(raw_stats, user_id)

    # -------------------------------------------------------------------------
    # Main Entry Points
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
            try:
                normalized = self.normalize_sleep(item, user_id)
                self.save_sleep_data(db, user_id, normalized)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save sleep data: {e}")
        return count

    def load_and_save_dailies(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load dailies data from API and save to database."""
        raw_data = self.get_dailies_data(db, user_id, start_time, end_time)
        count = 0
        for item in raw_data:
            try:
                normalized = self.normalize_dailies(item, user_id)
                count += self.save_dailies_data(db, user_id, normalized)
            except Exception as e:
                self.logger.warning(f"Failed to save daily data: {e}")
        return count

    def load_and_save_epochs(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load epochs data from API and save to database."""
        raw_data = self.get_epochs_data(db, user_id, start_time, end_time)
        normalized = self.normalize_epochs(raw_data, user_id)
        return self.save_epochs_data(db, user_id, normalized)

    def load_and_save_body_composition(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load body composition and save to database."""
        raw_data = self.get_body_composition(db, user_id, start_time, end_time)
        count = 0
        for item in raw_data:
            try:
                count += self.save_body_composition(db, user_id, item)
            except Exception as e:
                self.logger.warning(f"Failed to save body composition: {e}")
        return count

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, Any]:
        """Trigger Garmin backfill to fetch historical 247 data.

        This method uses Garmin's Backfill API endpoints which:
        - Don't require pull tokens (unlike regular summary endpoints)
        - Return 202 Accepted (async processing)
        - Data is sent to configured webhook endpoints

        Flow:
        1. Call backfill endpoints for each data type
        2. Garmin queues async processing
        3. Data arrives via webhooks (handled by garmin_webhooks.py)
        4. Webhook handler uses normalize/save methods from this class

        Args:
            db: Database session
            user_id: User ID
            start_time: Start of date range (datetime or ISO string)
            end_time: End of date range (datetime or ISO string)
            is_first_sync: If True, use max timeframe (2 years). If False, use default.

        Returns:
            Dict with backfill trigger results
        """
        # Import here to avoid circular import
        from contextlib import suppress

        from app.integrations.celery.tasks.garmin_backfill_task import start_backfill
        from app.services.providers.garmin.backfill import GarminBackfillService

        # Parse dates
        start_dt: datetime | None = None
        end_dt: datetime | None = None

        if isinstance(start_time, str):
            with suppress(ValueError, AttributeError):
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        elif isinstance(start_time, datetime):
            start_dt = start_time

        if isinstance(end_time, str):
            with suppress(ValueError, AttributeError):
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        elif isinstance(end_time, datetime):
            end_dt = end_time

        # Create backfill service
        backfill_service = GarminBackfillService(
            provider_name=self.provider_name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

        # Initialize sequential backfill tracking in Redis
        # This tracks progress: 5 data types × 30 days
        start_backfill(user_id)

        # Trigger backfill for ONLY the first data type (sleeps)
        # Subsequent data types are triggered after each webhook delivery
        # Flow: sleeps → webhook → dailies → webhook → ... → next day
        self.logger.info(
            f"Triggering Garmin sequential backfill for user {user_id} "
            f"(starting with sleeps, first_sync={is_first_sync})"
        )
        result = backfill_service.trigger_backfill(
            db=db,
            user_id=user_id,
            data_types=["sleeps"],  # Only first data type to avoid rate limiting
            start_time=start_dt,
            end_time=end_dt,
            is_first_sync=is_first_sync,
        )

        return {
            "backfill_triggered": True,
            "triggered_types": result["triggered"],
            "failed_types": result["failed"],
            "start_time": result["start_time"],
            "end_time": result["end_time"],
            "message": "Sequential backfill started. Data types will be fetched one at a time via webhooks.",
        }

    # -------------------------------------------------------------------------
    # Raw API Access (for debugging)
    # -------------------------------------------------------------------------

    def get_raw_dailies(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Get raw dailies data from API without normalization."""
        return self.get_dailies_data(db, user_id, start_time, end_time)

    def get_raw_epochs(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Get raw epochs data from API without normalization."""
        return self.get_epochs_data(db, user_id, start_time, end_time)
