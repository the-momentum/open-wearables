from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, TypeVar
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import HealthScoreCategory, ProviderName, SeriesType
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    HealthScoreCreate,
    ScoreComponent,
    SleepStage,
    TimeSeriesSampleCreate,
)
from app.schemas.providers.polar import (
    CardioLoadJSON,
    ContinuousHeartRateJSON,
    DailyActivityJSON,
    NightlyRechargeJSON,
    SleepJSON,
)
from app.schemas.providers.polar.elixir import (
    BodyTemperaturePeriodJSON,
    EcgTestResultJSON,
    SkinTemperatureJSON,
    Spo2TestResultJSON,
)
from app.schemas.providers.polar.elixir.body_temperature import TemperatureMeasurementType
from app.schemas.providers.polar.elixir.spo2 import Spo2TestStatus
from app.schemas.providers.polar.sleepwise import AlertnessJSON, CircadianBedtimeJSON
from app.schemas.providers.polar.sleepwise.alertness import GradeClassification, GradeType, SleepInertia
from app.schemas.providers.polar.sleepwise.circadian_bedtime import CircadianBedtimeQuality, CircadianBedtimeResultType
from app.services.event_record_service import event_record_service
from app.services.health_score_service import health_score_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.raw_payload_storage import store_raw_payload
from app.services.timeseries_service import timeseries_service
from app.utils.structured_logging import log_structured

_T = TypeVar("_T", bound=BaseModel)


class Polar247Data(Base247DataTemplate):
    _NIGHTLY_RECHARGE_STATUS_LABELS: dict[int, str] = {
        1: "very poor",
        2: "poor",
        3: "compromised",
        4: "ok",
        5: "good",
        6: "very good",
    }

    _ANS_CHARGE_STATUS_LABELS: dict[int, str] = {
        1: "much below usual",
        2: "below usual",
        3: "usual",
        4: "above usual",
        5: "much above usual",
    }

    _GRADE_CLASSIFICATION_LABELS: dict[GradeClassification, str] = {
        GradeClassification.WEAK: "weak",
        GradeClassification.FAIR: "fair",
        GradeClassification.STRONG: "strong",
        GradeClassification.EXCELLENT: "excellent",
    }

    _SLEEP_INERTIA_LABELS: dict[SleepInertia, str] = {
        SleepInertia.NO_INERTIA: "no inertia",
        SleepInertia.MILD: "mild",
        SleepInertia.MODERATE: "moderate",
        SleepInertia.HEAVY: "heavy",
    }

    _CIRCADIAN_QUALITY_VALUES: dict[CircadianBedtimeQuality, int] = {
        CircadianBedtimeQuality.WEAK: 1,
        CircadianBedtimeQuality.COMPROMISED: 2,
        CircadianBedtimeQuality.CLEARLY_RECOGNIZABLE: 3,
    }

    _CIRCADIAN_QUALITY_LABELS: dict[CircadianBedtimeQuality, str] = {
        CircadianBedtimeQuality.WEAK: "weak",
        CircadianBedtimeQuality.COMPROMISED: "compromised",
        CircadianBedtimeQuality.CLEARLY_RECOGNIZABLE: "clearly recognizable",
    }

    _BODY_TEMP_SERIES_TYPE: dict[TemperatureMeasurementType, SeriesType] = {
        TemperatureMeasurementType.SKIN_TEMPERATURE: SeriesType.skin_temperature,
        TemperatureMeasurementType.CORE_TEMPERATURE: SeriesType.body_temperature,
    }

    _HYPNOGRAM_STAGE_MAP: dict[int, SleepStageType] = {
        0: SleepStageType.AWAKE,
        1: SleepStageType.REM,
        2: SleepStageType.LIGHT,
        3: SleepStageType.LIGHT,
        4: SleepStageType.DEEP,
        5: SleepStageType.UNKNOWN,
    }

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ):
        super().__init__(provider_name, api_base_url, oauth)
        self.connection_repo = UserConnectionRepository()

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            result = make_authenticated_request(
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
            store_raw_payload(
                source="api_response",
                provider="polar",
                payload=result,
                user_id=str(user_id),
                trace_id=endpoint,
            )
            return result
        except HTTPException as e:
            # 404 = no data for this date / feature not available on this device
            if e.status_code == 404:
                return None
            # 204 No Content: api_client raises 500 wrapping a JSONDecodeError on empty body
            if e.status_code == 500 and "Expecting value" in str(e.detail):
                return None
            raise

    def _parse_time_key(self, key: str) -> time:
        parts = key.split(":")
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return time(h, m, s)

    def _hhmm_to_datetimes(
        self,
        items: dict[str, Any],
        anchor: datetime,
    ) -> list[tuple[datetime, Any]]:
        """Convert dict[HH:MM or HH:MM:SS, value] to [(datetime, value)], handling midnight crossover."""
        result: list[tuple[datetime, Any]] = []
        current_date = anchor.date()
        prev_t: time | None = None
        for key, val in items.items():
            t = self._parse_time_key(key)
            if prev_t is not None and t < prev_t:
                current_date += timedelta(days=1)
            result.append((datetime.combine(current_date, t, tzinfo=anchor.tzinfo), val))
            prev_t = t
        return result

    def _parse(self, raw: dict[str, Any], schema: type[_T], user_id: UUID, context: str) -> _T | None:
        try:
            return schema.model_validate(raw)
        except ValidationError as e:
            log_structured(
                self.logger, "warning", f"Polar {context} validation error: {e}", provider="polar", user_id=str(user_id)
            )
            return None

    # -------------------------------------------------------------------------
    # Sleep - GET /v3/users/sleep, GET /v3/users/sleep/{date} and GET /v3/users/sleep/available
    # -------------------------------------------------------------------------

    def _get_available_sleep_dates(self, db: DbSession, user_id: UUID) -> set[date]:
        response = self._make_api_request(db, user_id, "/v3/users/sleep/available")
        nights = (response or {}).get("available", [])
        return {date.fromisoformat(night["date"]) for night in nights if night.get("date")}

    def get_sleep_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        date_range = {
            start_time.date() + timedelta(days=i) for i in range((end_time.date() - start_time.date()).days + 1)
        }
        available_dates = self._get_available_sleep_dates(db, user_id)
        sleep_data = []
        for d in date_range.intersection(available_dates):
            response = self._make_api_request(db, user_id, f"/v3/users/sleep/{d.isoformat()}")
            if response:
                sleep_data.append(response)
        return sleep_data

    def _parse_hypnogram(
        self,
        hypnogram: dict[str, int],
        sleep_start: datetime,
        sleep_end: datetime,
    ) -> list[SleepStage]:
        entries = self._hhmm_to_datetimes(hypnogram, sleep_start)
        if not entries:
            return []

        # Group consecutive runs of the same stage into a single SleepStage
        stages: list[SleepStage] = []
        group_start, current_val = entries[0]

        for dt, stage_val in entries[1:]:
            if stage_val != current_val:
                stage_type = self._HYPNOGRAM_STAGE_MAP.get(current_val)
                if stage_type is not None:
                    stages.append(SleepStage(stage=stage_type, start_time=group_start, end_time=dt))
                group_start = dt
                current_val = stage_val

        stage_type = self._HYPNOGRAM_STAGE_MAP.get(current_val)
        if stage_type is not None:
            stages.append(SleepStage(stage=stage_type, start_time=group_start, end_time=sleep_end))
        return stages

    def _parse_sleep_hr_samples(
        self,
        hr_samples: dict[str, int],
        sleep_start: datetime,
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        return [
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.POLAR,
                source=ProviderName.POLAR,
                recorded_at=dt,
                value=bpm,
                series_type=SeriesType.heart_rate,
            )
            for dt, bpm in self._hhmm_to_datetimes(hr_samples, sleep_start)
        ]

    SleepNormalized = tuple[
        EventRecordCreate, EventRecordDetailCreate, HealthScoreCreate | None, list[TimeSeriesSampleCreate]
    ]

    def normalize_sleep(  # type: ignore[override]
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[SleepNormalized]:
        results: list[Polar247Data.SleepNormalized] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, SleepJSON, user_id, "sleep")) is None:
                continue
            if not parsed.sleep_start_time or not parsed.sleep_end_time:
                log_structured(
                    self.logger,
                    "warning",
                    f"Polar sleep record missing start/end time: {parsed.date}",
                    provider="polar",
                    user_id=str(user_id),
                )
                continue

            sleep_id = uuid4()
            start_dt = datetime.fromisoformat(parsed.sleep_start_time)
            end_dt = datetime.fromisoformat(parsed.sleep_end_time)
            duration_seconds = int((end_dt - start_dt).total_seconds())

            light_s = parsed.light_sleep or 0
            deep_s = parsed.deep_sleep or 0
            rem_s = parsed.rem_sleep or 0
            sleep_stages = self._parse_hypnogram(parsed.hypnogram, start_dt, end_dt) if parsed.hypnogram else None

            record = EventRecordCreate(
                id=sleep_id,
                category="sleep",
                type="sleep_session",
                source_name="Polar",
                duration_seconds=duration_seconds,
                start_datetime=start_dt,
                end_datetime=end_dt,
                provider=ProviderName.POLAR,
                user_id=user_id,
            )
            detail = EventRecordDetailCreate(
                record_id=sleep_id,
                sleep_total_duration_minutes=(light_s + deep_s + rem_s) // 60,
                sleep_time_in_bed_minutes=duration_seconds // 60 if duration_seconds else None,
                sleep_deep_minutes=deep_s // 60,
                sleep_light_minutes=light_s // 60,
                sleep_rem_minutes=rem_s // 60,
                sleep_awake_minutes=(parsed.total_interruption_duration or 0) // 60,
                sleep_stages=sleep_stages,
            )

            score: HealthScoreCreate | None = None
            if parsed.sleep_score is not None:
                raw_components: dict[str, float | int | None] = {
                    "sleep_time": parsed.group_duration_score,
                    "long_interruptions": parsed.long_interruption_duration,
                    "continuity": parsed.continuity,
                    "actual_sleep": parsed.group_solidity_score,
                    "rem_sleep": parsed.rem_sleep,
                    "deep_sleep": parsed.deep_sleep,
                }
                components: dict[str, ScoreComponent] = {
                    k: ScoreComponent(value=v) for k, v in raw_components.items() if v is not None
                }
                score = HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.POLAR,
                    category=HealthScoreCategory.SLEEP,
                    value=parsed.sleep_score,
                    recorded_at=start_dt,
                    components=components or None,
                    sleep_record_id=sleep_id,
                )

            hr_samples = (
                self._parse_sleep_hr_samples(parsed.heart_rate_samples, start_dt, user_id)
                if parsed.heart_rate_samples
                else []
            )
            results.append((record, detail, score, hr_samples))
        return results

    # -------------------------------------------------------------------------
    # Daily Activity - GET /v3/users/activities
    # -------------------------------------------------------------------------

    def get_daily_activity_statistics(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        # Polar enforces a max 28-day window per request
        results: list[dict[str, Any]] = []
        chunk_start = start_date
        while chunk_start < end_date:
            chunk_end = min(chunk_start + timedelta(days=27), end_date)
            params = {
                "from": chunk_start.date().isoformat(),
                "to": chunk_end.date().isoformat(),
                "steps": "true",
                "activity_zones": "false",
                "inactivity_stamps": "false",
            }
            response = self._make_api_request(db, user_id, "/v3/users/activities", params=params)
            results.extend(response or [])
            chunk_start = chunk_end + timedelta(days=1)
        return results

    def normalize_daily_activity(  # type: ignore[override]
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        samples: list[TimeSeriesSampleCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, DailyActivityJSON, user_id, "daily_activity")) is None:
                continue
            if not parsed.start_time:
                continue
            recorded_at = datetime.fromisoformat(parsed.start_time)
            if parsed.steps is not None:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=ProviderName.POLAR,
                        source=ProviderName.POLAR,
                        recorded_at=recorded_at,
                        value=parsed.steps,
                        series_type=SeriesType.steps,
                    )
                )
            if parsed.active_calories is not None:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=ProviderName.POLAR,
                        source=ProviderName.POLAR,
                        recorded_at=recorded_at,
                        value=parsed.active_calories,
                        series_type=SeriesType.energy,
                    )
                )
            if parsed.distance_from_steps is not None:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=ProviderName.POLAR,
                        source=ProviderName.POLAR,
                        recorded_at=recorded_at,
                        value=Decimal(str(parsed.distance_from_steps)),
                        series_type=SeriesType.distance_walking_running,
                    )
                )
        return samples

    # -------------------------------------------------------------------------
    # Continuous Heart Rate - GET /v3/users/continuous-heart-rate/{date}
    # -------------------------------------------------------------------------

    def get_continuous_hr_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        chunk_start = start_time
        while chunk_start < end_time:
            chunk_end = min(chunk_start + timedelta(days=27), end_time)
            params = {"from": chunk_start.date().isoformat(), "to": chunk_end.date().isoformat()}
            response = self._make_api_request(db, user_id, "/v3/users/continuous-heart-rate", params=params)
            results.extend((response or {}).get("heart_rates", []))
            chunk_start = chunk_end + timedelta(days=1)
        return results

    def normalize_continuous_hr(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        samples: list[TimeSeriesSampleCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, ContinuousHeartRateJSON, user_id, "continuous_hr")) is None:
                continue
            if not parsed.date or not parsed.heart_rate_samples:
                continue
            anchor = datetime.fromisoformat(parsed.date)
            samples_dict = {s.sample_time: s.heart_rate for s in parsed.heart_rate_samples if s.sample_time}
            samples.extend(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.POLAR,
                    source=ProviderName.POLAR,
                    recorded_at=dt,
                    value=bpm,
                    series_type=SeriesType.heart_rate,
                )
                for dt, bpm in self._hhmm_to_datetimes(samples_dict, anchor)
            )
        return samples

    # -------------------------------------------------------------------------
    # Cardio Load - GET /v3/users/cardio-load/{date}
    # -------------------------------------------------------------------------

    def get_cardio_load_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        chunk_start = start_time
        while chunk_start < end_time:
            chunk_end = min(chunk_start + timedelta(days=27), end_time)
            params = {"from": chunk_start.date().isoformat(), "to": chunk_end.date().isoformat()}
            response = self._make_api_request(db, user_id, "/v3/users/cardio-load/date", params=params)
            results.extend(response or [])
            chunk_start = chunk_end + timedelta(days=1)
        return results

    def normalize_cardio_load(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[HealthScoreCreate]:
        scores: list[HealthScoreCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, CardioLoadJSON, user_id, "cardio_load")) is None:
                continue
            if parsed.cardio_load is None or not parsed.date:
                continue
            if parsed.cardio_load_status == "LOAD_STATUS_NOT_AVAILABLE":
                continue
            raw_components: dict[str, float | int | None] = {
                "strain": parsed.strain,
                "tolerance": parsed.tolerance,
                "cardio_load_ratio": parsed.cardio_load_ratio,
            }
            if parsed.cardio_load_level:
                lvl = parsed.cardio_load_level
                raw_components.update(
                    {
                        "level_very_low": lvl.very_low,
                        "level_low": lvl.low,
                        "level_medium": lvl.medium,
                        "level_high": lvl.high,
                        "level_very_high": lvl.very_high,
                    }
                )
            components = {k: ScoreComponent(value=v) for k, v in raw_components.items() if v is not None}
            scores.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.POLAR,
                    category=HealthScoreCategory.STRAIN,
                    value=parsed.cardio_load,
                    recorded_at=datetime.fromisoformat(parsed.date),
                    components=components or None,
                )
            )
        return scores

    # -------------------------------------------------------------------------
    # Nightly Recharge - GET /v3/users/nightly-recharge/{date}
    # -------------------------------------------------------------------------

    def get_nightly_recharge_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        response = self._make_api_request(db, user_id, "/v3/users/nightly-recharge")
        return (response or {}).get("recharges", [])

    def normalize_nightly_recharge(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[HealthScoreCreate]:
        scores: list[HealthScoreCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, NightlyRechargeJSON, user_id, "nightly_recharge")) is None:
                continue
            if parsed.nightly_recharge_status is None or not parsed.date:
                continue
            components: dict[str, ScoreComponent] = {}
            for key, val in {
                "heart_rate_avg": parsed.heart_rate_avg,
                "beat_to_beat_avg": parsed.beat_to_beat_avg,
                "heart_rate_variability_avg": parsed.heart_rate_variability_avg,
                "breathing_rate_avg": parsed.breathing_rate_avg,
                "ans_charge": parsed.ans_charge,
            }.items():
                if val is not None:
                    components[key] = ScoreComponent(value=val)
            if parsed.ans_charge_status is not None:
                components["ans_charge_status"] = ScoreComponent(
                    value=parsed.ans_charge_status,
                    qualifier=self._ANS_CHARGE_STATUS_LABELS.get(parsed.ans_charge_status),
                )
            scores.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.POLAR,
                    category=HealthScoreCategory.RECOVERY,
                    value=parsed.nightly_recharge_status,
                    qualifier=self._NIGHTLY_RECHARGE_STATUS_LABELS.get(parsed.nightly_recharge_status),
                    recorded_at=datetime.fromisoformat(parsed.date),
                    components=components or None,
                )
            )
        return scores

    # -------------------------------------------------------------------------
    # SleepWise — Alertness: GET /v3/users/sleepwise/alertness
    # -------------------------------------------------------------------------

    def get_alertness_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        params = {
            "from": start_time.date().isoformat(),
            "to": end_time.date().isoformat(),
        }
        response = self._make_api_request(db, user_id, "/v3/users/sleepwise/alertness", params=params)
        return response or []

    def normalize_alertness(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[HealthScoreCreate]:
        scores: list[HealthScoreCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, AlertnessJSON, user_id, "alertness")) is None:
                continue
            # Only score primary results — additional are supplementary assessments
            if parsed.grade is None or parsed.grade_type != GradeType.PRIMARY:
                continue
            if not parsed.period_start_time:
                continue
            components: dict[str, ScoreComponent] = {}
            if parsed.grade_validity_seconds is not None:
                components["grade_validity_seconds"] = ScoreComponent(value=parsed.grade_validity_seconds)
            if parsed.sleep_inertia is not None:
                components["sleep_inertia"] = ScoreComponent(
                    value=None,
                    qualifier=self._SLEEP_INERTIA_LABELS.get(parsed.sleep_inertia),
                )
            if parsed.sleep_type is not None:
                components["sleep_type"] = ScoreComponent(value=None, qualifier=parsed.sleep_type.value)
            scores.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.POLAR,
                    category=HealthScoreCategory.READINESS,
                    value=parsed.grade,
                    qualifier=self._GRADE_CLASSIFICATION_LABELS.get(parsed.grade_classification)
                    if parsed.grade_classification
                    else None,
                    recorded_at=datetime.fromisoformat(parsed.period_start_time),
                    components=components or None,
                )
            )
        return scores

    # -------------------------------------------------------------------------
    # SleepWise — Circadian Bedtime: GET /v3/users/sleepwise/circadian-bedtime
    # -------------------------------------------------------------------------

    def get_circadian_bedtime_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        params = {
            "from": start_time.date().isoformat(),
            "to": end_time.date().isoformat(),
        }
        response = self._make_api_request(db, user_id, "/v3/users/sleepwise/circadian-bedtime", params=params)
        return response or []

    def normalize_circadian_bedtime(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[HealthScoreCreate]:
        scores: list[HealthScoreCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, CircadianBedtimeJSON, user_id, "circadian_bedtime")) is None:
                continue
            if parsed.quality is None or parsed.quality == CircadianBedtimeQuality.UNKNOWN:
                continue
            if not parsed.period_start_time:
                continue
            components: dict[str, ScoreComponent] = {}
            if parsed.sleep_gate_start_time and parsed.sleep_gate_end_time:
                components["sleep_gate_start"] = ScoreComponent(value=None, qualifier=parsed.sleep_gate_start_time)
                components["sleep_gate_end"] = ScoreComponent(value=None, qualifier=parsed.sleep_gate_end_time)
            if parsed.result_type is not None and parsed.result_type != CircadianBedtimeResultType.UNKNOWN:
                components["result_type"] = ScoreComponent(value=None, qualifier=parsed.result_type.value)
            scores.append(
                HealthScoreCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.POLAR,
                    category=HealthScoreCategory.SLEEP,
                    value=self._CIRCADIAN_QUALITY_VALUES.get(parsed.quality),
                    qualifier=self._CIRCADIAN_QUALITY_LABELS.get(parsed.quality),
                    recorded_at=datetime.fromisoformat(parsed.period_start_time),
                    components=components or None,
                )
            )
        return scores

    # -------------------------------------------------------------------------
    # Elixir — Body Temperature: GET /v3/users/body-temperature
    # -------------------------------------------------------------------------

    def get_body_temperature_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        params = {"from": start_time.date().isoformat(), "to": end_time.date().isoformat()}
        response = self._make_api_request(db, user_id, "/v3/users/body-temperature", params=params)
        return response or []

    def normalize_body_temperature(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        samples: list[TimeSeriesSampleCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, BodyTemperaturePeriodJSON, user_id, "body_temperature")) is None:
                continue
            if not parsed.samples or not parsed.start_time or not parsed.measurement_type:
                continue
            series_type = self._BODY_TEMP_SERIES_TYPE.get(parsed.measurement_type)
            if series_type is None:
                continue
            anchor = datetime.fromisoformat(parsed.start_time)
            samples.extend(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider=ProviderName.POLAR,
                    source=ProviderName.POLAR,
                    recorded_at=anchor + timedelta(milliseconds=s.recording_time_delta_milliseconds or 0),
                    value=s.temperature_celsius,
                    series_type=series_type,
                )
                for s in parsed.samples
                if s.temperature_celsius is not None
            )
        return samples

    # -------------------------------------------------------------------------
    # Elixir — Sleep Skin Temperature: GET /v3/users/sleep-skin-temperature
    # -------------------------------------------------------------------------

    def get_sleep_skin_temperature_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        params = {"from": start_time.date().isoformat(), "to": end_time.date().isoformat()}
        response = self._make_api_request(db, user_id, "/v3/users/sleep-skin-temperature", params=params)
        return response or []

    def normalize_sleep_skin_temperature(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        samples: list[TimeSeriesSampleCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, SkinTemperatureJSON, user_id, "sleep_skin_temperature")) is None:
                continue
            if not parsed.sleep_date:
                continue
            recorded_at = datetime.fromisoformat(parsed.sleep_date)
            if parsed.sleep_time_skin_temperature_celsius is not None:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=ProviderName.POLAR,
                        source=ProviderName.POLAR,
                        recorded_at=recorded_at,
                        value=parsed.sleep_time_skin_temperature_celsius,
                        series_type=SeriesType.skin_temperature,
                    )
                )
            if parsed.deviation_from_baseline_celsius is not None:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=ProviderName.POLAR,
                        source=ProviderName.POLAR,
                        recorded_at=recorded_at,
                        value=parsed.deviation_from_baseline_celsius,
                        series_type=SeriesType.skin_temperature_deviation,
                    )
                )
        return samples

    # -------------------------------------------------------------------------
    # Elixir — SpO2: GET /v3/users/spo2
    # -------------------------------------------------------------------------

    def get_spo2_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        params = {"from": start_time.date().isoformat(), "to": end_time.date().isoformat()}
        response = self._make_api_request(db, user_id, "/v3/users/spo2", params=params)
        return response or []

    def normalize_spo2(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        samples: list[TimeSeriesSampleCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, Spo2TestResultJSON, user_id, "spo2")) is None:
                continue
            if parsed.test_status != Spo2TestStatus.PASSED or parsed.test_time is None:
                continue
            recorded_at = datetime.fromtimestamp(parsed.test_time, tz=timezone.utc)
            if parsed.blood_oxygen_percent is not None:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=ProviderName.POLAR,
                        source=ProviderName.POLAR,
                        recorded_at=recorded_at,
                        value=parsed.blood_oxygen_percent,
                        series_type=SeriesType.oxygen_saturation,
                    )
                )
            if parsed.heart_rate_variability_ms is not None:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=ProviderName.POLAR,
                        source=ProviderName.POLAR,
                        recorded_at=recorded_at,
                        value=parsed.heart_rate_variability_ms,
                        series_type=SeriesType.heart_rate_variability_rmssd,
                    )
                )
        return samples

    # -------------------------------------------------------------------------
    # Elixir — Wrist ECG: GET /v3/users/wrist-ecg
    # -------------------------------------------------------------------------

    def get_wrist_ecg_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        params = {"from": start_time.date().isoformat(), "to": end_time.date().isoformat()}
        response = self._make_api_request(db, user_id, "/v3/users/wrist-ecg", params=params)
        return response or []

    def normalize_wrist_ecg(
        self,
        raw_items: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        samples: list[TimeSeriesSampleCreate] = []
        for raw in raw_items:
            if (parsed := self._parse(raw, EcgTestResultJSON, user_id, "wrist_ecg")) is None:
                continue
            if parsed.test_time is None:
                continue
            recorded_at = datetime.fromtimestamp(parsed.test_time, tz=timezone.utc)
            if parsed.heart_rate_variability_ms is not None:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=ProviderName.POLAR,
                        source=ProviderName.POLAR,
                        recorded_at=recorded_at,
                        value=parsed.heart_rate_variability_ms,
                        series_type=SeriesType.heart_rate_variability_rmssd,
                    )
                )
            if parsed.average_heart_rate_bpm is not None:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider=ProviderName.POLAR,
                        source=ProviderName.POLAR,
                        recorded_at=recorded_at,
                        value=parsed.average_heart_rate_bpm,
                        series_type=SeriesType.heart_rate,
                    )
                )
        return samples

    # -------------------------------------------------------------------------
    # Persistence helpers
    # -------------------------------------------------------------------------

    def _save_timeseries(self, db: DbSession, samples: list[TimeSeriesSampleCreate]) -> int:
        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    def _save_scores(self, db: DbSession, scores: list[HealthScoreCreate]) -> int:
        if scores:
            health_score_service.bulk_create(db, scores)
        return len(scores)

    def _save_sleep(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        raw_items = self.get_sleep_data(db, user_id, start_time, end_time)
        normalized = self.normalize_sleep(raw_items, user_id)
        count = 0
        scores: list[HealthScoreCreate] = []
        hr_samples: list[TimeSeriesSampleCreate] = []

        for record, detail, score, hr in normalized:
            try:
                event_record_service.create_or_merge_sleep(db, user_id, record, detail, settings.sleep_end_gap_minutes)
                count += 1
                if score:
                    scores.append(score)
                hr_samples.extend(hr)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to save Polar sleep record: {e}",
                    provider="polar",
                    task="_save_sleep",
                    user_id=str(user_id),
                )

        self._save_scores(db, scores)
        self._save_timeseries(db, hr_samples)
        return count

    # -------------------------------------------------------------------------
    # Load and save all — entry point for sync_vendor_data task
    # -------------------------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        tasks: dict[str, Callable[[], int]] = {
            "sleep": lambda: self._save_sleep(db, user_id, start_time, end_time),
            "daily_activity": lambda: self._save_timeseries(
                db,
                self.normalize_daily_activity(
                    self.get_daily_activity_statistics(db, user_id, start_time, end_time), user_id
                ),
            ),
            "continuous_hr": lambda: self._save_timeseries(
                db,
                self.normalize_continuous_hr(self.get_continuous_hr_data(db, user_id, start_time, end_time), user_id),
            ),
            "cardio_load": lambda: self._save_scores(
                db, self.normalize_cardio_load(self.get_cardio_load_data(db, user_id, start_time, end_time), user_id)
            ),
            "nightly_recharge": lambda: self._save_scores(
                db,
                self.normalize_nightly_recharge(
                    self.get_nightly_recharge_data(db, user_id, start_time, end_time), user_id
                ),
            ),
            "alertness": lambda: self._save_scores(
                db, self.normalize_alertness(self.get_alertness_data(db, user_id, start_time, end_time), user_id)
            ),
            "circadian_bedtime": lambda: self._save_scores(
                db,
                self.normalize_circadian_bedtime(
                    self.get_circadian_bedtime_data(db, user_id, start_time, end_time), user_id
                ),
            ),
            "body_temperature": lambda: self._save_timeseries(
                db,
                self.normalize_body_temperature(
                    self.get_body_temperature_data(db, user_id, start_time, end_time), user_id
                ),
            ),
            "sleep_skin_temperature": lambda: self._save_timeseries(
                db,
                self.normalize_sleep_skin_temperature(
                    self.get_sleep_skin_temperature_data(db, user_id, start_time, end_time), user_id
                ),
            ),
            "spo2": lambda: self._save_timeseries(
                db, self.normalize_spo2(self.get_spo2_data(db, user_id, start_time, end_time), user_id)
            ),
            "wrist_ecg": lambda: self._save_timeseries(
                db, self.normalize_wrist_ecg(self.get_wrist_ecg_data(db, user_id, start_time, end_time), user_id)
            ),
        }

        results: dict[str, int] = {}
        for data_type, fn in tasks.items():
            try:
                results[data_type] = fn()
                db.commit()
            except Exception as e:
                db.rollback()
                results[data_type] = 0
                log_structured(
                    self.logger,
                    "error",
                    f"Failed to sync {data_type} data",
                    provider="polar",
                    task="load_and_save_all",
                    data_type=data_type,
                    user_id=str(user_id),
                    error=str(e),
                )

        return results

    # -------------------------------------------------------------------------
    # Not implemented — Polar recovery and activity samples map to other modules
    # -------------------------------------------------------------------------

    def get_recovery_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        return []

    def normalize_recovery(
        self,
        raw_recovery: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        return {}

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
