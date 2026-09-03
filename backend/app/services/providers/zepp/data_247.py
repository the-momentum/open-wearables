from __future__ import annotations

import base64
import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.config import settings
from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.repositories.data_point_series_repository import WriteCounts
from app.schemas.auth import ConnectionStatus
from app.schemas.enums import HealthScoreCategory, ProviderName, SeriesType
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    HealthScoreCreate,
    TimeSeriesSampleCreate,
)
from app.services.event_record_service import event_record_service
from app.services.health_score_service import health_score_service
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.zepp.client import DEFAULT_HOST, ZeppAuthExpiredError, ZeppClient
from app.services.timeseries_service import timeseries_service
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


def _decode_band_summary(summary_b64: Any) -> dict[str, Any] | None:
    """Safely decode Base64 JSON summary from band_data.json."""
    if not isinstance(summary_b64, str) or not summary_b64:
        return None
    try:
        decoded = base64.b64decode(summary_b64).decode("utf-8")
        parsed = json.loads(decoded)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


class Zepp247Data(Base247DataTemplate):
    """Zepp implementation of 247 continuous data (sleep, activity, biometrics, health scores)."""

    def __init__(
        self,
        provider_name: str = ProviderName.ZEPP.value,
        api_base_url: str = "",
        oauth: Any = None,
    ) -> None:
        super().__init__(provider_name, api_base_url, oauth)
        self.connection_repo = UserConnectionRepository()
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.logger = logger

    def _get_client(self, db: DbSession, user_id: UUID) -> tuple[ZeppClient | None, Any | None]:
        """Resolve active user connection and initialize ZeppClient."""
        conn = self.connection_repo.get_active_connection(db, user_id, self.provider_name)
        if not conn or not conn.access_token or not conn.provider_user_id:
            return None, conn

        client = ZeppClient(
            apptoken=conn.access_token,
            user_id=conn.provider_user_id,
            host=conn.refresh_token or DEFAULT_HOST,
        )
        return client, conn

    def _handle_auth_expired(self, db: DbSession, conn: Any) -> None:
        """Transition connection to EXPIRED when tokens are rejected."""
        if conn:
            conn.status = ConnectionStatus.EXPIRED
            conn.updated_at = datetime.now(timezone.utc)
            db.add(conn)
            db.commit()
            log_structured(
                self.logger,
                "warning",
                "Zepp credentials expired or unauthorized; connection marked as EXPIRED",
                user_id=str(conn.user_id),
                provider=self.provider_name,
            )

    # -------------------------------------------------------------------------
    # Base247DataTemplate Abstract Method Implementations
    # -------------------------------------------------------------------------

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        client, conn = self._get_client(db, user_id)
        if not client:
            return []
        try:
            with client:
                res = client.get_band_data(start_time.date(), end_time.date(), query_type="summary")
                data = res.get("data") if isinstance(res, dict) else None
                return data if isinstance(data, list) else []
        except ZeppAuthExpiredError:
            self._handle_auth_expired(db, conn)
            raise
        except Exception as exc:
            self.logger.error("Failed to fetch sleep data: %s", exc)
            return []

    def normalize_sleep(self, raw_sleep: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        return raw_sleep

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        return []

    def normalize_recovery(self, raw_recovery: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        return raw_recovery

    def get_activity_samples(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        return []

    def normalize_activity_samples(
        self,
        raw_samples: list[dict[str, Any]],
        user_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        return {}

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        return []

    def normalize_daily_activity(
        self,
        raw_stats: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        return raw_stats

    # -------------------------------------------------------------------------
    # Main Ingestion & Persistence Method: load_and_save_all
    # -------------------------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, Any]:
        """Fetch, decode and persist all 24/7 metrics, sleep sessions and health scores from Zepp."""
        client, conn = self._get_client(db, user_id)
        if not client:
            return {
                "sleep_sessions_synced": WriteCounts(0, 0),
                "activity_samples": WriteCounts(0, 0),
            }

        # Date normalization
        if isinstance(end_time, str):
            try:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                end_dt = datetime.now(timezone.utc)
        elif isinstance(end_time, datetime):
            end_dt = end_time
        else:
            end_dt = datetime.now(timezone.utc)

        if isinstance(start_time, str):
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                start_dt = end_dt - timedelta(days=30)
        elif isinstance(start_time, datetime):
            start_dt = start_time
        else:
            start_dt = end_dt - timedelta(days=30)

        from_date = start_dt.date()
        to_date = end_dt.date()
        from_ms = int(start_dt.timestamp() * 1000)
        to_ms = int(end_dt.timestamp() * 1000)
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        samples: list[TimeSeriesSampleCreate] = []
        health_scores: list[HealthScoreCreate] = []
        sleep_saved_count = 0

        with client:
            # 1. Band Data: Sleep sessions, daily steps, daily distance and daily calories
            try:
                band_res = client.get_band_data(from_date, to_date, query_type="summary")
                entries = band_res.get("data") if isinstance(band_res, dict) else None
                if isinstance(entries, list):
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        summary = _decode_band_summary(entry.get("summary"))
                        if not summary:
                            continue

                        # Extract Sleep
                        sleep_info = summary.get("slp")
                        if isinstance(sleep_info, dict):
                            st = sleep_info.get("st")
                            ed = sleep_info.get("ed")
                            dp = sleep_info.get("dp") or 0
                            lt = sleep_info.get("lt") or 0
                            rem = sleep_info.get("dt") or sleep_info.get("rem") or 0
                            wk = sleep_info.get("wk") or 0
                            rhr = sleep_info.get("rhr")

                            total_sleep_min = dp + lt + rem
                            if total_sleep_min > 0 and st and ed and ed > st:
                                start_sleep_dt = datetime.fromtimestamp(st, tz=timezone.utc)
                                end_sleep_dt = datetime.fromtimestamp(ed, tz=timezone.utc)
                                time_in_bed_min = round((ed - st) / 60)

                                record_id = uuid4()
                                record = EventRecordCreate(
                                    id=record_id,
                                    user_id=user_id,
                                    provider=ProviderName.ZEPP,
                                    category="sleep",
                                    source_name="zepp",
                                    source="zepp",
                                    duration_seconds=total_sleep_min * 60,
                                    start_datetime=start_sleep_dt,
                                    end_datetime=end_sleep_dt,
                                )
                                detail = EventRecordDetailCreate(
                                    record_id=record_id,
                                    sleep_total_duration_minutes=total_sleep_min,
                                    sleep_time_in_bed_minutes=time_in_bed_min,
                                    sleep_deep_minutes=dp,
                                    sleep_light_minutes=lt,
                                    sleep_rem_minutes=rem,
                                    sleep_awake_minutes=wk,
                                )
                                event_record_service.create_or_merge_sleep(
                                    db,
                                    user_id,
                                    record,
                                    detail,
                                    settings.sleep_end_gap_minutes,
                                )
                                sleep_saved_count += 1

                                if rhr and isinstance(rhr, (int, float)) and 30 <= rhr <= 220:
                                    samples.append(
                                        TimeSeriesSampleCreate(
                                            id=uuid4(),
                                            user_id=user_id,
                                            provider=self.provider_name,
                                            recorded_at=start_sleep_dt,
                                            value=Decimal(str(rhr)),
                                            series_type=SeriesType.resting_heart_rate,
                                        )
                                    )

                        # Extract Steps, Distance and Energy
                        step_info = summary.get("stp")
                        if isinstance(step_info, dict):
                            date_str = str(entry.get("date_time") or entry.get("date") or "")
                            try:
                                day_d = date.fromisoformat(date_str[:10])
                                day_dt = datetime.combine(day_d, datetime.min.time(), tzinfo=timezone.utc)
                            except (ValueError, AttributeError):
                                day_dt = datetime.now(timezone.utc)

                            ttl_steps = step_info.get("ttl")
                            if ttl_steps is not None and ttl_steps > 0:
                                samples.append(
                                    TimeSeriesSampleCreate(
                                        id=uuid4(),
                                        user_id=user_id,
                                        provider=self.provider_name,
                                        recorded_at=day_dt,
                                        value=Decimal(str(ttl_steps)),
                                        series_type=SeriesType.steps,
                                        is_daily_total=True,
                                    )
                                )

                            dis_meters = step_info.get("dis")
                            if dis_meters is not None and dis_meters > 0:
                                samples.append(
                                    TimeSeriesSampleCreate(
                                        id=uuid4(),
                                        user_id=user_id,
                                        provider=self.provider_name,
                                        recorded_at=day_dt,
                                        value=Decimal(str(dis_meters)),
                                        series_type=SeriesType.distance_walking_running,
                                        is_daily_total=True,
                                    )
                                )

                            cal = step_info.get("cal")
                            if cal is not None and cal > 0:
                                samples.append(
                                    TimeSeriesSampleCreate(
                                        id=uuid4(),
                                        user_id=user_id,
                                        provider=self.provider_name,
                                        recorded_at=day_dt,
                                        value=Decimal(str(cal)),
                                        series_type=SeriesType.energy,
                                        is_daily_total=True,
                                    )
                                )
            except ZeppAuthExpiredError:
                self._handle_auth_expired(db, conn)
                raise
            except Exception as exc:
                self.logger.warning("Error syncing Zepp band_data: %s", exc)

            # 2. Heart Rate minute-by-minute samples & resting heart rate
            try:
                hr_res = client.get_heart_rate(start_ts, end_ts)
                hr_items = hr_res.get("items") if isinstance(hr_res, dict) else None
                if isinstance(hr_items, list):
                    for it in hr_items:
                        if not isinstance(it, dict):
                            continue
                        ts = it.get("timestamp") or it.get("time")
                        if not ts:
                            continue
                        sample_dt = (
                            datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                            if ts > 10_000_000_000
                            else datetime.fromtimestamp(ts, tz=timezone.utc)
                        )

                        val = it.get("value")
                        if val is not None and isinstance(val, (int, float)) and 30 <= val <= 250:
                            is_rhr = it.get("type") == 1 or it.get("subType") == "resting"
                            samples.append(
                                TimeSeriesSampleCreate(
                                    id=uuid4(),
                                    user_id=user_id,
                                    provider=self.provider_name,
                                    recorded_at=sample_dt,
                                    value=Decimal(str(val)),
                                    series_type=SeriesType.resting_heart_rate if is_rhr else SeriesType.heart_rate,
                                )
                            )

                        # Parse minute heartRateData Base64 stream
                        raw_b64 = it.get("heartRateData")
                        if isinstance(raw_b64, str) and raw_b64:
                            try:
                                decoded_hr = base64.b64decode(raw_b64)
                                for idx, byte_val in enumerate(decoded_hr):
                                    if 30 <= byte_val <= 220:
                                        min_dt = sample_dt + timedelta(minutes=idx)
                                        samples.append(
                                            TimeSeriesSampleCreate(
                                                id=uuid4(),
                                                user_id=user_id,
                                                provider=self.provider_name,
                                                recorded_at=min_dt,
                                                value=Decimal(str(byte_val)),
                                                series_type=SeriesType.heart_rate,
                                            )
                                        )
                            except Exception:
                                pass
            except ZeppAuthExpiredError:
                self._handle_auth_expired(db, conn)
                raise
            except Exception as exc:
                self.logger.warning("Error syncing Zepp heart rate: %s", exc)

            # 3. Health Scores: Readiness & Sleep HRV
            try:
                rdns_res = client.get_events("readiness", "watch_score", from_ms, to_ms)
                rdns_items = rdns_res.get("items") if isinstance(rdns_res, dict) else None
                if isinstance(rdns_items, list):
                    for it in rdns_items:
                        if not isinstance(it, dict):
                            continue
                        val = it.get("value")
                        if not isinstance(val, dict):
                            continue
                        ts = it.get("timestamp") or val.get("timestamp") or 0
                        recorded_at = (
                            datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                            if ts > 10_000_000_000
                            else datetime.fromtimestamp(ts, tz=timezone.utc)
                        )

                        rdns_score = val.get("rdnsScore")
                        if rdns_score is not None and rdns_score != 255 and 0 <= rdns_score <= 100:
                            health_scores.append(
                                HealthScoreCreate(
                                    id=uuid4(),
                                    user_id=user_id,
                                    provider=ProviderName.ZEPP,
                                    category=HealthScoreCategory.READINESS,
                                    value=Decimal(str(rdns_score)),
                                    recorded_at=recorded_at,
                                )
                            )

                        sleep_hrv = val.get("sleepHRV")
                        if sleep_hrv is not None and sleep_hrv != 255 and sleep_hrv > 0:
                            samples.append(
                                TimeSeriesSampleCreate(
                                    id=uuid4(),
                                    user_id=user_id,
                                    provider=self.provider_name,
                                    recorded_at=recorded_at,
                                    value=Decimal(str(sleep_hrv)),
                                    series_type=SeriesType.heart_rate_variability_rmssd,
                                )
                            )
            except ZeppAuthExpiredError:
                self._handle_auth_expired(db, conn)
                raise
            except Exception as exc:
                self.logger.warning("Error syncing Zepp readiness: %s", exc)

            # 4. Health Scores: Stress
            try:
                stress_res = client.get_events("Charge", "stress_data", from_ms, to_ms)
                stress_items = stress_res.get("items") if isinstance(stress_res, dict) else None
                if isinstance(stress_items, list):
                    for it in stress_items:
                        if not isinstance(it, dict):
                            continue
                        val = it.get("value")
                        score = (
                            val.get("stress") or val.get("value") or val.get("score") if isinstance(val, dict) else val
                        )
                        ts = it.get("timestamp", 0)
                        if score is not None and isinstance(score, (int, float)) and 0 <= score <= 100:
                            recorded_at = (
                                datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                                if ts > 10_000_000_000
                                else datetime.fromtimestamp(ts, tz=timezone.utc)
                            )
                            health_scores.append(
                                HealthScoreCreate(
                                    id=uuid4(),
                                    user_id=user_id,
                                    provider=ProviderName.ZEPP,
                                    category=HealthScoreCategory.STRESS,
                                    value=Decimal(str(score)),
                                    recorded_at=recorded_at,
                                )
                            )
            except ZeppAuthExpiredError:
                self._handle_auth_expired(db, conn)
                raise
            except Exception as exc:
                self.logger.warning("Error syncing Zepp stress: %s", exc)

            # 5. Health Scores: Body Battery
            try:
                bb_res = client.get_events("Charge", "real_data", from_ms, to_ms)
                bb_items = bb_res.get("items") if isinstance(bb_res, dict) else None
                if isinstance(bb_items, list):
                    for it in bb_items:
                        if not isinstance(it, dict):
                            continue
                        val = it.get("value")
                        score = (
                            val.get("bodyBattery") or val.get("value") or val.get("score")
                            if isinstance(val, dict)
                            else val
                        )
                        ts = it.get("timestamp", 0)
                        if score is not None and isinstance(score, (int, float)) and 0 <= score <= 100:
                            recorded_at = (
                                datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                                if ts > 10_000_000_000
                                else datetime.fromtimestamp(ts, tz=timezone.utc)
                            )
                            health_scores.append(
                                HealthScoreCreate(
                                    id=uuid4(),
                                    user_id=user_id,
                                    provider=ProviderName.ZEPP,
                                    category=HealthScoreCategory.BODY_BATTERY,
                                    value=Decimal(str(score)),
                                    recorded_at=recorded_at,
                                )
                            )
            except ZeppAuthExpiredError:
                self._handle_auth_expired(db, conn)
                raise
            except Exception as exc:
                self.logger.warning("Error syncing Zepp body battery: %s", exc)

            # 6. Biometrics: VO2 Max
            try:
                vo2_res = client.get_vo2_max(from_date, to_date)
                vo2_items = vo2_res.get("items") if isinstance(vo2_res, dict) else None
                if isinstance(vo2_items, list):
                    for it in vo2_items:
                        if not isinstance(it, dict):
                            continue
                        vo2 = it.get("vo2Max")
                        day_id = str(it.get("dayId") or "")
                        if vo2 is not None and isinstance(vo2, (int, float)) and vo2 > 0:
                            try:
                                day_d = date.fromisoformat(day_id[:10])
                                day_dt = datetime.combine(day_d, datetime.min.time(), tzinfo=timezone.utc)
                            except (ValueError, AttributeError):
                                day_dt = datetime.now(timezone.utc)

                            samples.append(
                                TimeSeriesSampleCreate(
                                    id=uuid4(),
                                    user_id=user_id,
                                    provider=self.provider_name,
                                    recorded_at=day_dt,
                                    value=Decimal(str(vo2)),
                                    series_type=SeriesType.vo2_max,
                                    is_daily_total=True,
                                )
                            )
            except ZeppAuthExpiredError:
                self._handle_auth_expired(db, conn)
                raise
            except Exception as exc:
                self.logger.warning("Error syncing Zepp VO2 Max: %s", exc)

            # 7. Biometrics: SpO2
            try:
                spo2_res = client.get_user_events("blood_oxygen", from_ms, to_ms, sub_type="click")
                spo2_items = spo2_res.get("items") if isinstance(spo2_res, dict) else None
                if isinstance(spo2_items, list):
                    for it in spo2_items:
                        if not isinstance(it, dict):
                            continue
                        val = it.get("value")
                        spo2_val = val.get("bloodOxygen") or val.get("value") if isinstance(val, dict) else val
                        ts = it.get("timestamp", 0)
                        if spo2_val and isinstance(spo2_val, (int, float)) and 50 <= spo2_val <= 100:
                            recorded_at = (
                                datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                                if ts > 10_000_000_000
                                else datetime.fromtimestamp(ts, tz=timezone.utc)
                            )
                            samples.append(
                                TimeSeriesSampleCreate(
                                    id=uuid4(),
                                    user_id=user_id,
                                    provider=self.provider_name,
                                    recorded_at=recorded_at,
                                    value=Decimal(str(spo2_val)),
                                    series_type=SeriesType.oxygen_saturation,
                                )
                            )
            except ZeppAuthExpiredError:
                self._handle_auth_expired(db, conn)
                raise
            except Exception as exc:
                self.logger.warning("Error syncing Zepp SpO2: %s", exc)

            # 8. Biometrics: Weight & BMI
            try:
                weight_res = client.get_weight_records(start_ts, end_ts)
                weight_items = weight_res.get("items") if isinstance(weight_res, dict) else None
                if isinstance(weight_items, list):
                    for it in weight_items:
                        if not isinstance(it, dict):
                            continue
                        summary = it.get("summary")
                        if not isinstance(summary, dict):
                            continue
                        ts = it.get("timestamp") or it.get("createTime") or 0
                        recorded_at = (
                            datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                            if ts > 10_000_000_000
                            else datetime.fromtimestamp(ts, tz=timezone.utc)
                        )
                        w_val = summary.get("weight")
                        if w_val and isinstance(w_val, (int, float)) and w_val > 0:
                            samples.append(
                                TimeSeriesSampleCreate(
                                    id=uuid4(),
                                    user_id=user_id,
                                    provider=self.provider_name,
                                    recorded_at=recorded_at,
                                    value=Decimal(str(w_val)),
                                    series_type=SeriesType.weight,
                                )
                            )
                        bmi_val = summary.get("bmi")
                        if bmi_val and isinstance(bmi_val, (int, float)) and bmi_val > 0:
                            samples.append(
                                TimeSeriesSampleCreate(
                                    id=uuid4(),
                                    user_id=user_id,
                                    provider=self.provider_name,
                                    recorded_at=recorded_at,
                                    value=Decimal(str(bmi_val)),
                                    series_type=SeriesType.body_mass_index,
                                )
                            )
            except ZeppAuthExpiredError:
                self._handle_auth_expired(db, conn)
                raise
            except Exception as exc:
                self.logger.warning("Error syncing Zepp weight: %s", exc)

        # Save collected samples and health scores to database
        activity_inserted = 0
        activity_updated = 0
        if samples:
            try:
                counts = timeseries_service.bulk_create_samples(db, samples)
                activity_inserted = getattr(counts, "inserted", 0)
                activity_updated = getattr(counts, "updated", 0)
            except Exception as exc:
                self.logger.error("Error bulk creating Zepp timeseries samples: %s", exc)

        if health_scores:
            try:
                health_score_service.bulk_create(db, health_scores)
            except Exception as exc:
                self.logger.error("Error bulk creating Zepp health scores: %s", exc)

        return {
            "sleep_sessions_synced": WriteCounts(sleep_saved_count, 0),
            "activity_samples": WriteCounts(activity_inserted, activity_updated),
        }
