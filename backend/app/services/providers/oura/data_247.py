"""Oura Ring 247 Data implementation for sleep, readiness, heart rate, activity, and SpO2."""

from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import groupby
from typing import Any
from uuid import UUID, uuid4

from app.config import settings
from app.constants.series_types.oura.sleep_phase import SLEEP_PHASE_MAP
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.schemas.enums import HealthScoreCategory, ProviderName, SeriesType
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    HealthScoreCreate,
    ScoreComponent,
    SleepStage,
    TimeSeriesSampleCreate,
)
from app.schemas.providers.oura import (
    OuraDailyActivityJSON,
    OuraDailyReadinessJSON,
    OuraDailySleepJSON,
    OuraSleepJSON,
)
from app.schemas.providers.oura.imports import OuraIntervalData, OuraPersonalInfoJSON
from app.services.event_record_service import event_record_service
from app.services.health_score_service import health_score_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.raw_payload_storage import store_raw_payload
from app.services.timeseries_service import timeseries_service
from app.utils.structured_logging import log_structured


class Oura247Data(Base247DataTemplate):
    """Oura implementation for 247 data (sleep, readiness, activity, HR, SpO2)."""

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ):
        super().__init__(provider_name, api_base_url, oauth)
        self.event_record_repo = EventRecordRepository(EventRecord)
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
        """Generic paginator for Oura API endpoints that return {data: [...], next_token: ...}."""
        all_data: list[dict[str, Any]] = []
        next_token: str | None = None

        while True:
            request_params = {**params}
            if next_token:
                request_params["next_token"] = next_token

            try:
                response = self._make_api_request(db, user_id, endpoint, params=request_params)
                store_raw_payload(
                    source="api_response",
                    provider="oura",
                    payload=response,
                    user_id=str(user_id),
                    trace_id=endpoint,
                )

                data = response.get("data", []) if isinstance(response, dict) else []
                all_data.extend(data)

                next_token = response.get("next_token") if isinstance(response, dict) else None
                if not data or not next_token:
                    break

            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    "Error fetching endpoint",
                    action="oura_api_fetch_error",
                    endpoint=endpoint,
                    error=str(e),
                )
                if all_data:
                    log_structured(
                        self.logger,
                        "warning",
                        "Returning partial data due to error",
                        action="oura_api_partial_data",
                        endpoint=endpoint,
                        error=str(e),
                    )
                    break
                raise

        return all_data

    # -------------------------------------------------------------------------
    # Daily Activity Data - /v2/usercollection/daily_activity
    # -------------------------------------------------------------------------

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily activity data from Oura API."""
        params = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/daily_activity", params)

    def _normalize_activity_scores(
        self,
        activity_items: list[OuraDailyActivityJSON],
        user_id: UUID,
    ) -> list[HealthScoreCreate]:
        """Normalize Oura daily activity scores to HealthScoreCreate."""
        result = []
        for activity in activity_items:
            if activity.score is None:
                continue

            timestamp_str = activity.timestamp or (f"{activity.day}T00:00:00+00:00" if activity.day else None)
            if not timestamp_str:
                continue

            try:
                recorded_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            components = None
            if activity.contributors and isinstance(activity.contributors, dict):
                components = {
                    k: ScoreComponent(value=int(v)) for k, v in activity.contributors.items() if v is not None
                }

            result.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    category=HealthScoreCategory.ACTIVITY,
                    value=activity.score,
                    provider=ProviderName.OURA,
                    recorded_at=recorded_at,
                    components=components or None,
                )
            )
        return result

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> tuple[dict[str, list[dict[str, Any]]], list[HealthScoreCreate]]:  # type: ignore[override]
        """Normalize daily activity data into categorized samples and health scores."""
        activity_items = [OuraDailyActivityJSON(**item) for item in raw_samples]
        activity_scores = self._normalize_activity_scores(activity_items, user_id)

        result: dict[str, list[dict[str, Any]]] = {
            "steps": [],
            "energy": [],
            "distance": [],
        }

        for activity in activity_items:
            timestamp_str = activity.timestamp or (f"{activity.day}T00:00:00+00:00" if activity.day else None)
            if not timestamp_str:
                continue

            try:
                recorded_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            if activity.steps is not None:
                result["steps"].append({"recorded_at": recorded_at, "value": activity.steps})
            if activity.active_calories is not None:
                result["energy"].append({"recorded_at": recorded_at, "value": activity.active_calories})
            if activity.equivalent_walking_distance is not None:
                result["distance"].append({"recorded_at": recorded_at, "value": activity.equivalent_walking_distance})

        return result, activity_scores

    def save_activity_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized: tuple[dict[str, list[dict[str, Any]]], list[HealthScoreCreate]],
    ) -> int:
        """Save daily activity data as DataPointSeries and health scores."""
        activity_samples, health_scores = normalized
        type_map = {
            "steps": SeriesType.steps,
            "energy": SeriesType.energy,
            "distance": SeriesType.distance_walking_running,
        }

        samples: list[TimeSeriesSampleCreate] = []
        for key, series_type in type_map.items():
            for item in activity_samples.get(key, []):
                try:
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=item["recorded_at"],
                            value=Decimal(str(item["value"])),
                            series_type=series_type,
                        )
                    )
                except Exception as e:
                    log_structured(
                        self.logger,
                        "warning",
                        "Failed to save activity metric",
                        action="oura_activity_save_error",
                        metric=key,
                        error=str(e),
                    )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        if health_scores:
            health_score_service.bulk_create(db, health_scores)
            db.commit()
        return len(samples)

    # -------------------------------------------------------------------------
    # Cardiovascular age - /v2/usercollection/daily_cardiovascular_age
    # -------------------------------------------------------------------------

    def get_cardiovascular_age_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily cardiovascular age data from Oura API."""
        params = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/daily_cardiovascular_age", params)

    def normalize_cardiovascular_age_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[tuple[datetime, float]]:
        """Normalize daily cardiovascular age data into (recorded_at, value) pairs."""
        result: list[tuple[datetime, float]] = []

        for item in raw_samples:
            day = item.get("day")
            cardiovascular_age = item.get("vascular_age")

            if cardiovascular_age is None or not day:
                continue

            try:
                recorded_at = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                result.append((recorded_at, cardiovascular_age))
            except (ValueError, AttributeError):
                continue

        return result

    def save_cardiovascular_age_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized: list[tuple[datetime, float]],
    ) -> int:
        """Save daily cardiovascular age data as DataPointSeries."""
        samples: list[TimeSeriesSampleCreate] = []

        for recorded_at, value in normalized:
            try:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(value)),
                        series_type=SeriesType.cardiovascular_age,
                    )
                )
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    "Failed to save cardiovascular age data",
                    action="oura_cardiovascular_age_save_error",
                    error=str(e),
                )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Readiness Data
    # -------------------------------------------------------------------------

    def get_readiness_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily readiness (recovery) data from Oura API."""
        params = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/daily_readiness", params)

    def _normalize_readiness_scores(
        self,
        readiness: list[OuraDailyReadinessJSON],
        user_id: UUID,
    ) -> list[HealthScoreCreate]:
        """Normalize Oura readiness data to HealthScoreCreate."""
        scores = []
        for item in readiness:
            if item.score is None:
                continue

            recorded_at = None
            if item.timestamp:
                with suppress(ValueError, AttributeError):
                    recorded_at = datetime.fromisoformat(item.timestamp.replace("Z", "+00:00"))
            if recorded_at is None and item.day:
                with suppress(ValueError, AttributeError):
                    recorded_at = datetime.strptime(item.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)

            if recorded_at is None:
                continue

            components = None
            if item.contributors and isinstance(item.contributors, dict):
                components = {k: ScoreComponent(value=int(v)) for k, v in item.contributors.items() if v is not None}

            scores.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    category=HealthScoreCategory.READINESS,
                    value=item.score,
                    provider=ProviderName.OURA,
                    recorded_at=recorded_at,
                    components=components or None,
                )
            )
        return scores

    def normalize_readiness(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> tuple[list[dict[str, Any]], list[HealthScoreCreate]]:
        """Normalize Oura readiness data to internal schema."""
        readiness_items = [OuraDailyReadinessJSON(**item) for item in raw_items]
        recovery_metrics: list[dict[str, Any]] = []

        readiness_scores = self._normalize_readiness_scores(readiness_items, user_id)

        for readiness in readiness_items:
            timestamp = None
            if readiness.timestamp:
                try:
                    timestamp = datetime.fromisoformat(readiness.timestamp.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue
            elif readiness.day:
                try:
                    timestamp = datetime.strptime(readiness.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError):
                    continue

            if timestamp is None:
                continue

            recovery_metrics.append(
                {
                    "user_id": user_id,
                    "provider": self.provider_name,
                    "timestamp": timestamp,
                    "recovery_score": readiness.score,
                    "temperature_deviation": readiness.temperature_deviation,
                    "temperature_trend_deviation": readiness.temperature_trend_deviation,
                }
            )

        return recovery_metrics, readiness_scores

    def save_readiness_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized: tuple[list[dict[str, Any]], list[HealthScoreCreate]],
    ) -> int:
        """Save normalized readiness data as DataPointSeries and health scores."""
        recovery_metrics, health_scores = normalized

        metrics = [
            ("recovery_score", SeriesType.recovery_score),
            ("temperature_deviation", SeriesType.skin_temperature_deviation),
            ("temperature_trend_deviation", SeriesType.skin_temperature_trend_deviation),
        ]

        samples: list[TimeSeriesSampleCreate] = []
        for normalized_readiness in recovery_metrics:
            timestamp = normalized_readiness.get("timestamp")
            if not timestamp:
                continue
            for field_name, series_type in metrics:
                value = normalized_readiness.get(field_name)
                if value is not None:
                    try:
                        samples.append(
                            TimeSeriesSampleCreate(
                                id=uuid4(),
                                user_id=user_id,
                                source=self.provider_name,
                                recorded_at=timestamp,
                                value=Decimal(str(value)),
                                series_type=series_type,
                            )
                        )
                    except Exception as e:
                        log_structured(
                            self.logger,
                            "warning",
                            "Failed to save readiness metric",
                            action="oura_readiness_save_error",
                            field=field_name,
                            error=str(e),
                        )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        if health_scores:
            health_score_service.bulk_create(db, health_scores)
            db.commit()
        return len(samples)

    # -------------------------------------------------------------------------
    # Sleep Data
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch sleep data from Oura API."""
        params = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/sleep", params)

    def _extract_sleep_stages(self, sleep_phase_5_min: str | None, sleep_start: str | None) -> list[SleepStage]:
        """Convert Oura's 5-minute sleep phase string into list of SleepStage."""
        if not (sleep_phase_5_min and sleep_start):
            return []

        stages: list[SleepStage] = []

        phase_start = datetime.fromisoformat(sleep_start.replace("Z", "+00:00"))

        for stage, group in groupby(sleep_phase_5_min, lambda x: SLEEP_PHASE_MAP.get(x, SleepStageType.UNKNOWN)):
            occurrences = len(list(group))
            stages.append(
                SleepStage(
                    stage=stage, start_time=phase_start, end_time=phase_start + timedelta(minutes=5 * occurrences)
                )
            )
            phase_start += timedelta(minutes=5 * occurrences)

        return stages

    def normalize_sleeps(
        self,
        raw_sleep: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Normalize Oura sleep data to internal schema."""
        result = []
        for item in raw_sleep:
            sleep = OuraSleepJSON(**item)

            start_time = sleep.bedtime_start
            end_time = sleep.bedtime_end

            # Oura provides durations in seconds
            duration_seconds = sleep.time_in_bed or 0
            deep_seconds = sleep.deep_sleep_duration or 0
            light_seconds = sleep.light_sleep_duration or 0
            rem_seconds = sleep.rem_sleep_duration or 0
            awake_seconds = sleep.awake_time or 0

            # If duration is 0 but we have start/end, calculate
            if duration_seconds == 0 and start_time and end_time:
                try:
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    duration_seconds = int((end_dt - start_dt).total_seconds())
                except (ValueError, AttributeError):
                    pass

            sleep_stages = self._extract_sleep_stages(sleep.sleep_phase_5_min, start_time)

            internal_id = uuid4()

            result.append(
                {
                    "id": internal_id,
                    "user_id": user_id,
                    "provider": self.provider_name,
                    "timestamp": start_time or end_time,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_seconds": duration_seconds,
                    "efficiency_percent": float(sleep.efficiency) if sleep.efficiency is not None else None,
                    "is_nap": sleep.type == "rest",
                    "stages": {
                        "deep_seconds": deep_seconds,
                        "light_seconds": light_seconds,
                        "rem_seconds": rem_seconds,
                        "awake_seconds": awake_seconds,
                    },
                    "stage_timestamps": sleep_stages,
                    "average_heart_rate": sleep.average_heart_rate,
                    "average_hrv": sleep.average_hrv,
                    "lowest_heart_rate": sleep.lowest_heart_rate,
                    "heart_rate": sleep.heart_rate,
                    "hrv": sleep.hrv,
                    "oura_sleep_id": sleep.id,
                    "raw": raw_sleep,
                }
            )
        return result

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_items: list[dict[str, Any]],
    ) -> int:
        """Save normalized sleep data to database as EventRecord with SleepDetails."""
        count = 0
        for normalized_sleep in normalized_items:
            sleep_id = normalized_sleep["id"]

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
                log_structured(
                    self.logger,
                    "warning",
                    "Skipping sleep record: missing start/end time",
                    action="oura_sleep_skip",
                    sleep_id=str(sleep_id),
                )
                continue

            record = EventRecordCreate(
                id=sleep_id,
                category="sleep",
                type="sleep_session",
                source_name="Oura",
                device_model=None,
                duration_seconds=normalized_sleep.get("duration_seconds"),
                start_datetime=start_dt,
                end_datetime=end_dt,
                external_id=str(normalized_sleep.get("oura_sleep_id"))
                if normalized_sleep.get("oura_sleep_id")
                else None,
                source=self.provider_name,
                user_id=user_id,
            )

            stages = normalized_sleep.get("stages", {})
            total_sleep_seconds = (
                stages.get("deep_seconds", 0) + stages.get("light_seconds", 0) + stages.get("rem_seconds", 0)
            )
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
                sleep_stages=normalized_sleep.get("stage_timestamps", []),
            )

            try:
                event_record_service.create_or_merge_sleep(db, user_id, record, detail, settings.sleep_end_gap_minutes)
                count += 1
            except Exception as e:
                log_structured(
                    self.logger,
                    "error",
                    "Error saving sleep record",
                    action="oura_sleep_save_error",
                    sleep_id=str(sleep_id),
                    error=str(e),
                )

            hr: OuraIntervalData | None = normalized_sleep.get("heart_rate")
            hrv: OuraIntervalData | None = normalized_sleep.get("hrv")

            for interval_data, series_type, action in (
                (hr, SeriesType.heart_rate, "oura_sleep_hr_save_error"),
                (hrv, SeriesType.heart_rate_variability_sdnn, "oura_hrv_save_error"),
            ):
                if not (interval_data and interval_data.timestamp and interval_data.interval and interval_data.items):
                    continue
                try:
                    start = datetime.fromisoformat(interval_data.timestamp.replace("Z", "+00:00"))
                    samples = [
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=start + timedelta(seconds=interval_data.interval * i),
                            value=Decimal(str(value)),
                            series_type=series_type,
                        )
                        for i, value in enumerate(interval_data.items)
                        if value is not None
                    ]
                    if samples:
                        timeseries_service.bulk_create_samples(db, samples)
                except Exception as e:
                    log_structured(
                        self.logger,
                        "warning",
                        "Failed to save interval timeseries",
                        action=action,
                        sleep_id=str(sleep_id),
                        error=str(e),
                    )

        return count

    # -------------------------------------------------------------------------
    # Daily Sleep Score - /v2/usercollection/daily_sleep
    # -------------------------------------------------------------------------

    def get_daily_sleep_score_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily sleep scores from Oura API."""
        params = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/daily_sleep", params)

    def normalize_daily_sleep_scores(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[HealthScoreCreate]:
        """Normalize Oura daily sleep scores to HealthScoreCreate."""
        result = []
        for item in raw_items:
            sleep = OuraDailySleepJSON(**item)

            if sleep.score is None:
                continue

            recorded_at = None
            if sleep.timestamp:
                with suppress(ValueError, AttributeError):
                    recorded_at = datetime.fromisoformat(sleep.timestamp.replace("Z", "+00:00"))
            if recorded_at is None and sleep.day:
                with suppress(ValueError, AttributeError):
                    recorded_at = datetime.strptime(sleep.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)

            if recorded_at is None:
                continue

            components = None
            if sleep.contributors and isinstance(sleep.contributors, dict):
                components = {k: ScoreComponent(value=int(v)) for k, v in sleep.contributors.items() if v is not None}

            result.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    category=HealthScoreCategory.SLEEP,
                    value=sleep.score,
                    provider=ProviderName.OURA,
                    recorded_at=recorded_at,
                    components=components or None,
                )
            )
        return result

    def save_daily_sleep_scores(
        self,
        db: DbSession,
        user_id: UUID,
        normalized: list[HealthScoreCreate],
    ) -> int:
        """Save daily sleep scores via health_score_service."""
        if normalized:
            health_score_service.bulk_create(db, normalized)
            db.commit()
        return len(normalized)

    # -------------------------------------------------------------------------
    # Daily SpO2 Data
    # -------------------------------------------------------------------------

    def get_spo2_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily SpO2 data from Oura API."""
        params = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/daily_spo2", params)

    def save_spo2_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_data: list[dict[str, Any]],
    ) -> int:
        """Save SpO2 data as DataPointSeries."""
        samples: list[TimeSeriesSampleCreate] = []
        for item in raw_data:
            day = item.get("day")
            if not day:
                continue

            try:
                recorded_at = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue

            spo2_pct = item.get("spo2_percentage")
            avg_spo2 = spo2_pct.get("average") if isinstance(spo2_pct, dict) else None
            if avg_spo2 is not None:
                try:
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=recorded_at,
                            value=Decimal(str(avg_spo2)),
                            series_type=SeriesType.oxygen_saturation,
                        )
                    )
                except Exception as e:
                    log_structured(
                        self.logger,
                        "warning",
                        "Failed to save SpO2 data",
                        action="oura_spo2_save_error",
                        error=str(e),
                    )

            bdi = item.get("breathing_disturbance_index")
            if bdi is not None:
                try:
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            recorded_at=recorded_at,
                            value=Decimal(str(bdi)),
                            series_type=SeriesType.breathing_disturbance_index,
                        )
                    )
                except Exception as e:
                    log_structured(
                        self.logger,
                        "warning",
                        "Failed to save breathing disturbance index",
                        action="oura_bdi_save_error",
                        error=str(e),
                    )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Heart Rate Data
    # -------------------------------------------------------------------------

    def get_heart_rate_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch heart rate data from Oura API. Uses start_datetime/end_datetime (ISO 8601).

        Oura limits the timerange to 30 days per request; chunk accordingly.
        """
        _CHUNK_DAYS = 30  # noqa: N806
        results: list[dict[str, Any]] = []
        chunk_start = start_time.astimezone(timezone.utc)
        end_utc = end_time.astimezone(timezone.utc)
        while chunk_start < end_utc:
            chunk_end = min(chunk_start + timedelta(days=_CHUNK_DAYS), end_utc)
            params = {
                "start_datetime": chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_datetime": chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            results.extend(self._paginate(db, user_id, "/v2/usercollection/heartrate", params))
            chunk_start = chunk_end
        return results

    def save_heart_rate_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_data: list[dict[str, Any]],
    ) -> int:
        """Save heart rate samples as DataPointSeries."""
        samples: list[TimeSeriesSampleCreate] = []
        for item in raw_data:
            bpm = item.get("bpm")
            timestamp_str = item.get("timestamp")
            if bpm is None or not timestamp_str:
                continue

            try:
                recorded_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(bpm)),
                        series_type=SeriesType.heart_rate,
                    )
                )
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    "Failed to save HR sample",
                    action="oura_hr_save_error",
                    error=str(e),
                )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Personal Info Data (age, height, weight, etc.) - /v2/usercollection/personal_info
    # -------------------------------------------------------------------------

    def get_personal_info(
        self,
        db: DbSession,
        user_id: UUID,
    ) -> dict[str, Any]:
        """Fetch personal info data from Oura API."""
        return self._make_api_request(db, user_id, "/v2/usercollection/personal_info") or {}

    def normalize_personal_info(
        self,
        raw_info: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize personal info data."""
        try:
            personal_info = OuraPersonalInfoJSON(**raw_info)
            return {
                "weight": personal_info.weight,
                "height": personal_info.height,
            }
        except Exception as e:
            log_structured(
                self.logger,
                "warning",
                "Failed to normalize personal info",
                action="oura_personal_info_normalization_error",
                error=str(e),
            )
            return {}

    def save_personal_info(
        self,
        db: DbSession,
        user_id: UUID,
        raw_data: dict[str, Any],
    ) -> int:
        """Save personal info (weight, height) as DataPointSeries.

        Only saves when the value has changed from the most recent stored entry.
        """
        normalized = self.normalize_personal_info(raw_data, user_id)
        if not normalized:
            return 0

        now = datetime.now(timezone.utc)
        latest = timeseries_service.crud.get_latest_values_for_types(
            db, user_id, before_date=now, series_types=[SeriesType.weight, SeriesType.height]
        )

        samples: list[TimeSeriesSampleCreate] = []

        if (weight := normalized.get("weight")) is not None:
            new_weight = Decimal(str(weight))
            latest_weight = latest.get(SeriesType.weight)
            if latest_weight is None or abs(Decimal(str(latest_weight[0])) - new_weight) > Decimal("0.01"):
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=now,
                        value=new_weight,
                        series_type=SeriesType.weight,
                    )
                )

        if (height := normalized.get("height")) is not None:
            new_height = Decimal(str(round(height * 100, 2)))  # meters → cm
            latest_height = latest.get(SeriesType.height)
            if latest_height is None or abs(Decimal(str(latest_height[0])) - new_height) > Decimal("0.01"):
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=now,
                        value=new_height,
                        series_type=SeriesType.height,
                    )
                )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Daily Vo2 Data
    # -------------------------------------------------------------------------

    def get_vo2_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily Vo2 data from Oura API."""
        params = {
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/vO2_max", params)

    def save_vo2_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_data: list[dict[str, Any]],
    ) -> int:
        """Save Vo2 data as DataPointSeries."""
        samples: list[TimeSeriesSampleCreate] = []
        for item in raw_data:
            vo2_max = item.get("vo2_max")
            timestamp = item.get("timestamp")
            if not vo2_max or not timestamp:
                continue

            try:
                recorded_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        value=Decimal(str(vo2_max)),
                        series_type=SeriesType.vo2_max,
                    )
                )
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    "Failed to save Vo2 data",
                    action="oura_vo2_save_error",
                    error=str(e),
                )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

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
        """Load and save all 247 data types.

        Args:
            db: Database session
            user_id: User UUID
            start_time: Start of date range (defaults to 30 days ago)
            end_time: End of date range (defaults to now)
            is_first_sync: Whether this is the first sync (unused, for API compatibility)
        """
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        tasks: dict[str, Callable[[], int]] = {
            "activity": lambda: self.save_activity_data(
                db,
                user_id,
                self.normalize_activity_samples(self.get_activity_samples(db, user_id, start_time, end_time), user_id),
            ),
            "cardiovascular_age": lambda: self.save_cardiovascular_age_data(
                db,
                user_id,
                self.normalize_cardiovascular_age_samples(
                    self.get_cardiovascular_age_samples(db, user_id, start_time, end_time), user_id
                ),
            ),
            "readiness": lambda: self.save_readiness_data(
                db,
                user_id,
                self.normalize_readiness(self.get_readiness_data(db, user_id, start_time, end_time), user_id),
            ),
            "sleep": lambda: self.save_sleep_data(
                db, user_id, self.normalize_sleeps(self.get_sleep_data(db, user_id, start_time, end_time), user_id)
            ),
            "sleep_score": lambda: self.save_daily_sleep_scores(
                db,
                user_id,
                self.normalize_daily_sleep_scores(
                    self.get_daily_sleep_score_data(db, user_id, start_time, end_time), user_id
                ),
            ),
            "spo2": lambda: self.save_spo2_data(db, user_id, self.get_spo2_data(db, user_id, start_time, end_time)),
            "heart_rate": lambda: self.save_heart_rate_data(
                db, user_id, self.get_heart_rate_data(db, user_id, start_time, end_time)
            ),
            "personal_info": lambda: self.save_personal_info(db, user_id, self.get_personal_info(db, user_id)),
            "vo2_max": lambda: self.save_vo2_data(db, user_id, self.get_vo2_data(db, user_id, start_time, end_time)),
        }

        results: dict[str, int] = {}
        for data_type, fn in tasks.items():
            try:
                results[data_type] = fn()
            except Exception as e:
                results[data_type] = 0
                log_structured(
                    self.logger,
                    "error",
                    f"Failed to sync {data_type} data",
                    action="oura_sync_error",
                    data_type=data_type,
                    user_id=str(user_id),
                    error=str(e),
                )

        return results

    # -------------------------------------------------------------------------
    # Base class stubs — these abstract methods don't map to Oura's API.
    # Oura uses provider-specific endpoints (readiness, daily_activity, etc.)
    # rather than the generic recovery/daily_activity_statistics shape the base
    # class assumes. Implemented as no-ops to satisfy ABC instantiation.
    # -------------------------------------------------------------------------

    def normalize_sleep(self, raw_sleep: dict, user_id: UUID) -> dict:
        return {}

    def get_recovery_data(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict]:
        return []

    def normalize_recovery(self, raw_recovery: dict, user_id: UUID) -> dict:
        return {}

    def get_daily_activity_statistics(
        self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        return []

    def normalize_daily_activity(self, raw_stats: dict, user_id: UUID) -> dict:
        return {}
