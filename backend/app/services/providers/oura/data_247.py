"""Oura Ring 247 Data implementation for sleep, readiness, heart rate, activity, and SpO2."""

from contextlib import suppress
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import DataSource, EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_source_repository import DataSourceRepository  # noqa: F401
from app.schemas import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.oura.imports import (
    OuraDailyActivityJSON,
    OuraDailyReadinessJSON,
    OuraSleepJSON,
)
from app.schemas.series_types import SeriesType
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service


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
        """Generic paginator for Oura API endpoints that return {data: [...], next_token: ...}."""
        all_data: list[dict[str, Any]] = []
        next_token: str | None = None

        while True:
            request_params = {**params}
            if next_token:
                request_params["next_token"] = next_token

            try:
                response = self._make_api_request(db, user_id, endpoint, params=request_params)

                data = response.get("data", []) if isinstance(response, dict) else []
                all_data.extend(data)

                next_token = response.get("next_token") if isinstance(response, dict) else None
                if not data or not next_token:
                    break

            except Exception as e:
                self.logger.error(f"Error fetching {endpoint}: {e}")
                if all_data:
                    self.logger.warning(f"Returning partial data from {endpoint} due to error: {e}")
                    break
                raise

        return all_data

    # -------------------------------------------------------------------------
    # Sleep Data - /v2/usercollection/sleep
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

    def normalize_sleep(
        self,
        raw_sleep: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Oura sleep data to internal schema."""
        sleep = OuraSleepJSON(**raw_sleep)

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

        internal_id = uuid4()
        with suppress(ValueError, TypeError):
            internal_id = UUID(sleep.id)

        return {
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
            "average_heart_rate": sleep.average_heart_rate,
            "average_hrv": sleep.average_hrv,
            "lowest_heart_rate": sleep.lowest_heart_rate,
            "oura_sleep_id": sleep.id,
            "raw": raw_sleep,
        }

    def save_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_sleep: dict[str, Any],
    ) -> None:
        """Save normalized sleep data to database as EventRecord with SleepDetails."""
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
            self.logger.warning(f"Skipping sleep record {sleep_id}: missing start/end time")
            return

        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Oura",
            device_model=None,
            duration_seconds=normalized_sleep.get("duration_seconds"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            external_id=str(normalized_sleep.get("oura_sleep_id")) if normalized_sleep.get("oura_sleep_id") else None,
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
        )

        try:
            created_record = event_record_service.create(db, record)
            detail.record_id = created_record.id
            event_record_service.create_detail(db, detail, detail_type="sleep")
        except Exception as e:
            self.logger.error(f"Error saving sleep record {sleep_id}: {e}")

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

    # -------------------------------------------------------------------------
    # Recovery / Readiness Data - /v2/usercollection/daily_readiness
    # -------------------------------------------------------------------------

    def get_recovery_data(
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

    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize Oura readiness data to internal schema."""
        readiness = OuraDailyReadinessJSON(**raw_recovery)

        timestamp = None
        if readiness.timestamp:
            try:
                timestamp = datetime.fromisoformat(readiness.timestamp.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)
        elif readiness.day:
            try:
                timestamp = datetime.strptime(readiness.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

        return {
            "user_id": user_id,
            "provider": self.provider_name,
            "timestamp": timestamp,
            "recovery_score": readiness.score,
            "temperature_deviation": readiness.temperature_deviation,
            "raw": raw_recovery,
        }

    def save_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized_recovery: dict[str, Any],
    ) -> int:
        """Save normalized readiness data as DataPointSeries."""
        if not normalized_recovery:
            return 0

        timestamp = normalized_recovery.get("timestamp")
        if not timestamp:
            return 0

        count = 0

        # Map Oura readiness fields to SeriesType
        metrics = [
            ("recovery_score", SeriesType.recovery_score),
            ("temperature_deviation", SeriesType.body_temperature),
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
                    self.logger.warning(f"Failed to save readiness {field_name}: {e}")

        return count

    def load_and_save_recovery(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Load readiness data from API and save to database."""
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
    # Heart Rate Data - /v2/usercollection/heartrate
    # -------------------------------------------------------------------------

    def get_heart_rate_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch heart rate data from Oura API. Uses start_datetime/end_datetime (ISO 8601)."""
        params = {
            "start_datetime": start_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_datetime": end_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        return self._paginate(db, user_id, "/v2/usercollection/heartrate", params)

    def save_heart_rate_data(
        self,
        db: DbSession,
        user_id: UUID,
        raw_data: list[dict[str, Any]],
    ) -> int:
        """Save heart rate samples as DataPointSeries."""
        count = 0
        for item in raw_data:
            bpm = item.get("bpm")
            timestamp_str = item.get("timestamp")
            if bpm is None or not timestamp_str:
                continue

            try:
                recorded_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(bpm)),
                    series_type=SeriesType.heart_rate,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save HR sample: {e}")

        return count

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

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Normalize daily activity data into categorized samples."""
        result: dict[str, list[dict[str, Any]]] = {
            "steps": [],
            "energy": [],
            "distance": [],
        }

        for item in raw_samples:
            activity = OuraDailyActivityJSON(**item)
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

        return result

    def save_activity_data(
        self,
        db: DbSession,
        user_id: UUID,
        normalized: dict[str, list[dict[str, Any]]],
    ) -> int:
        """Save daily activity data as DataPointSeries."""
        count = 0

        type_map = {
            "steps": SeriesType.steps,
            "energy": SeriesType.energy,
            "distance": SeriesType.distance_walking_running,
        }

        for key, series_type in type_map.items():
            for item in normalized.get(key, []):
                try:
                    sample = TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        recorded_at=item["recorded_at"],
                        value=Decimal(str(item["value"])),
                        series_type=series_type,
                    )
                    timeseries_service.crud.create(db, sample)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to save activity {key}: {e}")

        return count

    # -------------------------------------------------------------------------
    # Daily SpO2 Data - /v2/usercollection/daily_spo2
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
        count = 0
        for item in raw_data:
            spo2_pct = item.get("spo2_percentage")
            day = item.get("day")
            if not spo2_pct or not day:
                continue

            # spo2_percentage is a dict with "average" key
            avg_spo2 = spo2_pct.get("average") if isinstance(spo2_pct, dict) else None
            if avg_spo2 is None:
                continue

            try:
                recorded_at = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    recorded_at=recorded_at,
                    value=Decimal(str(avg_spo2)),
                    series_type=SeriesType.oxygen_saturation,
                )
                timeseries_service.crud.create(db, sample)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save SpO2: {e}")

        return count

    # -------------------------------------------------------------------------
    # Daily Activity Statistics (required by base class)
    # -------------------------------------------------------------------------

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch daily activity - delegates to get_activity_samples."""
        return self.get_activity_samples(db, user_id, start_date, end_date)

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        """Normalize single daily activity record."""
        activity = OuraDailyActivityJSON(**raw_stats)
        return {
            "day": activity.day,
            "steps": activity.steps,
            "active_calories": activity.active_calories,
            "distance": activity.equivalent_walking_distance,
            "score": activity.score,
        }

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

        results = {
            "sleep_sessions_synced": 0,
            "recovery_samples_synced": 0,
            "activity_samples_synced": 0,
            "heart_rate_samples_synced": 0,
            "spo2_samples_synced": 0,
        }

        try:
            results["sleep_sessions_synced"] = self.load_and_save_sleep(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync sleep data: {e}")

        try:
            results["recovery_samples_synced"] = self.load_and_save_recovery(db, user_id, start_time, end_time)
        except Exception as e:
            self.logger.error(f"Failed to sync readiness data: {e}")

        try:
            raw_activity = self.get_activity_samples(db, user_id, start_time, end_time)
            normalized_activity = self.normalize_activity_samples(raw_activity, user_id)
            results["activity_samples_synced"] = self.save_activity_data(db, user_id, normalized_activity)
        except Exception as e:
            self.logger.error(f"Failed to sync activity data: {e}")

        try:
            raw_hr = self.get_heart_rate_data(db, user_id, start_time, end_time)
            results["heart_rate_samples_synced"] = self.save_heart_rate_data(db, user_id, raw_hr)
        except Exception as e:
            self.logger.error(f"Failed to sync heart rate data: {e}")

        try:
            raw_spo2 = self.get_spo2_data(db, user_id, start_time, end_time)
            results["spo2_samples_synced"] = self.save_spo2_data(db, user_id, raw_spo2)
        except Exception as e:
            self.logger.error(f"Failed to sync SpO2 data: {e}")

        return results
