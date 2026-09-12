"""Garmin Connect 24/7 data handler (sleep, HR, stress, steps, body comp, HRV)."""

import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.config import settings
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository, UserConnectionRepository
from app.schemas.enums import SeriesType, daily_total_flag
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    SleepStage,
    TimeSeriesSampleCreate,
)
from app.services.event_record_service import event_record_service
from app.services.providers.garmin_connect import client as garmin_client
from app.services.providers.garmin_connect.client import (
    GarminConnectClient,
    GarminConnectClientError,
    GarminConnectRateLimitError,
)
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.timeseries_service import timeseries_service
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROVIDER = "garmin_connect"

# How many days back to probe for a VO2max reading before giving up. Garmin only
# writes one after a qualifying activity, so a fixed small window finds the
# current value in 1-3 requests for anyone training weekly, while capping the
# cost for someone who has not.
_VO2MAX_LOOKBACK_DAYS = 10

# Map garminconnect sleep level activity values → SleepStageType
# sleepLevels entries have activityLevel: 0=deep, 1=light, 2=rem, 3=awake
_ACTIVITY_LEVEL_TO_STAGE: dict[int, SleepStageType] = {
    0: SleepStageType.DEEP,
    1: SleepStageType.LIGHT,
    2: SleepStageType.REM,
    3: SleepStageType.AWAKE,
}


class GarminConnect247Data(Base247DataTemplate):
    """24/7 data handler for Garmin Connect (sleep, HR, stress, steps, body comp, HRV)."""

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        client: GarminConnectClient,
    ) -> None:
        # oauth=None because garmin_connect bypasses OAuth entirely (credential-based
        # provider). The template's signature requires BaseOAuthTemplate, hence the
        # ignore — ty doesn't honour the mypy-style `type: ignore[arg-type]`.
        super().__init__(
            provider_name=provider_name,
            api_base_url=api_base_url,
            oauth=None,  # ty: ignore[invalid-argument-type]
        )
        self.client = client
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.connection_repo = UserConnectionRepository()
        self.logger = logging.getLogger(self.__class__.__name__)

    # -------------------------------------------------------------------------
    # Abstract method stubs (not used; we override load_and_save_all instead)
    # -------------------------------------------------------------------------

    def get_sleep_data(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict]:
        return []

    def normalize_sleep(self, raw_sleep: dict, user_id: UUID) -> dict:
        return {}

    def get_recovery_data(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict]:
        return []

    def normalize_recovery(self, raw_recovery: dict, user_id: UUID) -> dict:
        return {}

    def get_activity_samples(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict]:
        return []

    def normalize_activity_samples(self, raw_samples: list[dict], user_id: UUID) -> dict[str, list[dict]]:
        return {}

    def get_daily_activity_statistics(
        self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        return []

    def normalize_daily_activity(self, raw_stats: dict, user_id: UUID) -> dict:
        return {}

    # -------------------------------------------------------------------------
    # Sleep
    # -------------------------------------------------------------------------

    def _extract_sleep_stages(self, sleep_levels: list[dict]) -> list[SleepStage]:
        """Build SleepStage list from garminconnect sleepLevels entries."""
        stages: list[SleepStage] = []
        for entry in sleep_levels:
            start_raw = entry.get("startGMT")
            end_raw = entry.get("endGMT")
            level = entry.get("activityLevel")
            if start_raw is None or end_raw is None or level is None:
                continue
            stage_type = _ACTIVITY_LEVEL_TO_STAGE.get(int(level))
            if stage_type is None:
                continue
            try:
                start_dt = datetime.fromisoformat(str(start_raw).replace(" ", "T")).replace(tzinfo=timezone.utc)
                end_dt = datetime.fromisoformat(str(end_raw).replace(" ", "T")).replace(tzinfo=timezone.utc)
                stages.append(SleepStage(stage=stage_type, start_time=start_dt, end_time=end_dt))
            except (ValueError, TypeError):
                continue
        return sorted(stages, key=lambda s: s.start_time)

    def save_sleep_for_date(self, db: DbSession, user_id: UUID, cdate: date) -> int:
        """Fetch, normalize, and save sleep data for a single date."""
        raw = self.client.get_sleep_data(cdate)
        dto: dict = raw.get("dailySleepDTO") or {}
        if not dto:
            return 0

        start_ts = dto.get("sleepStartTimestampGMT")
        end_ts = dto.get("sleepEndTimestampGMT")
        if not start_ts or not end_ts:
            return 0

        # Garmin Connect returns sleepStartTimestampGMT / sleepEndTimestampGMT in
        # milliseconds, not seconds.
        start_dt = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc)
        duration_s = int(end_dt.timestamp() - start_dt.timestamp())

        deep_s = dto.get("deepSleepSeconds") or 0
        light_s = dto.get("lightSleepSeconds") or 0
        rem_s = dto.get("remSleepSeconds") or 0
        awake_s = dto.get("awakeSleepSeconds") or 0
        total_sleep_s = deep_s + light_s + rem_s

        sleep_levels: list[dict] = raw.get("sleepLevels") or []
        stage_timestamps = self._extract_sleep_stages(sleep_levels)

        sleep_id = uuid4()
        record = EventRecordCreate(
            id=sleep_id,
            category="sleep",
            type="sleep_session",
            source_name="Garmin Connect",
            # The 24/7 endpoints don't say which device produced the data, so ask
            # the account once per sync (cached on the client). Without a model,
            # infer_device_type_from_model returns UNKNOWN and the UI shows its
            # unknown-device fallback on every sleep / body-metrics row.
            device_model=self.client.get_last_used_device_model(),
            duration_seconds=duration_s,
            start_datetime=start_dt,
            end_datetime=end_dt,
            source=self.provider_name,
            user_id=user_id,
        )

        detail = EventRecordDetailCreate(
            record_id=sleep_id,
            sleep_total_duration_minutes=total_sleep_s // 60,
            sleep_time_in_bed_minutes=duration_s // 60,
            sleep_deep_minutes=deep_s // 60,
            sleep_light_minutes=light_s // 60,
            sleep_rem_minutes=rem_s // 60,
            sleep_awake_minutes=awake_s // 60,
            sleep_stages=stage_timestamps or None,
        )

        try:
            event_record_service.create_or_merge_sleep(db, user_id, record, detail, settings.sleep_end_gap_minutes)
            saved = 1
        except Exception as exc:
            log_structured(
                self.logger,
                "error",
                "Failed to save Garmin Connect sleep record",
                action="garmin_connect_sleep_save_error",
                error=str(exc),
                user_id=str(user_id),
            )
            return 0

        # Physiology rows are counted separately, NOT folded into `saved`.
        # results["sleep"] is reported as an item count via
        # sync_vendor_data_task -> provider_result.params["data_247"], and now
        # that this writes hundreds of intraday epoch rows per night, adding them
        # here would report a 7-night sync as ~2800 "sleep" items instead of 7.
        self._save_sleep_physiology(db, user_id, raw, dto, start_dt, end_dt)
        return saved

    def _save_sleep_physiology(
        self, db: DbSession, user_id: UUID, raw: dict, dto: dict, start_dt: datetime, end_dt: datetime
    ) -> int:
        """Persist the nightly physiology averages carried in the sleep payload.

        These arrive in the same ``get_sleep_data`` response we have already paid
        for, so this costs no additional authenticated request — which matters,
        because the per-day sync loop is what got this provider IP rate-limited.
        Emitted once per night at the sleep midpoint so they cannot collide with
        each other on the (data_source, series_type, recorded_at) upsert key.
        """
        midpoint = start_dt + (end_dt - start_dt) / 2
        device_model = self.client.get_last_used_device_model()

        # Field names verified against a live payload 2026-08-29. The previous
        # names (avgSpO2 / avgRespirationValue / avgSleepHRV) do not exist in the
        # response, so every lookup returned None and this method wrote zero rows
        # on every night since it was added — while coverage.py advertised both
        # series. avgOvernightHrv sits at the response ROOT, not inside
        # dailySleepDTO, which is why it is passed in separately below.
        mapping: list[tuple[dict, str, SeriesType]] = [
            (dto, "averageSpO2Value", SeriesType.oxygen_saturation),
            (dto, "averageRespirationValue", SeriesType.respiratory_rate),
            # Garmin's own overnight HRV average. Independent of get_hrv_data, so
            # HRV survives even when that endpoint returns nothing for a date.
            (raw, "avgOvernightHrv", SeriesType.heart_rate_variability_rmssd),
        ]

        samples: list[TimeSeriesSampleCreate] = []
        for container, field, series_type in mapping:
            value = container.get(field)
            if value is None:
                continue
            with suppress(Exception):
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        device_model=device_model,
                        recorded_at=midpoint,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                )

        samples.extend(self._build_sleep_epoch_samples(user_id, raw, device_model))

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    def _build_sleep_epoch_samples(
        self, user_id: UUID, raw: dict, device_model: str | None
    ) -> list[TimeSeriesSampleCreate]:
        """Build intraday SpO2 / respiration / HRV rows from the sleep payload.

        These arrays ride along in the ``get_sleep_data`` response we have
        already paid for, so they cost no additional authenticated request —
        which is the binding constraint for this provider. The official Garmin
        webhook provider persists the same series from /pulseOx and /respiration
        as an average PLUS an intraday series (see Garmin247Data), so this
        mirrors that shape rather than inventing one.

        Non-positive readings are skipped, matching the webhook parser: Garmin
        uses them as "not measured" sentinels.
        """
        out: list[TimeSeriesSampleCreate] = []

        def _add(recorded_at: datetime, value: float | int | None, series_type: SeriesType) -> None:
            if value is None or value <= 0:
                return
            with suppress(Exception):
                out.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        device_model=device_model,
                        recorded_at=recorded_at,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                )

        for entry in raw.get("wellnessEpochSPO2DataDTOList") or []:
            ts = entry.get("epochTimestamp")
            if not ts:
                continue
            with suppress(Exception):
                recorded_at = datetime.fromisoformat(str(ts)).replace(tzinfo=timezone.utc)
                _add(recorded_at, entry.get("spo2Reading"), SeriesType.oxygen_saturation)

        for entry in raw.get("wellnessEpochRespirationDataDTOList") or []:
            epoch_ms = entry.get("startTimeGMT")
            if epoch_ms is None:
                continue
            with suppress(Exception):
                recorded_at = datetime.fromtimestamp(float(epoch_ms) / 1000.0, tz=timezone.utc)
                _add(recorded_at, entry.get("respirationValue"), SeriesType.respiratory_rate)

        # NOTE the sleep payload also carries an "hrvData" array, but it is the
        # same readings at the same timestamps as get_hrv_data's "hrvReadings"
        # (verified 2026-08-29: 93 entries, identical epochs), which
        # save_hrv_for_date already persists. Ingesting both would build
        # duplicate objects for the upsert to discard. The nightly
        # avgOvernightHrv average above is kept as the documented fallback for
        # when get_hrv_data returns nothing.
        #
        # Consolidation opportunity, deliberately not taken here: because
        # avgOvernightHrv == hrvSummary.lastNightAvg and hrvData == hrvReadings,
        # the whole get_hrv_data per-day call could be dropped in favour of this
        # payload, saving one authenticated request per synced day. That is a
        # behavioural change to the sync task list and deserves its own review.
        return out

    # -------------------------------------------------------------------------
    # Heart Rate
    # -------------------------------------------------------------------------

    def save_heart_rate_for_date(self, db: DbSession, user_id: UUID, cdate: date) -> int:
        """Fetch and save heart rate samples for a single date."""
        raw = self.client.get_heart_rates(cdate)
        hr_values: list = raw.get("heartRateValues") or []
        resting_hr = raw.get("restingHeartRate")

        samples: list[TimeSeriesSampleCreate] = []

        for entry in hr_values:
            # entry is [epoch_ms, bpm]
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            epoch_ms, bpm = entry[0], entry[1]
            if bpm is None:
                continue
            try:
                recorded_at = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        device_model=self.client.get_last_used_device_model(),
                        recorded_at=recorded_at,
                        value=Decimal(str(bpm)),
                        series_type=SeriesType.heart_rate,
                    )
                )
            except Exception as exc:
                log_structured(
                    self.logger,
                    "warning",
                    "Failed to build HR sample",
                    action="garmin_connect_hr_sample_error",
                    error=str(exc),
                    user_id=str(user_id),
                )

        if resting_hr is not None:
            try:
                midnight = datetime(cdate.year, cdate.month, cdate.day, tzinfo=timezone.utc)
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        device_model=self.client.get_last_used_device_model(),
                        recorded_at=midnight,
                        value=Decimal(str(resting_hr)),
                        series_type=SeriesType.resting_heart_rate,
                    )
                )
            except Exception as exc:
                log_structured(
                    self.logger,
                    "warning",
                    "Failed to save resting HR",
                    action="garmin_connect_resting_hr_error",
                    error=str(exc),
                    user_id=str(user_id),
                )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Daily Stats (steps, calories, distance, stress summary)
    # -------------------------------------------------------------------------

    def save_daily_stats_for_date(self, db: DbSession, user_id: UUID, cdate: date) -> int:
        """Fetch and save daily stats (steps, energy, distance) for a single date."""
        raw = self.client.get_stats(cdate)
        if not raw:
            return 0

        midnight = datetime(cdate.year, cdate.month, cdate.day, tzinfo=timezone.utc)
        samples: list[TimeSeriesSampleCreate] = []

        metric_map: list[tuple[str, SeriesType]] = [
            ("totalSteps", SeriesType.steps),
            ("activeKilocalories", SeriesType.energy),
            # Basal metabolic rate. The official garmin provider persists this via
            # DAILIES_SERIES; get_stats has carried it all along and we discarded it,
            # which is why ActivitySummary.total_calories_kcal had no basal half.
            ("bmrKilocalories", SeriesType.basal_energy),
            ("totalDistanceMeters", SeriesType.distance_walking_running),
            ("floorsAscended", SeriesType.flights_climbed),
            ("averageStressLevel", SeriesType.garmin_stress_level),
            ("restingHeartRate", SeriesType.resting_heart_rate),
        ]

        # Garmin reports intensity minutes split by band; exercise_time is the
        # combined figure, so sum them rather than emitting two samples at the
        # same timestamp (the upsert key is data_source_id + series_type +
        # recorded_at, so the second would be silently dropped).
        intensity = sum(
            v for k in ("moderateIntensityMinutes", "vigorousIntensityMinutes") if (v := raw.get(k)) is not None
        )
        if intensity:
            metric_map.append(("_intensity_minutes_total", SeriesType.exercise_time))
            raw = {**raw, "_intensity_minutes_total": intensity}

        for field, series_type in metric_map:
            value = raw.get(field)
            if value is None:
                continue
            try:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        device_model=self.client.get_last_used_device_model(),
                        recorded_at=midnight,
                        value=Decimal(str(value)),
                        series_type=series_type,
                        # These are whole-day figures, not intraday samples. Without
                        # this they default to None, which aggregation treats as
                        # summable — so a daily total double-counts against another
                        # provider and mis-aggregates over multi-day ranges.
                        is_daily_total=daily_total_flag(series_type, is_daily=True),
                    )
                )
            except Exception as exc:
                log_structured(
                    self.logger,
                    "warning",
                    "Failed to build daily stat sample",
                    action="garmin_connect_daily_stat_error",
                    field=field,
                    error=str(exc),
                    user_id=str(user_id),
                )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Stress (time-series)
    # -------------------------------------------------------------------------

    def save_stress_for_date(self, db: DbSession, user_id: UUID, cdate: date) -> int:
        """Fetch and save time-series stress data for a single date."""
        raw = self.client.get_stress_data(cdate)
        stress_values: list = raw.get("stressValuesArray") or []

        samples: list[TimeSeriesSampleCreate] = []
        for entry in stress_values:
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            epoch_ms, stress = entry[0], entry[1]
            if stress is None or stress < 0:
                # garminconnect uses -1 / -2 for unmeasured intervals
                continue
            try:
                recorded_at = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        device_model=self.client.get_last_used_device_model(),
                        recorded_at=recorded_at,
                        value=Decimal(str(stress)),
                        series_type=SeriesType.garmin_stress_level,
                    )
                )
            except Exception as exc:
                log_structured(
                    self.logger,
                    "warning",
                    "Failed to build stress sample",
                    action="garmin_connect_stress_sample_error",
                    error=str(exc),
                    user_id=str(user_id),
                )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Body Composition
    # -------------------------------------------------------------------------

    def save_vo2max_for_range(self, db: DbSession, user_id: UUID, end_date: date) -> int:
        """Fetch and save the current VO2max, without a per-day loop.

        Garmin recomputes VO2max only after a qualifying run/ride, so the
        underlying endpoint (/metrics/maxmet/daily/{d}/{d}) returns [] on most
        dates — checked live: 2026-08-05, -24, -27 and -28 were all empty while
        2026-07-18 (a trail run) returned 50.0. Querying only ``end_date`` would
        therefore usually record nothing at all, and a year-long backfill would
        capture at most one point.

        So walk backwards from end_date until a value is found, capped at
        _VO2MAX_LOOKBACK_DAYS requests. That bounds the cost — typically 1-3
        calls, never more than the cap — instead of multiplying by the window
        size, which is the constraint that got this provider rate-limited.
        Only the most recent value is needed: VO2max is a slow-moving estimate
        and the series is an AVG aggregation, not a daily total.

        The sample is stamped with the calendarDate Garmin attributes it to,
        which can predate end_date, rather than with the fetch date.
        """
        entries: list[dict] = []
        for back in range(_VO2MAX_LOOKBACK_DAYS):
            entries = self.client.get_max_metrics(end_date - timedelta(days=back))
            if entries:
                break

        samples: list[TimeSeriesSampleCreate] = []
        for entry in entries:
            generic = entry.get("generic") or {}
            value = generic.get("vo2MaxPreciseValue") or generic.get("vo2MaxValue")
            cal_date = generic.get("calendarDate")
            if value is None or not cal_date:
                continue
            with suppress(Exception):
                recorded_at = datetime.strptime(cal_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        device_model=self.client.get_last_used_device_model(),
                        recorded_at=recorded_at,
                        value=Decimal(str(value)),
                        series_type=SeriesType.vo2_max,
                        # No is_daily_total: vo2_max aggregates as AVG, and
                        # daily_total_flag returns None for anything non-SUM, so
                        # passing it would be a dead expression that reads as
                        # meaningful.
                    )
                )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    def save_body_composition(self, db: DbSession, user_id: UUID, start_date: date, end_date: date) -> int:
        """Fetch and save body composition data for a date range."""
        raw = self.client.get_body_composition(start_date, end_date)
        date_list: list[dict] = raw.get("dateWeightList") or []

        samples: list[TimeSeriesSampleCreate] = []

        for entry in date_list:
            cal_date = entry.get("calendarDate")
            if not cal_date:
                continue
            try:
                recorded_at = datetime.strptime(cal_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            body_metric_map: list[tuple[str, SeriesType]] = [
                ("weight", SeriesType.weight),
                ("bmi", SeriesType.body_mass_index),
                ("bodyFat", SeriesType.body_fat_percentage),
                ("muscleMass", SeriesType.skeletal_muscle_mass),
                ("boneMass", SeriesType.lean_body_mass),
            ]

            for field, series_type in body_metric_map:
                value = entry.get(field)
                if value is None:
                    continue
                # weight from garminconnect is in grams — convert to kg
                if field == "weight":
                    value = value / 1000.0
                try:
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            device_model=self.client.get_last_used_device_model(),
                            recorded_at=recorded_at,
                            value=Decimal(str(round(value, 4))),
                            series_type=series_type,
                        )
                    )
                except Exception as exc:
                    log_structured(
                        self.logger,
                        "warning",
                        "Failed to build body comp sample",
                        action="garmin_connect_body_comp_error",
                        field=field,
                        error=str(exc),
                        user_id=str(user_id),
                    )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # HRV
    # -------------------------------------------------------------------------

    def save_hrv_for_date(self, db: DbSession, user_id: UUID, cdate: date) -> int:
        """Fetch and save HRV data for a single date.

        The nightly average key is ``lastNightAvg``. This previously read
        ``lastNight``, which does not exist in the payload, so the guard below
        returned 0 on every date and this provider never wrote a single HRV
        sample — while still spending one authenticated request per day inside
        the rate-limited sync loop.

        That fix corrected the inner key but left the OUTER one wrong:
        ``hrvSummary`` sits at the response root, not under ``raw["hrv"]``, so
        the lookup still resolved to {} and HRV stayed at zero on every sync
        (verified against a live payload 2026-08-29 — the response has keys
        userProfilePk / hrvSummary / hrvReadings and no "hrv" wrapper).

        ``weeklyAvg`` is deliberately NOT persisted as SDNN: it is a rolling
        average of the same RMSSD-based metric, not an SDNN measurement, and
        writing it to heart_rate_variability_sdnn mislabelled the data.
        """
        raw = self.client.get_hrv_data(cdate)
        # Read from the root, but tolerate a wrapped payload rather than silently
        # writing zero rows again if a garminconnect release reintroduces one:
        # this exact lookup has already been wrong twice.
        body: dict = raw.get("hrv") or raw
        summary: dict = body.get("hrvSummary") or {}
        midnight = datetime(cdate.year, cdate.month, cdate.day, tzinfo=timezone.utc)

        samples: list[TimeSeriesSampleCreate] = []

        last_night = summary.get("lastNightAvg")
        if last_night is not None:
            try:
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        device_model=self.client.get_last_used_device_model(),
                        recorded_at=midnight,
                        value=Decimal(str(last_night)),
                        series_type=SeriesType.heart_rate_variability_rmssd,
                    )
                )
            except Exception as exc:
                log_structured(
                    self.logger,
                    "warning",
                    "Failed to build HRV sample",
                    action="garmin_connect_hrv_error",
                    error=str(exc),
                    user_id=str(user_id),
                )

        # Per-reading intraday RMSSD (roughly 5-minute cadence overnight). Already
        # in the response we just paid for, so this costs no extra request.
        for reading in body.get("hrvReadings") or []:
            value = reading.get("hrvValue")
            ts = reading.get("readingTimeGMT") or reading.get("readingTimeLocal")
            if value is None or not ts:
                continue
            with suppress(Exception):
                recorded_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if recorded_at.tzinfo is None:
                    recorded_at = recorded_at.replace(tzinfo=timezone.utc)
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        device_model=self.client.get_last_used_device_model(),
                        recorded_at=recorded_at,
                        value=Decimal(str(value)),
                        series_type=SeriesType.heart_rate_variability_rmssd,
                    )
                )

        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return len(samples)

    # -------------------------------------------------------------------------
    # Combined load
    # -------------------------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        """Load and save all 24/7 data types for the given date range.

        Aborts the whole run on the first ``GarminConnectClientError`` instead of
        grinding through every remaining (date, data_type) pair: a rate limit, a
        locked account or wrong credentials will all still be true on the next
        pair, and each retry is one more login storm against the endpoint Garmin
        rate-limits. Only genuinely per-day errors (a day with no stress data, a
        malformed payload) are swallowed. Formerly the ow-patch
        fix-garmin-connect-rate-limit-backoff; retired into source 2026-09-13.
        """
        # Module attribute (not a from-import) so the cooldown check can be
        # monkeypatched in one place.
        blocked = garmin_client.cooldown_remaining()
        if blocked > 0:
            log_structured(
                self.logger,
                "warning",
                "Skipping Garmin Connect 24/7 sync: rate-limit cooldown active",
                action="garmin_connect_sync_skipped_cooldown",
                cooldown_remaining_seconds=blocked,
                user_id=str(user_id),
            )
            raise GarminConnectRateLimitError(
                f"Garmin Connect is in rate-limit cooldown for another {blocked}s; sync skipped"
            )

        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        start_date = start_time.date()
        end_date = end_time.date()

        results: dict[str, int] = {
            "sleep": 0,
            "heart_rate": 0,
            "daily_stats": 0,
            "stress": 0,
            "hrv": 0,
            "vo2_max": 0,
        }

        per_day_tasks: dict[str, Callable[[date], int]] = {
            "sleep": lambda d: self.save_sleep_for_date(db, user_id, d),
            "heart_rate": lambda d: self.save_heart_rate_for_date(db, user_id, d),
            "daily_stats": lambda d: self.save_daily_stats_for_date(db, user_id, d),
            "stress": lambda d: self.save_stress_for_date(db, user_id, d),
            "hrv": lambda d: self.save_hrv_for_date(db, user_id, d),
        }

        fatal_exc: Exception | None = None

        for cdate in self.client.iter_dates(start_date, end_date):
            if fatal_exc is not None:
                break
            for data_type, fn in per_day_tasks.items():
                try:
                    results[data_type] += fn(cdate)
                except GarminConnectClientError as exc:
                    fatal_exc = exc
                    rate_limited = isinstance(exc, GarminConnectRateLimitError)
                    log_structured(
                        self.logger,
                        "error",
                        "Aborting Garmin Connect 24/7 sync: "
                        + ("rate limited" if rate_limited else "authentication failed"),
                        action="garmin_connect_sync_aborted_rate_limit"
                        if rate_limited
                        else "garmin_connect_sync_aborted_auth",
                        data_type=data_type,
                        date=str(cdate),
                        error=str(exc),
                        partial_results=dict(results),
                        user_id=str(user_id),
                    )
                    break
                except Exception as exc:
                    log_structured(
                        self.logger,
                        "error",
                        f"Failed to sync {data_type} for {cdate}",
                        action="garmin_connect_sync_error",
                        data_type=data_type,
                        date=str(cdate),
                        error=str(exc),
                        user_id=str(user_id),
                    )

        if fatal_exc is not None:
            # Surface as a failure so the sync run is recorded failed rather than
            # a successful no-op. Records already persisted stay persisted.
            raise fatal_exc

        # Body composition fetched once for the full range
        try:
            results["body_composition"] = self.save_body_composition(db, user_id, start_date, end_date)
        except GarminConnectClientError:
            results["body_composition"] = 0
            raise
        except Exception as exc:
            results["body_composition"] = 0
            log_structured(
                self.logger,
                "error",
                "Failed to sync body composition data",
                action="garmin_connect_body_comp_sync_error",
                error=str(exc),
                user_id=str(user_id),
            )

        # VO2max likewise fetched once, not per-day — see save_vo2max_for_range.
        try:
            results["vo2_max"] = self.save_vo2max_for_range(db, user_id, end_date)
        except GarminConnectClientError:
            results["vo2_max"] = 0
            raise
        except Exception as exc:
            results["vo2_max"] = 0
            log_structured(
                self.logger,
                "error",
                "Failed to sync VO2max data",
                action="garmin_connect_vo2max_sync_error",
                error=str(exc),
                user_id=str(user_id),
            )

        return results
