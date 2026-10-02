"""Withings 24/7 data: body measures (``getmeas``), daily activity (``getactivity``),
intraday activity (``getintradayactivity``) and sleep (``getsummary`` for the night's
totals, ``get`` for its hypnogram). Continuous metrics become ``DataPointSeries``
samples; sleep becomes an ``EventRecord`` + ``EventRecordDetail``, mirroring Oura.
"""

import logging
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, NamedTuple, NoReturn
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.config import settings
from app.constants.series_types.withings import SLEEP_STATE_STAGE_MAP
from app.constants.withings_requests import ACTIVITY, INTRADAY_ACTIVITY, MEASURES, SLEEP_SERIES, SLEEP_SUMMARY
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
from app.schemas.providers.withings import (
    WithingsActivity,
    WithingsIntradayActivity,
    WithingsMeasureGroup,
    WithingsSleepSummary,
)
from app.schemas.providers.withings.imports import WithingsSleepSeriesEntry
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.withings.coverage import ACTIVITY_FIELD_MAP, MEASURE_TYPE_MAP, MEASURE_UNIT_FACTOR
from app.services.providers.withings.handlers.rpc_client import (
    paginate,
    paginate_mapping,
    scale_measure,
    withings_request,
)
from app.services.providers.withings.handlers.timezone import local_day_start, zone_offset_at
from app.services.timeseries_service import timeseries_service
from app.utils.dates import parse_datetime_or_default
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


class _Night(NamedTuple):
    """A sleep session's window, in epoch seconds as Withings reports it."""

    start: int
    end: int


# Trailing window used when a caller supplies no bounds.
_DEFAULT_SYNC_WINDOW = timedelta(days=30)

# Withings answers getintradayactivity with at most the first 24 h after startdate,
# so a longer window is walked a day at a time.
_INTRADAY_MAX_WINDOW = timedelta(days=1)

# Withings hardware is numbered up to 102; 1051 and above are third-party trackers
# relayed through the account (Apple, Android, GoogleFit, Samsung, Huawei), whose
# steps already reach us from the provider that recorded them.
_RELAYED_MODEL_ID_FLOOR = 1000

# Every mapped meastype is requested in one getmeas call. Derived from the
# coverage map, so it lives here rather than with the request definitions.
_REQUESTED_MEASTYPES = ",".join(str(code) for code in MEASURE_TYPE_MAP)


def _zone_for(timezones: dict[date_type, str | None], moment: datetime) -> str | None:
    """The zone reported for the slice's day, falling back to the most recent earlier day.

    A slice near midnight UTC belongs to a local day the map may key differently, and a
    day Withings reported no activity for has no row of its own.
    """
    day = moment.date()
    if day in timezones:
        return timezones[day]
    earlier = [known for known in timezones if known < day]
    return timezones[max(earlier)] if earlier else None


def _daily_total_instants(timezones: dict[date_type, str | None]) -> set[datetime]:
    """The instants ``save_activity`` stores each day's totals at.

    A series row is keyed by its instant alone, so a slice landing on one would upsert the
    day's total away. The two are written in separate batches, so nothing else catches it.
    """
    instants: set[datetime] = set()
    for day, zone_name in timezones.items():
        day_start, _ = local_day_start(day, zone_name, logger, action="intraday_day_start_invalid")
        instants.add(day_start)
    return instants


class Withings247Data(Base247DataTemplate):
    """Withings continuous-data handler."""

    def __init__(self, provider_name: str, api_base_url: str, oauth: BaseOAuthTemplate) -> None:
        super().__init__(provider_name, api_base_url, oauth)
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.connection_repo = UserConnectionRepository()

    # ---------------------- Body measures (getmeas) ----------------------

    def _active_connection_id(self, db: DbSession, user_id: UUID) -> UUID | None:
        connection = self.connection_repo.get_active_connection(db, user_id, self.provider_name)
        return connection.id if connection is not None and isinstance(connection.id, UUID) else None

    def normalize_measures(
        self,
        groups: list[dict],
        user_id: UUID,
        user_connection_id: UUID | None = None,
        *,
        default_timezone: str | None = None,
    ) -> list[TimeSeriesSampleCreate]:
        """Normalize measure groups, preferring each group timezone over the response timezone."""
        samples: list[TimeSeriesSampleCreate] = []
        for group in groups:
            # Tolerate a malformed group without dropping the rest of the batch.
            try:
                parsed = WithingsMeasureGroup.model_validate(group)
            except ValidationError as e:
                log_structured(
                    logger,
                    "warning",
                    "Skipping unparseable Withings measure group",
                    provider=self.provider_name,
                    action="measure_group_validation_failed",
                    user_id=str(user_id),
                    error=str(e),
                )
                continue
            samples.extend(self._normalize_measure_group(parsed, user_id, user_connection_id, default_timezone))
        return samples

    def _normalize_measure_group(
        self,
        group: WithingsMeasureGroup,
        user_id: UUID,
        user_connection_id: UUID | None,
        default_timezone: str | None = None,
    ) -> list[TimeSeriesSampleCreate]:
        ts = datetime.fromtimestamp(group.date, tz=timezone.utc)
        zone_offset = zone_offset_at(
            group.timezone or default_timezone,
            ts,
            logger,
            action="measure_timezone_invalid",
            user_id=str(user_id),
        )
        external_id = str(group.grpid) if group.grpid is not None else None
        samples: list[TimeSeriesSampleCreate] = []
        for measure in group.measures:
            series_type = MEASURE_TYPE_MAP.get(measure.type)
            if series_type is None:
                continue
            value = scale_measure(measure)
            factor = MEASURE_UNIT_FACTOR.get(measure.type)
            if factor is not None:
                value = value * factor
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    provider=self.provider_name,
                    user_connection_id=user_connection_id,
                    external_id=external_id,
                    recorded_at=ts,
                    zone_offset=zone_offset,
                    value=value,
                    series_type=series_type,
                )
            )
        return samples

    def save_measures(self, db: DbSession, user_id: UUID, start: datetime, end: datetime) -> int:
        user_connection_id = self._active_connection_id(db, user_id)
        page = paginate(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path=MEASURES.service_path,
            action=MEASURES.action,
            params={
                "meastypes": _REQUESTED_MEASTYPES,
                "category": 1,
                "startdate": int(start.timestamp()),
                "enddate": int(end.timestamp()),
            },
            list_key=MEASURES.list_key,
        )
        samples = self.normalize_measures(
            page.rows,
            user_id,
            user_connection_id,
            default_timezone=page.envelope.get("timezone"),
        )
        if not samples:
            return 0
        counts = timeseries_service.bulk_create_samples(db, samples)
        db.commit()
        return counts

    # ---------------------- Daily activity (getactivity) ----------------------

    def normalize_activity(
        self,
        rows: list[dict],
        user_id: UUID,
        user_connection_id: UUID | None = None,
    ) -> list[TimeSeriesSampleCreate]:
        samples: list[TimeSeriesSampleCreate] = []
        for row in rows:
            # Tolerate a malformed row without dropping the rest of the batch.
            try:
                activity = WithingsActivity.model_validate(row)
            except ValidationError as e:
                log_structured(
                    logger,
                    "warning",
                    "Skipping unparseable Withings activity row",
                    provider=self.provider_name,
                    action="activity_row_validation_failed",
                    user_id=str(user_id),
                    error=str(e),
                )
                continue
            # Withings documents brand=18 as external and brand=1 as Withings.
            # deviceid is only an identifier and may be absent on valid rows.
            if activity.brand == 18:
                logger.debug("Skipping externally sourced Withings activity for %s", activity.date)
                continue
            ts, zone_offset = local_day_start(
                activity.date,
                activity.timezone,
                logger,
                action="activity_timezone_invalid",
                user_id=str(user_id),
            )
            for field, series_type in ACTIVITY_FIELD_MAP.items():
                value = getattr(activity, field)
                if value is None:
                    continue
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        provider=self.provider_name,
                        user_connection_id=user_connection_id,
                        external_id=f"activity:{activity.date}:{series_type.value}",
                        recorded_at=ts,
                        zone_offset=zone_offset,
                        value=Decimal(str(value)),
                        series_type=series_type,
                        is_daily_total=daily_total_flag(series_type, is_daily=True),
                    )
                )
            if activity.totalcalories is not None and activity.calories is not None:
                passive_calories = Decimal(str(activity.totalcalories)) - Decimal(str(activity.calories))
                if passive_calories >= 0:
                    samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            source=self.provider_name,
                            provider=self.provider_name,
                            user_connection_id=user_connection_id,
                            external_id=f"activity:{activity.date}:{SeriesType.basal_energy.value}",
                            recorded_at=ts,
                            zone_offset=zone_offset,
                            value=passive_calories,
                            series_type=SeriesType.basal_energy,
                            is_daily_total=daily_total_flag(SeriesType.basal_energy, is_daily=True),
                        )
                    )
        return samples

    @staticmethod
    def _ymd_window(start: datetime, end: datetime) -> tuple[str, str]:
        """Widen a UTC window to cover the local-date boundaries Withings queries."""
        return (start - timedelta(days=1)).strftime("%Y-%m-%d"), (end + timedelta(days=1)).strftime("%Y-%m-%d")

    def save_activity(
        self,
        db: DbSession,
        user_id: UUID,
        start: datetime,
        end: datetime,
    ) -> int:
        user_connection_id = self._active_connection_id(db, user_id)
        start_ymd, end_ymd = self._ymd_window(start, end)
        rows = paginate(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path=ACTIVITY.service_path,
            action=ACTIVITY.action,
            params={
                "startdateymd": start_ymd,
                "enddateymd": end_ymd,
                "data_fields": ",".join(ACTIVITY.data_fields),
            },
            list_key=ACTIVITY.list_key,
        ).rows
        samples = self.normalize_activity(rows, user_id, user_connection_id)
        if not samples:
            return 0
        counts = timeseries_service.bulk_create_samples(db, samples)
        db.commit()
        return counts

    # ---------------------- Intraday activity (getintradayactivity) ----------------------

    def _window_timezones(
        self,
        db: DbSession,
        user_id: UUID,
        start: datetime,
        end: datetime,
    ) -> dict[date_type, str | None]:
        """Map each day with a daily row to the zone Withings reported for it, if any.

        The keys decide which days get an intraday request, so a day without a zone stays in.
        """
        start_ymd, end_ymd = self._ymd_window(start, end)
        rows = paginate(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path=ACTIVITY.service_path,
            action=ACTIVITY.action,
            params={"startdateymd": start_ymd, "enddateymd": end_ymd},
            list_key=ACTIVITY.list_key,
        ).rows
        timezones: dict[date_type, str | None] = {}
        for row in rows:
            try:
                activity = WithingsActivity.model_validate(row)
            except ValidationError:
                continue
            # Only the rows save_activity keeps decide where the day's total sits.
            if activity.brand == 18:
                continue
            timezones[activity.date] = activity.timezone
        return timezones

    def normalize_intraday_activity(
        self,
        series: dict[str, Any],
        user_id: UUID,
        user_connection_id: UUID | None = None,
        timezones: dict[date_type, str | None] | None = None,
    ) -> list[TimeSeriesSampleCreate]:
        """Turn the epoch-keyed slices into samples carrying the same measures as the daily rows.

        A slice is keyed by an absolute epoch, but an hour of the day is a local one, so
        each sample takes the offset Withings reported for that day; ``timezones`` supplies
        it, because the intraday response itself carries no zone.
        """
        samples: list[TimeSeriesSampleCreate] = []
        reserved = _daily_total_instants(timezones or {})
        for epoch, row in series.items():
            try:
                recorded_at = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
            except (TypeError, ValueError):
                log_structured(
                    logger,
                    "warning",
                    "Skipping Withings intraday slice keyed by an unreadable epoch",
                    provider=self.provider_name,
                    action="intraday_epoch_invalid",
                    user_id=str(user_id),
                    epoch=str(epoch),
                )
                continue
            # Tolerate a malformed slice without dropping the rest of the day.
            try:
                activity_slice = WithingsIntradayActivity.model_validate(row)
            except ValidationError as e:
                log_structured(
                    logger,
                    "warning",
                    "Skipping unparseable Withings intraday slice",
                    provider=self.provider_name,
                    action="intraday_slice_validation_failed",
                    user_id=str(user_id),
                    error=str(e),
                )
                continue
            if activity_slice.model_id is not None and activity_slice.model_id >= _RELAYED_MODEL_ID_FLOOR:
                continue
            if recorded_at in reserved:
                continue
            zone_name = _zone_for(timezones or {}, recorded_at)
            zone_offset = (
                zone_offset_at(
                    zone_name,
                    recorded_at,
                    logger,
                    action="intraday_timezone_invalid",
                    user_id=str(user_id),
                )
                if zone_name
                else None
            )
            for field, series_type in ACTIVITY_FIELD_MAP.items():
                value = getattr(activity_slice, field)
                if value is None:
                    continue
                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=self.provider_name,
                        provider=self.provider_name,
                        user_connection_id=user_connection_id,
                        external_id=f"intraday:{epoch}:{series_type.value}",
                        recorded_at=recorded_at,
                        zone_offset=zone_offset,
                        value=Decimal(str(value)),
                        series_type=series_type,
                        is_daily_total=daily_total_flag(series_type, is_daily=False),
                    )
                )
        return samples

    def save_intraday_activity(
        self,
        db: DbSession,
        user_id: UUID,
        start: datetime,
        end: datetime,
    ) -> int:
        """Store the intraday slices, one request per day that has a daily row.

        The action returns at most 24 h per call, and asking for days without data would spend
        the per-minute quota the other domains need.
        """
        user_connection_id = self._active_connection_id(db, user_id)
        timezones = self._window_timezones(db, user_id, start, end)
        if not timezones:
            return 0
        samples: list[TimeSeriesSampleCreate] = []
        for day, zone_name in sorted(timezones.items()):
            day_start, _ = local_day_start(day, zone_name, logger, action="intraday_day_start_invalid")
            try:
                series = paginate_mapping(
                    db=db,
                    user_id=user_id,
                    connection_repo=self.connection_repo,
                    oauth=self.oauth,
                    service_path=INTRADAY_ACTIVITY.service_path,
                    action=INTRADAY_ACTIVITY.action,
                    params={
                        "startdate": int(day_start.timestamp()),
                        "enddate": int((day_start + _INTRADAY_MAX_WINDOW).timestamp()),
                        "data_fields": ",".join(INTRADAY_ACTIVITY.data_fields),
                    },
                    map_key=INTRADAY_ACTIVITY.list_key,
                )
            except Exception as e:
                if not samples:
                    raise
                log_structured(
                    logger,
                    "warning",
                    f"Returning partial Withings intraday activity due to error: {e}",
                    provider=self.provider_name,
                    action="withings_api_partial_data",
                    user_id=str(user_id),
                )
                break
            samples.extend(self.normalize_intraday_activity(series, user_id, user_connection_id, timezones))
        if not samples:
            return 0
        counts = timeseries_service.bulk_create_samples(db, samples)
        db.commit()
        return counts

    # ---------------------- Sleep (getsummary) ----------------------

    def save_sleep(
        self,
        db: DbSession,
        user_id: UUID,
        start: datetime,
        end: datetime,
    ) -> int:
        user_connection_id = self._active_connection_id(db, user_id)
        start_ymd, end_ymd = self._ymd_window(start, end)
        rows = paginate(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path=SLEEP_SUMMARY.service_path,
            action=SLEEP_SUMMARY.action,
            params={
                "startdateymd": start_ymd,
                "enddateymd": end_ymd,
                "data_fields": ",".join(SLEEP_SUMMARY.data_fields),
            },
            list_key=SLEEP_SUMMARY.list_key,
        ).rows
        # One request per window, not per night: the free plan caps the app at 120/min.
        # Keyed on the nights themselves, since getsummary works on whole local days and
        # returns nights that start after the requested window ends.
        # A row the window cannot be read from is left to _save_sleep_row to report,
        # rather than failing the whole batch here.
        nights = [
            _Night(start, self._epoch_or_none(row.get("enddate")) or start)
            for row in rows
            if isinstance(row, dict) and (start := self._epoch_or_none(row.get("startdate"))) is not None
        ]
        window_stages = self._fetch_sleep_stages(db, user_id, nights) if nights else []
        processed = 0
        samples: list[TimeSeriesSampleCreate] = []
        for row in rows:
            # Tolerate a malformed night without dropping the rest of the batch.
            try:
                night_samples = self._save_sleep_row(db, user_id, row, user_connection_id, window_stages)
                if night_samples is not None:
                    processed += 1
                    samples.extend(night_samples)
            except Exception as e:
                db.rollback()
                log_and_capture_error(
                    e,
                    logger,
                    "Skipping unparseable Withings sleep row",
                    level="warning",
                    extra={"provider": "withings", "user_id": str(user_id)},
                )
        if samples:
            timeseries_service.bulk_create_samples(db, samples)
            db.commit()
        return processed

    def _fetch_sleep_stages(
        self,
        db: DbSession,
        user_id: UUID,
        nights: list[_Night],
    ) -> list[SleepStage]:
        """Fetch the hypnogram covering the given nights. Empty when it is unavailable.

        The endpoint truncates long ranges without setting `more`, so the nights are walked
        with a cursor. A page that adds nothing means an empty stretch, not the end of the
        data, so the cursor moves on to the next night.
        """
        stages: list[SleepStage] = []
        seen: set[tuple[int, int]] = set()
        starts = sorted(datetime.fromtimestamp(night.start, tz=timezone.utc) for night in nights)
        end_dt = datetime.fromtimestamp(max(night.end for night in nights), tz=timezone.utc)
        cursor = starts[0]
        # A page reaches at least a day and a night is shorter, so a night costs at most
        # two: one for its stages, one for the empty stretch that follows it.
        for _ in range(2 * len(nights)):
            try:
                body = withings_request(
                    db=db,
                    user_id=user_id,
                    connection_repo=self.connection_repo,
                    oauth=self.oauth,
                    service_path=SLEEP_SERIES.service_path,
                    action=SLEEP_SERIES.action,
                    params={"startdate": int(cursor.timestamp()), "enddate": int(end_dt.timestamp())},
                )
            except Exception as e:
                log_and_capture_error(
                    e,
                    logger,
                    "Withings sleep series fetch failed",
                    level="warning",
                    extra={"provider": "withings", "user_id": str(user_id)},
                )
                break

            rows = body.get(SLEEP_SERIES.list_key) or []
            if isinstance(rows, dict):
                rows = [rows]

            newest = cursor
            for row in rows:
                try:
                    entry = WithingsSleepSeriesEntry.model_validate(row)
                except ValidationError:
                    continue
                interval_end = datetime.fromtimestamp(entry.enddate, tz=timezone.utc)
                newest = max(newest, interval_end)
                stage = SLEEP_STATE_STAGE_MAP.get(entry.state)
                # A page starts on the previous one's last interval, so it repeats it.
                if stage is None or (entry.startdate, entry.enddate) in seen:
                    continue
                seen.add((entry.startdate, entry.enddate))
                stages.append(
                    SleepStage(
                        stage=stage,
                        start_time=datetime.fromtimestamp(entry.startdate, tz=timezone.utc),
                        end_time=interval_end,
                    )
                )

            if newest >= end_dt:
                break
            if newest > cursor:
                cursor = newest
                continue
            next_night = next((start for start in starts if start > cursor), None)
            if next_night is None:
                break
            cursor = next_night
        else:
            log_structured(
                logger,
                "warning",
                "Withings sleep series walk ran out of requests; later nights keep no stages",
                provider="withings",
                user_id=str(user_id),
                nights=len(nights),
                stopped_at=cursor.isoformat(),
            )

        return self._merge_adjacent(sorted(stages, key=lambda s: s.start_time))

    @staticmethod
    def _merge_adjacent(stages: list[SleepStage]) -> list[SleepStage]:
        """Fold runs of one stage into a single interval.

        The endpoint returns minute-by-minute states for the first night of a range and
        merged blocks for the rest, so a night's shape would otherwise depend on where
        it fell in the request.
        """
        merged: list[SleepStage] = []
        for stage in stages:
            previous = merged[-1] if merged else None
            if previous and previous.stage == stage.stage and previous.end_time >= stage.start_time:
                previous.end_time = max(previous.end_time, stage.end_time)
                continue
            merged.append(stage.model_copy())
        return merged

    @staticmethod
    def _epoch_or_none(value: Any) -> int | None:
        """Epoch seconds a datetime can hold, or None — a nonsense value belongs to its own row."""
        try:
            epoch = int(value)
            datetime.fromtimestamp(epoch, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            return None
        return epoch

    @staticmethod
    def _stages_within(stages: list[SleepStage], start_dt: datetime, end_dt: datetime) -> list[SleepStage] | None:
        """Take one night out of a window hypnogram, clipped to that night."""
        night = []
        for stage in stages:
            if not start_dt <= stage.start_time < end_dt:
                continue
            end = min(stage.end_time, end_dt)
            if end <= stage.start_time:
                continue
            night.append(stage.model_copy(update={"end_time": end}))
        return night or None

    def _save_sleep_row(
        self,
        db: DbSession,
        user_id: UUID,
        row: dict,
        user_connection_id: UUID | None,
        window_stages: list[SleepStage],
    ) -> list[TimeSeriesSampleCreate] | None:
        """Save one night and return its samples, or None when the night was not saved."""
        summary = WithingsSleepSummary.model_validate(row)
        start_dt = datetime.fromtimestamp(summary.startdate, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(summary.enddate, tz=timezone.utc)
        zone_offset = zone_offset_at(
            summary.timezone,
            end_dt,
            logger,
            action="sleep_timezone_invalid",
            user_id=str(user_id),
            sleep_id=summary.id,
        )
        data = summary.data

        # Stage durations are null for nights imported from an external source.
        stage_sleep_seconds = sum(
            duration
            for duration in (data.deepsleepduration, data.lightsleepduration, data.remsleepduration)
            if duration is not None
        )
        total_sleep_seconds = (
            data.total_sleep_time
            if data.total_sleep_time is not None
            else data.asleepduration
            if data.asleepduration is not None
            else stage_sleep_seconds
        )
        awake_seconds = data.wakeupduration or 0
        time_in_bed_seconds = (
            data.total_timeinbed if data.total_timeinbed is not None else total_sleep_seconds + awake_seconds
        )
        if time_in_bed_seconds <= 0:
            time_in_bed_seconds = int((end_dt - start_dt).total_seconds())
        if total_sleep_seconds < 0 or time_in_bed_seconds < 0:
            raise ValueError("Withings sleep durations must not be negative")
        efficiency = data.sleep_efficiency

        record_id = uuid4()
        sleep_stages = self._stages_within(window_stages, start_dt, end_dt)
        record = EventRecordCreate(
            id=record_id,
            category="sleep",
            type="sleep_session",
            source_name="Withings",
            duration_seconds=time_in_bed_seconds,
            start_datetime=start_dt,
            end_datetime=end_dt,
            zone_offset=zone_offset,
            external_id=str(summary.id) if summary.id is not None else None,
            source=self.provider_name,
            provider=self.provider_name,
            user_connection_id=user_connection_id,
            user_id=user_id,
        )
        detail = EventRecordDetailCreate(
            record_id=record_id,
            sleep_total_duration_minutes=total_sleep_seconds // 60,
            sleep_time_in_bed_minutes=time_in_bed_seconds // 60,
            # sleep_efficiency is a 0–1 ratio; stored on the 0–100 scale.
            sleep_efficiency_score=Decimal(str(efficiency * 100)) if efficiency is not None else None,
            sleep_deep_minutes=data.deepsleepduration // 60 if data.deepsleepduration is not None else None,
            sleep_light_minutes=data.lightsleepduration // 60 if data.lightsleepduration is not None else None,
            sleep_rem_minutes=data.remsleepduration // 60 if data.remsleepduration is not None else None,
            sleep_awake_minutes=data.wakeupduration // 60 if data.wakeupduration is not None else None,
            is_nap=False,
            sleep_stages=sleep_stages,
        )
        try:
            event_record_service.create_or_merge_sleep(db, user_id, record, detail, settings.sleep_end_gap_minutes)
        except Exception as e:
            db.rollback()
            log_and_capture_error(
                e,
                logger,
                "Withings sleep save error",
                extra={"provider": "withings", "user_id": str(user_id)},
            )
            return None

        # Withings publishes no resting heart rate; the night's lowest is what Oura and Suunto map too.
        if data.hr_min is None:
            return []
        return [
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user_id,
                provider=self.provider_name,
                source=self.provider_name,
                user_connection_id=user_connection_id,
                recorded_at=start_dt,
                # The record keys on the night's end; a sample stamped at its start can sit
                # on the other side of a DST change.
                zone_offset=zone_offset_at(
                    summary.timezone,
                    start_dt,
                    logger,
                    action="sleep_timezone_invalid",
                    user_id=str(user_id),
                    sleep_id=summary.id,
                ),
                value=data.hr_min,
                series_type=SeriesType.resting_heart_rate,
            )
        ]

    # ---------------------- Combined load ----------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, int]:
        """Sync-task entry point.

        Each domain runs independently so one failure doesn't abort the others,
        and each failure is captured where it happens rather than aggregated into
        a raise — matching every other provider's 24/7 handler.
        """
        # Callers pass the window as datetimes, ISO strings or nothing (Celery task,
        # sync route, webhook replay); Suunto resolves it the same way.
        end_time = parse_datetime_or_default(end_time, datetime.now(timezone.utc))
        start_time = parse_datetime_or_default(start_time, end_time - _DEFAULT_SYNC_WINDOW)

        results: dict[str, int] = {}
        for name, fn in (
            ("measures", self.save_measures),
            ("activity", self.save_activity),
            ("sleep", self.save_sleep),
            # Last: it spends one request per active day, far more than the others, and a
            # throttle it triggers must not be what stops them from running at all.
            ("intraday_activity", self.save_intraday_activity),
        ):
            try:
                results[name] = fn(db, user_id, start_time, end_time)
            except Exception as e:
                # A failed domain reports zero rows rather than going missing, so a
                # caller reading the counts sees the gap instead of a short dict.
                results[name] = 0
                # Reset the session for the next domain; a failing rollback must
                # not itself abort the remaining domains.
                try:
                    db.rollback()
                except Exception as rollback_error:
                    log_and_capture_error(
                        rollback_error,
                        logger,
                        f"Withings {name} rollback failed",
                        extra={"provider": "withings", "data_type": name, "user_id": str(user_id)},
                    )
                log_and_capture_error(
                    e,
                    logger,
                    f"Withings {name} sync failed: {e}",
                    extra={"provider": "withings", "data_type": name, "user_id": str(user_id)},
                )
        return results

    # Withings uses load_and_save_all(); inherited single-domain hooks must fail loudly.

    def _unsupported(self, feature: str) -> NoReturn:
        raise NotImplementedError(f"Withings 24/7 data uses load_and_save_all(); {feature} is not used")

    def get_sleep_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        self._unsupported("get_sleep_data")

    def normalize_sleep(self, raw_sleep: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        self._unsupported("normalize_sleep")

    def get_recovery_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        self._unsupported("get_recovery_data")

    def normalize_recovery(self, raw_recovery: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        self._unsupported("normalize_recovery")

    def get_activity_samples(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        self._unsupported("get_activity_samples")

    def normalize_activity_samples(
        self, raw_samples: list[dict[str, Any]], user_id: UUID
    ) -> dict[str, list[dict[str, Any]]]:
        self._unsupported("normalize_activity_samples")

    def get_daily_activity_statistics(
        self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        self._unsupported("get_daily_activity_statistics")

    def normalize_daily_activity(self, raw_stats: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        self._unsupported("normalize_daily_activity")
