"""Sleep score service.

Exposes three entry points for computing a per-night OW sleep score using the
four-pillar algorithm (duration, stages, consistency, interruptions):

- SleepScoreService.get_sleep_score              - pure calculation; accepts raw sleep parameters
- SleepScoreService.get_sleep_score_for_user     - DB-backed; single date, two DB queries
- SleepScoreService.get_sleep_scores_for_date_range - DB-backed; multiple dates, one DB query
"""

from datetime import date, datetime, timedelta, timezone
from logging import Logger, getLogger
from uuid import UUID

from pydantic import BaseModel

from app.algorithms.config_algorithms import sleep_config
from app.algorithms.sleep import SleepScoreResult, calculate_overall_sleep_score
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.models import EventRecord, SleepDetails
from app.repositories.event_record_repository import EventRecordRepository
from app.schemas.model_crud.activities import EventRecordQueryParams
from app.schemas.model_crud.activities.sleep import SleepStage
from app.utils.exceptions import ResourceNotFoundError, handle_exceptions
from app.utils.structured_logging import log_structured


class WasoData(BaseModel):
    total_awake_minutes: float
    awakening_durations: list[float]


class SleepScoreService:
    """Service for computing per-night sleep scores."""

    def __init__(self, log: Logger):
        self.logger = log
        self.event_record_repo = EventRecordRepository(EventRecord)

    @staticmethod
    def _apply_zone_offset(dt: datetime, zone_offset: str | None) -> datetime:
        """Return dt converted to local time using the stored zone_offset string.

        Falls back to the original value when zone_offset is unavailable so that
        providers that omit it continue to work unchanged.
        """
        if zone_offset is None:
            return dt
        sign = 1 if zone_offset[0] == "+" else -1
        hours, minutes = int(zone_offset[1:3]), int(zone_offset[4:6])
        offset = timedelta(hours=sign * hours, minutes=sign * minutes)
        tz = timezone(offset)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz)

    def _parse_wearable_stages_for_interruptions(
        self,
        sleep_stages: list[SleepStage],
    ) -> WasoData:
        """Strip sleep latency and morning lying-in-bed periods to calculate true WASO.

        Returns total WASO minutes and individual awakening durations.
        """
        if not sleep_stages:
            return WasoData(total_awake_minutes=0.0, awakening_durations=[])

        sleep_indices = [i for i, s in enumerate(sleep_stages) if s.stage != SleepStageType.AWAKE]
        if not sleep_indices:
            return WasoData(total_awake_minutes=0.0, awakening_durations=[])

        first_sleep_idx = sleep_indices[0]
        last_sleep_idx = sleep_indices[-1]

        true_sleep_period = sleep_stages[first_sleep_idx : last_sleep_idx + 1]

        waso_total_minutes = 0.0
        awakening_durations: list[float] = []
        for block in true_sleep_period:
            if block.stage == SleepStageType.AWAKE:
                duration_mins = (block.end_time - block.start_time).total_seconds() / 60.0
                waso_total_minutes += duration_mins
                awakening_durations.append(duration_mins)

        return WasoData(
            total_awake_minutes=waso_total_minutes,
            awakening_durations=awakening_durations,
        )

    def get_sleep_score(
        self,
        total_sleep_duration_minutes: float,
        deep_minutes: float,
        rem_minutes: float,
        awake_minutes: float,
        session_start: datetime,
        historical_bedtimes: list[datetime],
        sleep_stages: list[SleepStage] | None = None,
    ) -> SleepScoreResult:
        """Calculate a sleep score from raw sleep parameters for a single night.

        If sleep_stages is provided it is used to derive true WASO (strips sleep
        latency and morning lie-in). Otherwise awake_minutes is used as a fallback
        for interruption scoring.

        total_sleep_duration_minutes is expected to be net sleep (awake time already
        excluded), as stored by wearable providers. awake_minutes / stage-derived WASO
        feeds only the interruptions pillar.
        """
        if not total_sleep_duration_minutes or total_sleep_duration_minutes <= 0:
            raise ValueError(
                "Cannot calculate sleep score: total_sleep_duration_minutes must be"
                f" > 0, got {total_sleep_duration_minutes}"
            )

        if sleep_stages:
            waso = self._parse_wearable_stages_for_interruptions(sleep_stages)
            total_awake = waso.total_awake_minutes
            awakening_durations = waso.awakening_durations
        else:
            total_awake = awake_minutes
            awakening_durations = []

        return calculate_overall_sleep_score(
            total_sleep_minutes=total_sleep_duration_minutes,
            deep_minutes=deep_minutes,
            rem_minutes=rem_minutes,
            session_start=session_start.isoformat(),
            historical_bedtimes=[dt.isoformat() for dt in historical_bedtimes],
            total_awake_minutes=total_awake,
            awakening_durations=awakening_durations,
        )

    @handle_exceptions
    def get_sleep_score_for_user(
        self,
        db_session: DbSession,
        user_id: UUID,
        sleep_date: date,
    ) -> SleepScoreResult:
        """Fetch sleep data for a user on a given date and return their sleep score.

        sleep_date is the calendar date on which the sleep session started (bedtime
        date). The longest non-nap session that started on that date is used.
        Historical bedtimes from the prior rolling window are fetched for consistency
        scoring.
        """
        day_start = datetime(sleep_date.year, sleep_date.month, sleep_date.day)

        # Fetch sessions that started on sleep_date (broader window, post-filter below).
        records, _ = self.event_record_repo.get_records_with_filters(
            db_session,
            EventRecordQueryParams(
                category="sleep",
                start_datetime=day_start,
                sort_by="start_datetime",
                sort_order="asc",
                limit=20,
            ),
            str(user_id),
        )

        # Keep non-nap sessions that actually started on sleep_date (local time).
        sessions = [
            (record, detail)
            for record, _ in records
            if self._apply_zone_offset(record.start_datetime, record.zone_offset).date() == sleep_date
            and isinstance((detail := record.detail), SleepDetails)
            and not detail.is_nap
        ]

        if not sessions:
            raise ResourceNotFoundError(f"sleep data for user {user_id} on {sleep_date}")

        record, detail = max(sessions, key=lambda s: s[1].sleep_total_duration_minutes or 0)

        # Fetch historical bedtimes for consistency scoring.
        history_start = day_start - timedelta(days=sleep_config.rolling_window_nights + 1)
        hist_records, _ = self.event_record_repo.get_records_with_filters(
            db_session,
            EventRecordQueryParams(
                category="sleep",
                start_datetime=history_start,
                end_datetime=day_start,
                sort_by="start_datetime",
                sort_order="desc",
                # Use a generous multiplier so deduplication always has enough
                # raw records even when multiple sources sync the same night.
                limit=sleep_config.rolling_window_nights * 4,
            ),
            str(user_id),
        )

        # Deduplicate by calendar date so multiple sessions on one night (e.g. two
        # sources syncing the same sleep, or a split session) don't crowd out earlier
        # nights in the rolling window.
        # TODO: this is a simplification — a user may have genuinely separate sleep
        # periods on one night (woke up fully, went back to bed, or switched devices).
        # Device priority (already used elsewhere in the codebase) could help pick the
        # most trustworthy record per night. Revisit when we have a smarter
        # session-merging / source-priority strategy.
        seen_nights: set[date] = set()
        historical_bedtimes: list[datetime] = []
        for r, _ in hist_records:
            if isinstance(r.detail, SleepDetails) and not r.detail.is_nap:
                local_start = self._apply_zone_offset(r.start_datetime, r.zone_offset)
                night = local_start.date()
                if night not in seen_nights:
                    seen_nights.add(night)
                    historical_bedtimes.append(local_start)
            if len(historical_bedtimes) >= sleep_config.rolling_window_nights:
                break

        sleep_stages: list[SleepStage] | None = None
        if detail.sleep_stages:
            sleep_stages = [SleepStage(**s) for s in detail.sleep_stages]

        return self.get_sleep_score(
            total_sleep_duration_minutes=float(detail.sleep_total_duration_minutes or 0),
            deep_minutes=float(detail.sleep_deep_minutes or 0),
            rem_minutes=float(detail.sleep_rem_minutes or 0),
            awake_minutes=float(detail.sleep_awake_minutes or 0),
            session_start=self._apply_zone_offset(record.start_datetime, record.zone_offset),
            historical_bedtimes=historical_bedtimes,
            sleep_stages=sleep_stages,
        )

    def get_sleep_scores_for_records(
        self,
        db_session: DbSession,
        user_id: UUID,
        record_wakes: list[tuple[UUID, date]],
    ) -> dict[tuple[UUID, date], SleepScoreResult]:
        """Calculate sleep scores for specific event records identified by ID.

        Accepts (record_id, wake_date) pairs so each session is matched exactly
        — no date-collision issues for users in extreme time zones. Returns a
        dict keyed by the same (record_id, wake_date) tuples so callers can
        retrieve the wake_date when persisting recorded_at.

        Calculation logic (historical bedtimes, stage parsing, algorithm) is
        unchanged relative to get_sleep_scores_for_date_range.
        """
        if not record_wakes:
            return {}

        target_ids = {r_id for r_id, _ in record_wakes}
        wake_by_id = {r_id: wake_d for r_id, wake_d in record_wakes}

        earliest_wake = min(wake_d for _, wake_d in record_wakes)
        latest_wake = max(wake_d for _, wake_d in record_wakes)

        # Fetch a window broad enough to cover target sessions (which may start
        # the evening before their wake_date) plus rolling history for consistency.
        window_start = datetime(earliest_wake.year, earliest_wake.month, earliest_wake.day) - timedelta(
            days=sleep_config.rolling_window_nights + 2
        )
        window_end = datetime(latest_wake.year, latest_wake.month, latest_wake.day) + timedelta(days=2)

        all_records, _ = self.event_record_repo.get_records_with_filters(
            db_session,
            EventRecordQueryParams(
                category="sleep",
                start_datetime=window_start,
                end_datetime=window_end,
                sort_by="start_datetime",
                sort_order="asc",
                limit=min(1000, (len(record_wakes) + sleep_config.rolling_window_nights) * 4),
            ),
            str(user_id),
        )

        # Build a sorted list of all valid non-nap sessions in the window for
        # history lookup, and separately index the target sessions by record id.
        all_sessions_asc: list[tuple[date, EventRecord, SleepDetails]] = []
        target_by_id: dict[UUID, tuple[EventRecord, SleepDetails]] = {}

        for record, _ in all_records:
            if isinstance((detail := record.detail), SleepDetails) and not detail.is_nap:
                local_start = self._apply_zone_offset(record.start_datetime, record.zone_offset)
                all_sessions_asc.append((local_start.date(), record, detail))
                if record.id in target_ids:
                    target_by_id[record.id] = (record, detail)

        all_sessions_asc.sort(key=lambda x: x[0])

        results: dict[tuple[UUID, date], SleepScoreResult] = {}
        skipped: list[tuple[UUID, str, str]] = []  # (record_id, record_id_str, reason)

        for r_id, (record, detail) in target_by_id.items():
            local_start = self._apply_zone_offset(record.start_datetime, record.zone_offset)
            target_night = local_start.date()

            # Historical bedtimes: non-nap sessions before this one within the
            # rolling window. Deduplicate by calendar start-date so multiple
            # sources on the same night don't crowd out earlier history.
            history_cutoff = target_night - timedelta(days=sleep_config.rolling_window_nights + 1)
            seen_nights: set[date] = set()
            historical_bedtimes: list[datetime] = []
            for night, hist_record, _ in reversed(all_sessions_asc):
                if night >= target_night:
                    continue
                if night < history_cutoff:
                    break
                if night not in seen_nights:
                    seen_nights.add(night)
                    historical_bedtimes.append(
                        self._apply_zone_offset(hist_record.start_datetime, hist_record.zone_offset)
                    )
                if len(historical_bedtimes) >= sleep_config.rolling_window_nights:
                    break

            sleep_stages: list[SleepStage] | None = None
            if detail.sleep_stages:
                sleep_stages = [SleepStage(**s) for s in detail.sleep_stages]

            try:
                results[(r_id, wake_by_id[r_id])] = self.get_sleep_score(
                    total_sleep_duration_minutes=float(detail.sleep_total_duration_minutes or 0),
                    deep_minutes=float(detail.sleep_deep_minutes or 0),
                    rem_minutes=float(detail.sleep_rem_minutes or 0),
                    awake_minutes=float(detail.sleep_awake_minutes or 0),
                    session_start=local_start,
                    historical_bedtimes=historical_bedtimes,
                    sleep_stages=sleep_stages,
                )
            except (ValueError, OverflowError) as exc:
                skipped.append((r_id, str(record.id), str(exc)))

        if skipped:
            log_structured(
                self.logger,
                "warning",
                f"Skipped sleep score for {len(skipped)} record(s): invalid session data",
                skipped=[{"record_id": rid, "reason": reason} for _, rid, reason in skipped],
            )

        return results

    def get_sleep_scores_for_date_range(
        self,
        db_session: DbSession,
        user_id: UUID,
        dates: list[date],
    ) -> dict[date, SleepScoreResult]:
        """Calculate sleep scores for multiple dates with a single DB query.

        Fetches the full window (target dates + rolling window) once and loops
        in memory, avoiding the multiple queries that repeated get_sleep_score_for_user
        calls would incur.

        Returns a dict mapping each date to its SleepScoreResult. Dates without
        usable sleep data are omitted from the result.
        """
        if not dates:
            return {}

        earliest = min(dates)
        latest = max(dates)

        # Extend the window on each side to accommodate UTC timezone offsets and
        # the fact that sleep sessions end in the early morning hours of the next
        # calendar day.  window_end must reach past the latest possible end_datetime
        # (sleep starting at 23:59 local + 10 h = ~10:00 next day UTC) so we add
        # 2 days instead of 1.
        window_start = datetime(earliest.year, earliest.month, earliest.day) - timedelta(
            days=sleep_config.rolling_window_nights + 2
        )
        window_end = datetime(latest.year, latest.month, latest.day) + timedelta(days=2)

        all_records, _ = self.event_record_repo.get_records_with_filters(
            db_session,
            EventRecordQueryParams(
                category="sleep",
                start_datetime=window_start,
                end_datetime=window_end,
                sort_by="start_datetime",
                sort_order="asc",
                # Override the default limit of 50 — date bounds are the real constraint.
                limit=(len(dates) + sleep_config.rolling_window_nights) * 4,
            ),
            str(user_id),
        )

        # Build a per-night index keeping the longest non-nap session per calendar date.
        sessions_by_date: dict[date, tuple[EventRecord, SleepDetails]] = {}
        for record, _ in all_records:
            if isinstance((detail := record.detail), SleepDetails) and not detail.is_nap:
                local_start = self._apply_zone_offset(record.start_datetime, record.zone_offset)
                night = local_start.date()
                existing = sessions_by_date.get(night)
                if existing is None or (detail.sleep_total_duration_minutes or 0) > (
                    existing[1].sleep_total_duration_minutes or 0
                ):
                    sessions_by_date[night] = (record, detail)

        all_nights_asc = sorted(sessions_by_date)
        target_dates = set(dates)

        results: dict[date, SleepScoreResult] = {}
        skipped: list[tuple[date, str, str]] = []  # (date, record_id, reason)
        for i, sleep_date in enumerate(all_nights_asc):
            if sleep_date not in target_dates:
                continue

            record, detail = sessions_by_date[sleep_date]

            # Historical bedtimes: up to rolling_window_nights nights before this one.
            # i is already the split point — no search needed.
            history_cutoff = sleep_date - timedelta(days=sleep_config.rolling_window_nights + 1)
            prior_nights = all_nights_asc[max(0, i - sleep_config.rolling_window_nights) : i]
            historical_bedtimes = [
                self._apply_zone_offset(sessions_by_date[n][0].start_datetime, sessions_by_date[n][0].zone_offset)
                for n in reversed(prior_nights)
                if n >= history_cutoff
            ]

            sleep_stages: list[SleepStage] | None = None
            if detail.sleep_stages:
                sleep_stages = [SleepStage(**s) for s in detail.sleep_stages]

            try:
                results[sleep_date] = self.get_sleep_score(
                    total_sleep_duration_minutes=float(detail.sleep_total_duration_minutes or 0),
                    deep_minutes=float(detail.sleep_deep_minutes or 0),
                    rem_minutes=float(detail.sleep_rem_minutes or 0),
                    awake_minutes=float(detail.sleep_awake_minutes or 0),
                    session_start=self._apply_zone_offset(record.start_datetime, record.zone_offset),
                    historical_bedtimes=historical_bedtimes,
                    sleep_stages=sleep_stages,
                )
            except (ValueError, OverflowError) as exc:
                skipped.append((sleep_date, str(record.id), str(exc)))

        if skipped:
            log_structured(
                self.logger,
                "warning",
                f"Skipped sleep score for {len(skipped)} date(s): invalid session data",
                skipped=[{"date": str(d), "record_id": rid, "reason": reason} for d, rid, reason in skipped],
            )

        return results


sleep_score_service = SleepScoreService(log=getLogger(__name__))
