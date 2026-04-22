"""Garmin 247 Data implementation for sleep, dailies, epochs, and body composition."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.config import settings
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.models import DataPointSeries, EventRecord
from app.repositories import DataSourceRepository, EventRecordRepository, UserConnectionRepository
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.schemas.enums import HealthScoreCategory, ProviderName, SeriesType
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    HealthScoreCreate,
    ScoreComponent,
    SleepStage,
    TimeSeriesSampleCreate,
)
from app.services.event_record_service import event_record_service
from app.services.health_score_service import health_score_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.dates import offset_to_iso
from app.utils.structured_logging import log_structured


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
        self.data_source_repo = DataSourceRepository()
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
                log_structured(
                    self.logger,
                    "warning",
                    f"Error fetching {endpoint} chunk ({current_start.isoformat()} to {current_end.isoformat()}): {e}",
                    provider="garmin",
                    task="fetch_in_chunks",
                    user_id=str(user_id),
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

    def _extract_sleep_stages_from_map(self, sleep_map: dict) -> list[SleepStage]:
        """Extract sleep stage intervals from Garmin sleepLevelsMap."""
        stages: list[SleepStage] = []
        for stage_key, intervals in sleep_map.items():
            try:
                stage_type = SleepStageType(stage_key)
            except ValueError:
                continue
            for iv in intervals:
                try:
                    stages.append(
                        SleepStage(
                            stage=stage_type,
                            start_time=datetime.fromtimestamp(iv["startTimeInSeconds"], tz=timezone.utc),
                            end_time=datetime.fromtimestamp(iv["endTimeInSeconds"], tz=timezone.utc),
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    log_structured(
                        self.logger,
                        "warning",
                        "Invalid sleep stage interval data",
                        interval_data=iv,
                        provider="garmin",
                        task="extract_sleep_stages_from_map",
                    )
                    continue

        return sorted(stages, key=lambda s: s.start_time)

    def _normalize_sleep_health_score(
        self,
        normalized_sleep: dict[str, Any],
        user_id: UUID,
    ) -> HealthScoreCreate | None:
        """Extract sleep health score from a normalized Garmin sleep record."""
        sleep_score = normalized_sleep.get("sleep_score")
        sleep_qualifier = normalized_sleep.get("sleep_qualifier")
        sleep_score_components = normalized_sleep.get("sleep_score_components")

        if sleep_score is None and sleep_qualifier is None:
            return None

        start_time_str = normalized_sleep.get("start_time")
        if not start_time_str:
            return None
        try:
            recorded_at = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

        return HealthScoreCreate(
            id=uuid4(),
            user_id=user_id,
            provider=ProviderName.GARMIN,
            category=HealthScoreCategory.SLEEP,
            value=sleep_score,
            qualifier=sleep_qualifier,
            recorded_at=recorded_at,
            components=sleep_score_components,
        )

    def normalize_sleep(  # type: ignore[override]
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> tuple[dict[str, Any], HealthScoreCreate | None]:
        """Normalize Garmin sleep data to internal schema."""
        start_ts = raw_sleep.get("startTimeInSeconds", 0)
        duration = raw_sleep.get("durationInSeconds", 0)
        end_ts = start_ts + duration

        start_dt = self._from_epoch_seconds(start_ts)
        end_dt = self._from_epoch_seconds(end_ts)
        zone_offset = offset_to_iso(raw_sleep.get("startTimeOffsetInSeconds"))

        # Sleep stages (in seconds)
        deep_seconds = raw_sleep.get("deepSleepDurationInSeconds") or 0
        light_seconds = raw_sleep.get("lightSleepDurationInSeconds") or 0
        rem_seconds = raw_sleep.get("remSleepInSeconds") or 0
        awake_seconds = raw_sleep.get("awakeDurationInSeconds") or 0

        sleep_stages: list[SleepStage] | None = None
        if sleep_map := raw_sleep.get("sleepLevelsMap"):
            sleep_stages = self._extract_sleep_stages_from_map(sleep_map)
            if sleep_stages:
                last_stage_end = max(int(s.end_time.timestamp()) for s in sleep_stages)
                end_ts = max(end_ts, last_stage_end)
                duration = end_ts - start_ts
                end_dt = self._from_epoch_seconds(end_ts)

        # Extract sleep score if available
        sleep_score = None
        sleep_qualifier = None
        overall_score = raw_sleep.get("overallSleepScore")
        if overall_score and isinstance(overall_score, dict):
            sleep_score = overall_score.get("value")
            sleep_qualifier = overall_score.get("qualifier")

        sleep_scores = raw_sleep.get("sleepScores") or {}
        sleep_score_components = {
            key: ScoreComponent(qualifier=value.get("qualifierKey")) for key, value in sleep_scores.items()
        }

        normalized = {
            "id": uuid4(),
            "user_id": user_id,
            "provider": self.provider_name,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "zone_offset": zone_offset,
            "duration_seconds": duration,
            "stages": {
                "deep_seconds": deep_seconds,
                "light_seconds": light_seconds,
                "rem_seconds": rem_seconds,
                "awake_seconds": awake_seconds,
            },
            "stage_timestamps": sleep_stages,
            "avg_heart_rate_bpm": raw_sleep.get("averageHeartRate"),
            "min_heart_rate_bpm": raw_sleep.get("lowestHeartRate"),
            "avg_respiration": raw_sleep.get("respirationAvg"),
            "avg_spo2_percent": raw_sleep.get("avgOxygenSaturation"),
            "sleep_score": sleep_score,
            "sleep_qualifier": sleep_qualifier,
            "sleep_score_components": sleep_score_components,
            "validation": raw_sleep.get("validation"),
            "garmin_summary_id": raw_sleep.get("summaryId"),
            "raw": raw_sleep,
        }
        return normalized, self._normalize_sleep_health_score(normalized, user_id)

    def _build_sleep_record(
        self,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate] | None:
        """Build EventRecord + EventRecordDetail for a sleep session (no DB interaction)."""
        sleep_id = normalized_sleep["id"]

        # Parse start and end times
        start_dt = None
        end_dt = None
        if normalized_sleep.get("start_time"):
            start_dt = datetime.fromisoformat(normalized_sleep["start_time"].replace("Z", "+00:00"))
        if normalized_sleep.get("end_time"):
            end_dt = datetime.fromisoformat(normalized_sleep["end_time"].replace("Z", "+00:00"))

        if not start_dt or not end_dt:
            log_structured(
                self.logger,
                "warning",
                f"Missing start/end time for sleep {sleep_id}",
                provider="garmin",
                task="build_sleep_record",
                user_id=str(user_id),
            )
            return None

        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Garmin",
            device_model=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            zone_offset=normalized_sleep.get("zone_offset"),
            external_id=normalized_sleep.get("garmin_summary_id"),
            source=self.provider_name,
            user_id=user_id,
        )

        stages = normalized_sleep.get("stages", {})
        asleep_seconds = stages.get("deep_seconds", 0) + stages.get("light_seconds", 0) + stages.get("rem_seconds", 0)
        time_in_bed_seconds = normalized_sleep.get("duration_seconds") or 0
        efficiency_score = Decimal(str(asleep_seconds / time_in_bed_seconds * 100)) if time_in_bed_seconds > 0 else None

        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=asleep_seconds // 60,
            sleep_time_in_bed_minutes=time_in_bed_seconds // 60,
            sleep_efficiency_score=efficiency_score,
            sleep_deep_minutes=stages.get("deep_seconds", 0) // 60,
            sleep_light_minutes=stages.get("light_seconds", 0) // 60,
            sleep_rem_minutes=stages.get("rem_seconds", 0) // 60,
            sleep_awake_minutes=stages.get("awake_seconds", 0) // 60,
            is_nap=False,
            heart_rate_avg=Decimal(str(normalized_sleep["avg_heart_rate_bpm"]))
            if normalized_sleep.get("avg_heart_rate_bpm")
            else None,
            heart_rate_min=normalized_sleep.get("min_heart_rate_bpm"),
            sleep_stages=normalized_sleep.get("stage_timestamps"),
        )

        return record, detail

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> None:
        """Save normalized sleep data as EventRecord + EventRecordDetail."""
        result = self._build_sleep_record(user_id, normalized_sleep)
        if not result:
            return

        record, detail = result
        try:
            event_record_service.create_or_merge_sleep(db, user_id, record, detail, settings.sleep_end_gap_minutes)
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Error saving sleep record {normalized_sleep['id']}: {e}",
                provider="garmin",
                task="save_sleep_data",
                user_id=str(user_id),
            )

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

    def _normalize_dailies_health_scores(
        self,
        normalized_daily: dict[str, Any],
        user_id: UUID,
    ) -> list[HealthScoreCreate]:
        """Extract stress and body battery health scores from a normalized Garmin daily."""
        scores: list[HealthScoreCreate] = []
        start_ts = normalized_daily.get("start_time_seconds")
        calendar_date = normalized_daily.get("calendar_date")
        if start_ts:
            recorded_at = self._from_epoch_seconds(start_ts)
        elif calendar_date:
            try:
                recorded_at = datetime.strptime(calendar_date, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
            except ValueError:
                return scores
        else:
            return scores

        avg_stress = normalized_daily.get("avg_stress")
        raw_qualifier = normalized_daily.get("stress_qualifier")
        stress_qualifier = raw_qualifier.replace("_", " ").title() if raw_qualifier else None
        # averageStressLevel is -1 when there is not enough data to calculate
        if avg_stress is not None and avg_stress != -1:
            scores.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.GARMIN,
                    category=HealthScoreCategory.STRESS,
                    value=avg_stress,
                    qualifier=stress_qualifier,
                    recorded_at=recorded_at,
                )
            )

        return scores

    def normalize_dailies(
        self,
        raw_daily: dict[str, Any],
        user_id: UUID,
    ) -> tuple[dict[str, Any], list[HealthScoreCreate]]:
        """Normalize Garmin daily summary to internal schema."""
        normalized = {
            "user_id": user_id,
            "calendar_date": raw_daily.get("calendarDate"),
            "start_time_seconds": raw_daily.get("startTimeInSeconds"),
            "zone_offset": offset_to_iso(raw_daily.get("startTimeOffsetInSeconds")),
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
            "stress_qualifier": raw_daily.get("stressQualifier"),
            "moderate_intensity_minutes": (raw_daily.get("moderateIntensityDurationInSeconds") or 0) // 60,
            "vigorous_intensity_minutes": (raw_daily.get("vigorousIntensityDurationInSeconds") or 0) // 60,
            "heart_rate_samples": raw_daily.get("timeOffsetHeartRateSamples"),
            "garmin_summary_id": raw_daily.get("summaryId"),
        }
        return normalized, self._normalize_dailies_health_scores(normalized, user_id)

    def _build_dailies_samples(
        self,
        user_id: UUID,
        normalized_daily: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from normalized daily data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        calendar_date = normalized_daily.get("calendar_date")
        start_ts = normalized_daily.get("start_time_seconds")

        if not calendar_date and not start_ts:
            return samples

        if start_ts:
            recorded_at = self._from_epoch_seconds(start_ts)
        elif calendar_date:
            try:
                recorded_at = datetime.strptime(calendar_date, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
            except ValueError:
                return samples
        else:
            return samples

        zone_offset = normalized_daily.get("zone_offset")

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
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        zone_offset=zone_offset,
                        value=Decimal(str(value)),
                        series_type=series_type,
                        external_id=normalized_daily.get("garmin_summary_id"),
                    )
                )

        hr_samples = normalized_daily.get("heart_rate_samples")
        if hr_samples and isinstance(hr_samples, dict):
            samples.extend(self._collect_heart_rate_samples(user_id, start_ts or 0, hr_samples, zone_offset))

        return samples

    def save_dailies_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_daily: tuple[dict[str, Any], list[HealthScoreCreate]],
    ) -> int:
        """Save daily data to DataPointSeries and health scores.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        daily_data, health_scores = normalized_daily
        samples = self._build_dailies_samples(user_id, daily_data)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        if health_scores:
            health_score_service.bulk_create(db, health_scores)
            db.commit()
        return len(samples)

    def _collect_heart_rate_samples(
        self,
        user_id: UUID,
        base_timestamp: int,
        hr_samples: dict[str, int],
        zone_offset: str | None = None,
    ) -> list[TimeSeriesSampleCreate]:
        """Collect heart rate samples from daily summary for bulk insert.

        Args:
            user_id: User ID
            base_timestamp: Base Unix timestamp (start of day)
            hr_samples: Dict of offset_seconds -> heart_rate_bpm
            zone_offset: ISO 8601 timezone offset string

        Returns:
            List of TimeSeriesSampleCreate objects
        """
        samples: list[TimeSeriesSampleCreate] = []
        base_dt = self._from_epoch_seconds(base_timestamp) if base_timestamp else None

        if not base_dt:
            return samples

        for offset_str, hr_value in hr_samples.items():
            try:
                offset_seconds = int(offset_str)
                recorded_at = base_dt + timedelta(seconds=offset_seconds)

                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(hr_value)),
                    series_type=SeriesType.heart_rate,
                )
                samples.append(sample)
            except Exception:
                pass

        return samples

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
            zone_offset = offset_to_iso(epoch.get("startTimeOffsetInSeconds"))

            # Heart rate
            mean_hr = epoch.get("meanHeartRateInBeatsPerMinute")
            if mean_hr:
                heart_rate_samples.append(
                    {
                        "timestamp": recorded_at.isoformat(),
                        "value": mean_hr,
                        "zone_offset": zone_offset,
                    }
                )

            # Steps
            steps = epoch.get("steps")
            if steps is not None:
                step_samples.append(
                    {
                        "timestamp": recorded_at.isoformat(),
                        "value": steps,
                        "zone_offset": zone_offset,
                    }
                )

            # Active calories
            calories = epoch.get("activeKilocalories")
            if calories is not None:
                energy_samples.append(
                    {
                        "timestamp": recorded_at.isoformat(),
                        "value": calories,
                        "zone_offset": zone_offset,
                    }
                )

        return {
            "heart_rate": heart_rate_samples,
            "steps": step_samples,
            "energy": energy_samples,
        }

    def _build_epochs_samples(
        self,
        user_id: UUID,
        normalized_epochs: dict[str, list[dict[str, Any]]],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from normalized epoch data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        type_mapping: dict[str, SeriesType] = {
            "heart_rate": SeriesType.heart_rate,
            "steps": SeriesType.steps,
            "energy": SeriesType.energy,
        }

        for key, epoch_samples in normalized_epochs.items():
            series_type = type_mapping.get(key)
            if not series_type:
                continue

            for sample in epoch_samples:
                timestamp_str = sample.get("timestamp")
                value = sample.get("value")

                if not timestamp_str or value is None:
                    continue

                try:
                    recorded_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    sample_create = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        zone_offset=sample.get("zone_offset"),
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                    samples.append(sample_create)
                except Exception:
                    pass

        return samples

    def save_epochs_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_epochs: dict[str, list[dict[str, Any]]],
    ) -> int:
        """Save epoch samples to DataPointSeries.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        samples = self._build_epochs_samples(user_id, normalized_epochs)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        return len(samples)

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

    def _build_body_comp_samples(
        self,
        user_id: UUID,
        raw_body_comp: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from body composition data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        measurement_ts = raw_body_comp.get("measurementTimeInSeconds", 0)

        if not measurement_ts:
            return samples

        recorded_at = self._from_epoch_seconds(measurement_ts)
        summary_id = raw_body_comp.get("summaryId")
        zone_offset = offset_to_iso(raw_body_comp.get("measurementTimeOffsetInSeconds"))

        # Weight (convert grams to kg)
        weight_grams = raw_body_comp.get("weightInGrams")
        if weight_grams:
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(weight_grams)) / 1000,  # Convert to kg
                    series_type=SeriesType.weight,
                    external_id=summary_id,
                )
            )

        # Body fat percentage
        body_fat = raw_body_comp.get("bodyFatInPercent")
        if body_fat:
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(body_fat)),
                    series_type=SeriesType.body_fat_percentage,
                    external_id=summary_id,
                )
            )

        # BMI
        bmi = raw_body_comp.get("bodyMassIndex")
        if bmi:
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(bmi)),
                    series_type=SeriesType.body_mass_index,
                    external_id=summary_id,
                )
            )

        return samples

    def save_body_composition(
        self,
        db: DbSession,
        user_id: UUID,
        raw_body_comp: dict[str, Any],
    ) -> int:
        """Save body composition metrics to DataPointSeries.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        samples = self._build_body_comp_samples(user_id, raw_body_comp)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # HRV (Heart Rate Variability) - /wellness-api/rest/hrv
    # -------------------------------------------------------------------------

    def _build_hrv_samples(
        self,
        user_id: UUID,
        raw_hrv: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from HRV data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        start_ts = raw_hrv.get("startTimeInSeconds", 0)
        summary_id = raw_hrv.get("summaryId")
        calendar_date = raw_hrv.get("calendarDate")
        zone_offset = offset_to_iso(raw_hrv.get("startTimeOffsetInSeconds"))

        if not start_ts:
            log_structured(
                self.logger,
                "warning",
                "HRV data missing startTimeInSeconds",
                provider="garmin",
                task="build_hrv_samples",
                user_id=str(user_id),
            )
            return samples

        # Collect lastNightAvg as the main HRV value for the night
        last_night_avg = raw_hrv.get("lastNightAvg")
        if last_night_avg is not None:
            recorded_at = self._from_epoch_seconds(start_ts)
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(last_night_avg)),
                    series_type=SeriesType.heart_rate_variability_rmssd,
                    external_id=summary_id,
                )
            )
            self.logger.debug(f"Collecting HRV nightly avg={last_night_avg}ms for {calendar_date}")

        # Collect individual HRV readings from hrvValues
        hrv_values = raw_hrv.get("hrvValues", {})
        if hrv_values and isinstance(hrv_values, dict):
            for offset_str, hrv_ms in hrv_values.items():
                try:
                    offset_seconds = int(offset_str)
                    recorded_at = self._from_epoch_seconds(start_ts + offset_seconds)
                    sample = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        zone_offset=zone_offset,
                        value=Decimal(str(hrv_ms)),
                        series_type=SeriesType.heart_rate_variability_rmssd,
                        external_id=f"{summary_id}:{offset_str}" if summary_id else None,
                    )
                    samples.append(sample)
                except Exception as e:
                    self.logger.debug(f"Failed to collect HRV value at offset {offset_str}: {e}")

        return samples

    def save_hrv_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_hrv: dict[str, Any],
    ) -> int:
        """Save HRV (Heart Rate Variability) data to DataPointSeries.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        samples = self._build_hrv_samples(user_id, raw_hrv)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Activity Data - /wellness-api/rest/activities
    # -------------------------------------------------------------------------

    def _build_activity_record(
        self,
        user_id: UUID,
        raw_activity: dict[str, Any],
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate] | None:
        """Build EventRecord + WorkoutDetail for an activity (no DB interaction)."""
        activity_id = raw_activity.get("activityId")
        if not activity_id:
            return None

        start_ts = raw_activity.get("startTimeInSeconds", 0)
        duration = raw_activity.get("durationInSeconds", 0)

        if not start_ts:
            return None

        start_dt = self._from_epoch_seconds(start_ts)
        end_dt = self._from_epoch_seconds(start_ts + duration) if duration else start_dt
        zone_offset = offset_to_iso(raw_activity.get("startTimeOffsetInSeconds"))

        activity_type = raw_activity.get("activityType", "unknown")

        record_id = uuid4()
        record = EventRecordCreate(
            id=record_id,
            category="workout",
            type=activity_type.lower(),
            source_name="Garmin",
            device_model=raw_activity.get("deviceId"),
            duration_seconds=duration,
            start_datetime=start_dt,
            end_datetime=end_dt,
            zone_offset=zone_offset,
            external_id=str(activity_id),
            source=self.provider_name,
            user_id=user_id,
        )

        distance = raw_activity.get("distanceInMeters")
        calories = raw_activity.get("activeKilocalories")
        avg_hr = raw_activity.get("averageHeartRateInBeatsPerMinute")
        max_hr = raw_activity.get("maxHeartRateInBeatsPerMinute")
        elevation_gain = raw_activity.get("elevationGainInMeters")
        avg_speed = raw_activity.get("averageSpeedInMetersPerSecond")

        detail = EventRecordDetailCreate(
            record_id=record_id,
            distance=Decimal(str(distance)) if distance is not None else None,
            energy_burned=Decimal(str(calories)) if calories is not None else None,
            heart_rate_avg=Decimal(str(avg_hr)) if avg_hr is not None else None,
            heart_rate_max=max_hr,
            total_elevation_gain=Decimal(str(elevation_gain)) if elevation_gain is not None else None,
            average_speed=Decimal(str(avg_speed)) if avg_speed is not None else None,
        )

        return record, detail

    def save_activity_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_activity: dict[str, Any],
    ) -> int:
        """Save activity data as EventRecord with WorkoutDetails."""
        result = self._build_activity_record(user_id, raw_activity)
        if not result:
            return 0

        record, detail = result
        try:
            created_record = event_record_service.create(db, record)
            detail.record_id = created_record.id
            event_record_service.create_detail(db, detail, detail_type="workout")
            return 1
        except Exception as e:
            self.logger.debug(f"Activity may already exist: {e}")
            return 0

    # -------------------------------------------------------------------------
    # Stress Data - /wellness-api/rest/stressDetails
    # -------------------------------------------------------------------------

    def _normalize_body_battery_health_score(
        self,
        user_id: UUID,
        raw_stress: dict[str, Any],
    ) -> HealthScoreCreate | None:
        """Extract peak body battery health score from a stressDetails record."""
        start_ts = raw_stress.get("startTimeInSeconds", 0)
        if not start_ts:
            return None
        battery_values = raw_stress.get("timeOffsetBodyBatteryValues") or raw_stress.get("bodyBatteryValues", {})
        if not battery_values or not isinstance(battery_values, dict):
            return None
        valid = [v for v in battery_values.values() if v is not None and v >= 0]
        if not valid:
            return None
        return HealthScoreCreate(
            id=uuid4(),
            user_id=user_id,
            provider=ProviderName.GARMIN,
            category=HealthScoreCategory.BODY_BATTERY,
            value=max(valid),
            recorded_at=self._from_epoch_seconds(start_ts),
            zone_offset=offset_to_iso(raw_stress.get("startTimeOffsetInSeconds")),
        )

    def _build_stress_samples(
        self,
        user_id: UUID,
        raw_stress: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build individual stress level and body battery time series samples from a stressDetails record."""
        samples: list[TimeSeriesSampleCreate] = []
        start_ts = raw_stress.get("startTimeInSeconds", 0)

        if not start_ts:
            return samples

        zone_offset = offset_to_iso(raw_stress.get("startTimeOffsetInSeconds"))

        # Stress level values (negative values are special states: off-wrist, motion, etc.)
        stress_values = raw_stress.get("timeOffsetStressLevelValues") or raw_stress.get("stressLevelValues", {})
        if stress_values and isinstance(stress_values, dict):
            for offset_str, stress_value in stress_values.items():
                try:
                    if stress_value is None or stress_value < 0:
                        continue
                    offset_seconds = int(offset_str)
                    recorded_at = self._from_epoch_seconds(start_ts + offset_seconds)
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=recorded_at,
                            zone_offset=zone_offset,
                            value=Decimal(str(stress_value)),
                            series_type=SeriesType.garmin_stress_level,
                        )
                    )
                except Exception:
                    pass

        # Body battery values
        battery_values = raw_stress.get("timeOffsetBodyBatteryValues") or raw_stress.get("bodyBatteryValues", {})
        if battery_values and isinstance(battery_values, dict):
            for offset_str, battery_value in battery_values.items():
                try:
                    if battery_value is None or battery_value < 0:
                        continue
                    offset_seconds = int(offset_str)
                    recorded_at = self._from_epoch_seconds(start_ts + offset_seconds)
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=recorded_at,
                            zone_offset=zone_offset,
                            value=Decimal(str(battery_value)),
                            series_type=SeriesType.garmin_body_battery,
                        )
                    )
                except Exception:
                    pass

        return samples

    def save_stress_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_stress: dict[str, Any],
    ) -> int:
        """Save individual stress/body battery timeseries
        and peak body battery health score from a stressDetails record."""
        samples = self._build_stress_samples(user_id, raw_stress)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        if score := self._normalize_body_battery_health_score(user_id, raw_stress):
            health_score_service.bulk_create(db, [score])
            db.commit()
        return len(samples)

    # -------------------------------------------------------------------------
    # Respiration Data - /wellness-api/rest/respiration
    # -------------------------------------------------------------------------

    def _build_respiration_samples(
        self,
        user_id: UUID,
        raw_respiration: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from respiration data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        start_ts = raw_respiration.get("startTimeInSeconds", 0)
        summary_id = raw_respiration.get("summaryId")

        if not start_ts:
            return samples

        zone_offset = offset_to_iso(raw_respiration.get("startTimeOffsetInSeconds"))

        # Average respiration for the period
        avg_respiration = raw_respiration.get("avgWakingRespirationValue")
        if avg_respiration:
            recorded_at = self._from_epoch_seconds(start_ts)
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(avg_respiration)),
                    series_type=SeriesType.respiratory_rate,
                    external_id=summary_id,
                )
            )

        # Individual respiration readings
        respiration_values = raw_respiration.get("timeOffsetRespirationRateValues", {})
        if respiration_values and isinstance(respiration_values, dict):
            for offset_str, resp_value in respiration_values.items():
                try:
                    if resp_value is None or resp_value <= 0:
                        continue
                    offset_seconds = int(offset_str)
                    recorded_at = self._from_epoch_seconds(start_ts + offset_seconds)
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=recorded_at,
                            zone_offset=zone_offset,
                            value=Decimal(str(resp_value)),
                            series_type=SeriesType.respiratory_rate,
                        )
                    )
                except Exception:
                    pass

        return samples

    def save_respiration_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_respiration: dict[str, Any],
    ) -> int:
        """Save respiration rate data to DataPointSeries.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        samples = self._build_respiration_samples(user_id, raw_respiration)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Pulse Ox Data - /wellness-api/rest/pulseOx
    # -------------------------------------------------------------------------

    def _build_pulse_ox_samples(
        self,
        user_id: UUID,
        raw_pulse_ox: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from pulse ox data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        start_ts = raw_pulse_ox.get("startTimeInSeconds", 0)
        summary_id = raw_pulse_ox.get("summaryId")

        if not start_ts:
            return samples

        zone_offset = offset_to_iso(raw_pulse_ox.get("startTimeOffsetInSeconds"))

        # Average SpO2
        avg_spo2 = raw_pulse_ox.get("avgSpo2")
        if avg_spo2:
            recorded_at = self._from_epoch_seconds(start_ts)
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(avg_spo2)),
                    series_type=SeriesType.oxygen_saturation,
                    external_id=summary_id,
                )
            )

        # Individual SpO2 readings
        spo2_values = raw_pulse_ox.get("timeOffsetSpo2Values", {})
        if spo2_values and isinstance(spo2_values, dict):
            for offset_str, spo2_value in spo2_values.items():
                try:
                    if spo2_value is None or spo2_value <= 0:
                        continue
                    offset_seconds = int(offset_str)
                    recorded_at = self._from_epoch_seconds(start_ts + offset_seconds)
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=recorded_at,
                            zone_offset=zone_offset,
                            value=Decimal(str(spo2_value)),
                            series_type=SeriesType.oxygen_saturation,
                        )
                    )
                except Exception:
                    pass

        return samples

    def save_pulse_ox_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_pulse_ox: dict[str, Any],
    ) -> int:
        """Save SpO2 (blood oxygen saturation) data to DataPointSeries.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        samples = self._build_pulse_ox_samples(user_id, raw_pulse_ox)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Blood Pressure - /wellness-api/rest/bloodPressures
    # -------------------------------------------------------------------------

    def _build_blood_pressure_samples(
        self,
        user_id: UUID,
        raw_bp: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from blood pressure data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        measurement_ts = raw_bp.get("measurementTimestampGMT", 0)
        summary_id = raw_bp.get("summaryId")

        # Try alternative timestamp field
        if not measurement_ts:
            measurement_ts = raw_bp.get("startTimeInSeconds", 0)

        if not measurement_ts:
            return samples

        recorded_at = self._from_epoch_seconds(measurement_ts)

        meas = raw_bp.get("measurementTimeOffsetInSeconds")
        start = raw_bp.get("startTimeOffsetInSeconds")
        zone_offset = offset_to_iso(meas if meas is not None else start)

        # Systolic blood pressure
        systolic = raw_bp.get("systolic")
        if systolic:
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(systolic)),
                    series_type=SeriesType.blood_pressure_systolic,
                    external_id=summary_id,
                )
            )

        # Diastolic blood pressure
        diastolic = raw_bp.get("diastolic")
        if diastolic:
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(diastolic)),
                    series_type=SeriesType.blood_pressure_diastolic,
                    external_id=summary_id,
                )
            )

        return samples

    def save_blood_pressure_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_bp: dict[str, Any],
    ) -> int:
        """Save blood pressure data to DataPointSeries.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        samples = self._build_blood_pressure_samples(user_id, raw_bp)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # User Metrics - /wellness-api/rest/userMetrics
    # -------------------------------------------------------------------------

    def _build_user_metrics_samples(
        self,
        user_id: UUID,
        raw_metrics: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from user metrics data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        calendar_date = raw_metrics.get("calendarDate")
        summary_id = raw_metrics.get("summaryId")

        if not calendar_date:
            return samples

        try:
            recorded_at = datetime.strptime(calendar_date, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
        except ValueError:
            return samples

        # VO2 max
        vo2_max = raw_metrics.get("vo2Max")
        if vo2_max:
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(vo2_max)),
                    series_type=SeriesType.vo2_max,
                    external_id=summary_id,
                )
            )

        # Fitness age
        fitness_age = raw_metrics.get("fitnessAge")
        if fitness_age:
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(fitness_age)),
                    series_type=SeriesType.garmin_fitness_age,
                    external_id=summary_id,
                )
            )

        return samples

    def save_user_metrics_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_metrics: dict[str, Any],
    ) -> int:
        """Save user metrics (VO2max, fitness age) to DataPointSeries.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        samples = self._build_user_metrics_samples(user_id, raw_metrics)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Skin Temperature - /wellness-api/rest/skinTemp
    # -------------------------------------------------------------------------

    def _build_skin_temp_samples(
        self,
        user_id: UUID,
        raw_skin_temp: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from skin temperature data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        start_ts = raw_skin_temp.get("startTimeInSeconds", 0)
        summary_id = raw_skin_temp.get("summaryId")

        if not start_ts:
            return samples

        recorded_at = self._from_epoch_seconds(start_ts)
        zone_offset = offset_to_iso(raw_skin_temp.get("startTimeOffsetInSeconds"))

        skin_temp = raw_skin_temp.get("skinTemperature")
        if skin_temp is not None:
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(skin_temp)),
                    series_type=SeriesType.skin_temperature,
                    external_id=summary_id,
                )
            )

        return samples

    def save_skin_temp_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_skin_temp: dict[str, Any],
    ) -> int:
        """Save skin temperature data to DataPointSeries.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        samples = self._build_skin_temp_samples(user_id, raw_skin_temp)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Health Snapshot - /wellness-api/rest/healthSnapshot
    # -------------------------------------------------------------------------

    def _build_health_snapshot_samples(
        self,
        user_id: UUID,
        raw_snapshot: dict[str, Any],
    ) -> list[TimeSeriesSampleCreate]:
        """Build time series samples from health snapshot data (no DB interaction)."""
        samples: list[TimeSeriesSampleCreate] = []
        start_ts = raw_snapshot.get("startTimeInSeconds", 0)
        summary_id = raw_snapshot.get("summaryId")

        if not start_ts:
            return samples

        recorded_at = self._from_epoch_seconds(start_ts)
        zone_offset = offset_to_iso(raw_snapshot.get("startTimeOffsetInSeconds"))

        summaries = {s["summaryType"]: s for s in raw_snapshot.get("summaries", []) if "summaryType" in s}

        # Heart rate from snapshot
        if heart_rate := summaries.get("heart_rate", {}).get("avgValue"):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(heart_rate)),
                    series_type=SeriesType.heart_rate,
                    external_id=f"{summary_id}:hr" if summary_id else None,
                )
            )

        # RMSSD HRV from snapshot
        if rmssd := summaries.get("rmssd_hrv", {}).get("avgValue"):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(rmssd)),
                    series_type=SeriesType.heart_rate_variability_rmssd,
                    external_id=f"{summary_id}:rmssd_hrv" if summary_id else None,
                )
            )

        # SDNN HRV from snapshot
        if sdrr := summaries.get("sdrr_hrv", {}).get("avgValue"):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(sdrr)),
                    series_type=SeriesType.heart_rate_variability_sdnn,
                    external_id=f"{summary_id}:sdrr_hrv" if summary_id else None,
                )
            )

        # Stress from snapshot
        stress_summary = summaries.get("stress", {})
        stress = stress_summary.get("avgValue")
        if stress is not None and stress >= 0:
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(stress)),
                    series_type=SeriesType.garmin_stress_level,
                    external_id=f"{summary_id}:stress" if summary_id else None,
                )
            )

        # SpO2 from snapshot
        if spo2 := summaries.get("pulse_ox", {}).get("avgValue"):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(spo2)),
                    series_type=SeriesType.oxygen_saturation,
                    external_id=f"{summary_id}:spo2" if summary_id else None,
                )
            )

        # Respiration from snapshot
        if respiration := summaries.get("respiration", {}).get("avgValue"):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    zone_offset=zone_offset,
                    value=Decimal(str(respiration)),
                    series_type=SeriesType.respiratory_rate,
                    external_id=f"{summary_id}:resp" if summary_id else None,
                )
            )

        return samples

    def save_health_snapshot_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_snapshot: dict[str, Any],
    ) -> int:
        """Save health snapshot data to DataPointSeries.

        Uses bulk_create with ON CONFLICT DO UPDATE for efficient upserts.
        """
        samples = self._build_health_snapshot_samples(user_id, raw_snapshot)
        if samples:
            self.data_point_repo.bulk_create(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Move IQ - /wellness-api/rest/moveiq
    # -------------------------------------------------------------------------

    def _build_moveiq_record(
        self,
        user_id: UUID,
        raw_moveiq: dict[str, Any],
    ) -> EventRecordCreate | None:
        """Build EventRecord for a Move IQ activity (no DB interaction)."""
        start_ts = raw_moveiq.get("startTimeInSeconds", 0)
        duration = raw_moveiq.get("durationInSeconds", 0)
        summary_id = raw_moveiq.get("summaryId")

        if not start_ts:
            return None

        start_dt = self._from_epoch_seconds(start_ts)
        end_dt = self._from_epoch_seconds(start_ts + duration) if duration else start_dt
        zone_offset = offset_to_iso(raw_moveiq.get("startTimeOffsetInSeconds"))

        activity_type = raw_moveiq.get("activityType", "unknown")

        return EventRecordCreate(
            id=uuid4(),
            category="activity",
            type=f"moveiq_{activity_type.lower()}",
            source_name="Garmin Move IQ",
            device_model=None,
            duration_seconds=duration,
            start_datetime=start_dt,
            end_datetime=end_dt,
            zone_offset=zone_offset,
            external_id=summary_id,
            source=self.provider_name,
            user_id=user_id,
        )

    def save_moveiq_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_moveiq: dict[str, Any],
    ) -> int:
        """Save Move IQ auto-detected activities as EventRecords."""
        record = self._build_moveiq_record(user_id, raw_moveiq)
        if not record:
            return 0

        try:
            event_record_service.create(db, record)
            return 1
        except Exception as e:
            self.logger.debug(f"Move IQ record may already exist: {e}")
            return 0

    # -------------------------------------------------------------------------
    # Menstrual Cycle Tracking - /wellness-api/rest/mct
    # -------------------------------------------------------------------------

    def save_mct_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_mct: dict[str, Any],
    ) -> int:
        """Save menstrual cycle tracking data.

        MCT data includes cycle day, phase, and symptoms.
        Currently stored as log entry; expand as needed.

        Args:
            db: Database session
            user_id: User ID
            raw_mct: Raw MCT data from Garmin API

        Returns:
            0 (logging only for now)
        """
        # MCT data structure is complex and user-sensitive
        # For now, just log that we received it; expand implementation as needed
        calendar_date = raw_mct.get("calendarDate")
        cycle_day = raw_mct.get("dayInCycle")

        if calendar_date:
            self.logger.debug(f"MCT data received for user {user_id}: date={calendar_date}, day={cycle_day}")

        # TODO: Implement proper MCT storage if needed
        return 0

    # -------------------------------------------------------------------------
    # Batch Processing (for webhook handlers)
    # -------------------------------------------------------------------------

    def process_items_batch(
        self,
        db: DbSession,
        user_id: UUID,
        summary_type: str,
        items: list[dict[str, Any]],
    ) -> int:
        """Process a batch of webhook items with minimal DB round-trips.

        Accumulates all samples/records across all items, then performs
        single bulk inserts instead of per-item DB calls.

        Args:
            db: Database session
            user_id: User ID
            summary_type: Garmin data type (e.g. "dailies", "sleeps")
            items: List of raw items from webhook payload

        Returns:
            Number of data points saved
        """
        all_samples: list[TimeSeriesSampleCreate] = []
        all_records: list[EventRecordCreate] = []
        all_workout_details: list[EventRecordDetailCreate] = []
        all_sleep_details: list[EventRecordDetailCreate] = []
        all_health_scores: list[HealthScoreCreate] = []

        for item in items:
            try:
                # DataPointSeries types - accumulate samples
                match summary_type:
                    case "dailies":
                        normalized, health_scores = self.normalize_dailies(item, user_id)
                        all_samples.extend(self._build_dailies_samples(user_id, normalized))
                        all_health_scores.extend(health_scores)
                    case "epochs":
                        normalized = self.normalize_epochs([item], user_id)
                        all_samples.extend(self._build_epochs_samples(user_id, normalized))
                    case "bodyComps":
                        all_samples.extend(self._build_body_comp_samples(user_id, item))
                    case "hrv":
                        all_samples.extend(self._build_hrv_samples(user_id, item))
                    case "stressDetails":
                        all_samples.extend(self._build_stress_samples(user_id, item))
                        if score := self._normalize_body_battery_health_score(user_id, item):
                            all_health_scores.append(score)
                    case "respiration":
                        all_samples.extend(self._build_respiration_samples(user_id, item))
                    case "pulseox":
                        all_samples.extend(self._build_pulse_ox_samples(user_id, item))
                    case "bloodPressures":
                        all_samples.extend(self._build_blood_pressure_samples(user_id, item))
                    case "userMetrics":
                        all_samples.extend(self._build_user_metrics_samples(user_id, item))
                    case "skinTemp":
                        all_samples.extend(self._build_skin_temp_samples(user_id, item))
                    case "healthSnapshot":
                        all_samples.extend(self._build_health_snapshot_samples(user_id, item))

                    # EventRecord types - accumulate records + details
                    case "sleeps":
                        normalized, health_score = self.normalize_sleep(item, user_id)
                        result = self._build_sleep_record(user_id, normalized)
                        if result:
                            record, detail = result
                            all_records.append(record)
                            all_sleep_details.append(detail)
                        if health_score:
                            all_health_scores.append(health_score)
                    case "activities" | "activityDetails":
                        result = self._build_activity_record(user_id, item)
                        if result:
                            record, detail = result
                            all_records.append(record)
                            all_workout_details.append(detail)
                    case "moveiq":
                        record = self._build_moveiq_record(user_id, item)
                        if record:
                            all_records.append(record)

                    # No-op types
                    case "mct":
                        self.save_mct_data(db, user_id, item)

            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Error building batch item for {summary_type}: {e}",
                    provider="garmin",
                    task="process_items_batch",
                    user_id=str(user_id),
                )

        count = 0

        # Single bulk insert for DataPointSeries
        if all_samples:
            self.data_point_repo.bulk_create(db, all_samples)
            count += len(all_samples)

        # Single bulk insert for EventRecords
        if all_records:
            inserted_ids = event_record_service.bulk_create(db, all_records)
            db.flush()

            inserted_set = set(inserted_ids)

            # Bulk create sleep details for actually inserted records
            sleep_details = [d for d in all_sleep_details if d.record_id in inserted_set]
            if sleep_details:
                event_record_service.bulk_create_details(db, sleep_details, detail_type="sleep")

            # Bulk create workout details for actually inserted records
            workout_details = [d for d in all_workout_details if d.record_id in inserted_set]
            if workout_details:
                event_record_service.bulk_create_details(db, workout_details, detail_type="workout")

            count += len(inserted_ids)

        if all_health_scores:
            health_score_service.bulk_create(db, all_health_scores)
            db.commit()

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

    def normalize_daily_activity(  # type: ignore[override]
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> tuple[dict[str, Any], list[HealthScoreCreate]]:
        """Delegate to normalize_dailies."""
        return self.normalize_dailies(raw_stats, user_id)

    # -------------------------------------------------------------------------
    # Main Entry Points
    # -------------------------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, Any]:
        """No-op: Garmin 247 data arrives via webhooks.

        REST/summary endpoints are not used. Historical data is fetched
        via the backfill API which delivers data through webhooks.

        Args:
            db: Database session
            user_id: User ID
            start_time: Unused (kept for interface compatibility)
            end_time: Unused (kept for interface compatibility)
            is_first_sync: Unused (kept for interface compatibility)

        Returns:
            Dict indicating data arrives via webhooks
        """
        self.logger.info(f"Garmin 247 data for user {user_id} arrives via webhooks (no REST fetch)")
        return {
            "sync_complete": True,
            "total_saved": 0,
            "message": "Garmin data arrives via webhooks. No REST fetch performed.",
        }
