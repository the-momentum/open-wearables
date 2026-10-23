"""Resilience score service: HRV-CV calculation and scoring.

ResilienceScoreService.get_hrv_cv_score is DB-backed: it computes a multi-day
HRV coefficient of variation using only samples recorded during sleep, and maps
that CV to a 0–100 resilience score via a linear scale.

Scoring:
    The raw HRV-CV (stored as a 3-decimal-place fraction, e.g. 0.123 = 12.3%)
    is mapped to a 0–100 score using ``_hrv_cv_to_resilience_score``.
    CV ≤ ``cv_ceiling`` (default 7 %) → 100.
    CV ≥ ``cv_floor``   (default 40 %) → 0.
    Between ceiling and floor the score drops linearly.
    Tuning parameters live in ``ResilienceScoreConfig``.
"""

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from logging import Logger, getLogger
from uuid import UUID

from app.algorithms.config_algorithms import resilience_config
from app.algorithms.resilience import calculate_hrv_cv
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.models import EventRecord, SeriesSample
from app.repositories import DataPointSeriesRepository, EventRecordRepository
from app.schemas.enums import SeriesType, get_series_type_id
from app.schemas.model_crud.activities.sleep import SleepStage
from app.schemas.responses.activity.resilience import DailyHrvScore, HrvCvScoreResult

# Stages that represent actual sleep (not just in-bed or awake)
_ASLEEP_STAGES: frozenset[SleepStageType] = frozenset(
    {
        SleepStageType.SLEEPING,
        SleepStageType.LIGHT,
        SleepStageType.DEEP,
        SleepStageType.REM,
    }
)


class ResilienceScoreService:
    """Service for computing HRV-based resilience scores."""

    def __init__(self, log: Logger):
        self.logger = log
        self._data_point_repo = DataPointSeriesRepository(SeriesSample)
        self._event_record_repo = EventRecordRepository(EventRecord)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_utc(self, dt: datetime) -> datetime:
        """Return a timezone-aware datetime in UTC.

        Naive datetimes (no tzinfo) are assumed to be UTC and made aware.
        Aware datetimes with a non-UTC offset are converted to UTC.
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _query_data_series(
        self,
        db_session: DbSession,
        user_id: UUID,
        type_id: int,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[tuple[datetime, float]]:
        """Query raw (recorded_at, value) pairs from SeriesSample via the repository."""
        return self._data_point_repo.query_series(db_session, user_id, type_id, start_dt, end_dt)

    def _extract_asleep_windows(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_dt: datetime,
        end_dt: datetime,
        allowed_stages: frozenset[SleepStageType],
    ) -> list[tuple[datetime, datetime]]:
        """Return time windows during which the user was in an allowed sleep stage.

        Fetches sleep EventRecords overlapping [start_dt, end_dt) via the repository
        and extracts stage-level windows from SleepDetails.sleep_stages JSONB.

        If a session has no stage data, its full session window is used as a single
        asleep window (conservative fallback).
        """
        records = self._event_record_repo.get_sleep_records_with_details(db_session, user_id, start_dt, end_dt)

        windows: list[tuple[datetime, datetime]] = []

        for record, details in records:
            if details is None or not details.sleep_stages:
                # No stage granularity — treat the whole session as asleep
                windows.append(
                    (
                        self._ensure_utc(record.start_datetime),
                        self._ensure_utc(record.end_datetime),
                    )
                )
                continue

            for stage_dict in details.sleep_stages:
                try:
                    stage = SleepStage.model_validate(stage_dict)
                except Exception:
                    continue  # skip malformed entries

                if stage.stage not in allowed_stages:
                    continue

                w_start = self._ensure_utc(stage.start_time)
                w_end = self._ensure_utc(stage.end_time)

                if w_start >= w_end:
                    continue  # skip zero or negative-duration stages

                windows.append((w_start, w_end))

        return windows

    def _filter_points_to_windows(
        self,
        data_points: list[tuple[datetime, float]],
        windows: list[tuple[datetime, datetime]],
    ) -> list[tuple[datetime, float]]:
        """Return only data points whose timestamp falls within a sleep window.

        Uses a half-open interval [window_start, window_end) for each window.
        Each point is counted at most once (breaks after the first matching window).
        """
        if not windows:
            return []

        filtered: list[tuple[datetime, float]] = []
        for ts, value in data_points:
            ts_aware = self._ensure_utc(ts)
            for w_start, w_end in windows:
                if w_start <= ts_aware < w_end:
                    filtered.append((ts, value))
                    break  # avoid double-counting overlapping windows

        return filtered

    def _group_by_day(
        self,
        data_points: list[tuple[datetime, float]],
    ) -> dict[date, list[float]]:
        """Group (timestamp, value) pairs by their UTC calendar date."""
        by_day: dict[date, list[float]] = defaultdict(list)
        for ts, value in data_points:
            by_day[self._ensure_utc(ts).date()].append(value)
        return dict(by_day)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _hrv_cv_to_resilience_score(hrv_cv: float) -> int:
        """Map HRV-CV (0.0–1.0+) to a 0–100 resilience score.

        CV ≤ cv_ceiling (default 7 %)  → 100.
        CV ≥ cv_floor   (default 40 %) → 0.
        Between ceiling and floor the score drops linearly.
        Result is clamped to [0, 100].
        """
        cv_pct = hrv_cv * 100.0

        if cv_pct <= resilience_config.cv_ceiling:
            return 100
        if cv_pct >= resilience_config.cv_floor:
            return 0

        score = (
            100.0 * (resilience_config.cv_floor - cv_pct) / (resilience_config.cv_floor - resilience_config.cv_ceiling)
        )
        return max(0, min(100, round(score)))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_hrv_cv_score(
        self,
        db_session: DbSession,
        user_id: UUID,
        reference_date: date,
    ) -> HrvCvScoreResult:
        """Calculate the HRV coefficient of variation for a configurable lookback window.

        Uses RMSSD as the HRV metric; the SDNN fallback is disabled for now.
        Only HRV samples recorded during sleep periods are used.

        The window covers ``resilience_config.lookback_days`` calendar days *before*
        ``reference_date`` (i.e. [reference_date - N days, reference_date) UTC).

        HRV-CV is calculated only when the number of days with at least one valid
        sample meets or exceeds ``resilience_config.min_days_required``; otherwise
        ``hrv_cv`` is returned as ``None``.

        Args:
            db_session: Active database session.
            user_id: UUID of the user.
            reference_date: Exclusive end date of the lookback window (typically today).

        Returns:
            HrvCvScoreResult with per-day scores and a summary CV value.
        """
        return self.get_hrv_cv_scores_for_date_range(db_session, user_id, [reference_date])[reference_date]

    def get_hrv_cv_scores_for_date_range(
        self,
        db_session: DbSession,
        user_id: UUID,
        reference_dates: list[date],
    ) -> dict[date, HrvCvScoreResult]:
        """Calculate HRV-CV scores for multiple reference dates with a single DB fetch.

        Fetches the full combined window (min reference_date - lookback_days to
        max reference_date) once for sleep windows and HRV data, then computes
        per-date CV in memory — avoiding the repeated overlapping queries that
        individual get_hrv_cv_score calls would incur.

        Uses RMSSD as the HRV metric; the SDNN fallback is disabled for now.

        Returns a dict mapping each reference_date to its HrvCvScoreResult.
        Dates with insufficient data have hrv_cv=None in the result.
        """
        if not reference_dates:
            return {}

        earliest = min(reference_dates)
        latest = max(reference_dates)

        start_dt = datetime.combine(
            earliest - timedelta(days=resilience_config.lookback_days),
            time.min,
            tzinfo=timezone.utc,
        )
        end_dt = datetime.combine(latest, time.min, tzinfo=timezone.utc)

        # Fetch sleep windows and HRV data once for the full combined window.
        windows = self._extract_asleep_windows(db_session, user_id, start_dt, end_dt, _ASLEEP_STAGES)

        rmssd_type_id = get_series_type_id(SeriesType.heart_rate_variability_rmssd)
        hrv_pts = self._query_data_series(db_session, user_id, rmssd_type_id, start_dt, end_dt)
        filtered_hrv = self._filter_points_to_windows(hrv_pts, windows)
        metric_type: str = "RMSSD"

        # NOTE: SDNN fallback is disabled pending validation — only RMSSD is used for now.
        # It falls back *after* sleep filtering: a user wearing multiple devices may have
        # daytime RMSSD from one device and overnight SDNN from another, and daytime-only
        # RMSSD must not block overnight SDNN.
        # if not filtered_hrv:
        #     sdnn_type_id = get_series_type_id(SeriesType.heart_rate_variability_sdnn)
        #     sdnn_pts = self._query_data_series(db_session, user_id, sdnn_type_id, start_dt, end_dt)
        #     filtered_hrv = self._filter_points_to_windows(sdnn_pts, windows)
        #     metric_type = "SDNN"

        # Group all filtered points by UTC date once; reused for every reference_date.
        by_day = self._group_by_day(filtered_hrv)
        # Most wearables send a night's HRV as one value per sleep, not as readings inside it: a night
        # without readings takes its sleep's session value, the provider's where it sent one, else ours.
        for day, value in self._event_record_repo.sleep_values_by_day(
            db_session, user_id, rmssd_type_id, start_dt, end_dt
        ).items():
            by_day.setdefault(day, [value])

        results: dict[date, HrvCvScoreResult] = {}
        for ref_date in reference_dates:
            all_days = [ref_date - timedelta(days=i) for i in range(resilience_config.lookback_days, 0, -1)]

            daily_scores: list[DailyHrvScore] = []
            for d in all_days:
                vals = by_day.get(d, [])
                avg = sum(vals) / len(vals) if vals else None
                daily_scores.append(DailyHrvScore(date=d, hrv_value_ms=avg, has_data=(avg is not None)))

            days_counted = sum(1 for ds in daily_scores if ds.has_data)
            hrv_cv: float | None = None
            resilience_score: int | None = None

            if days_counted >= resilience_config.min_days_required:
                valid_avgs = [ds.hrv_value_ms for ds in daily_scores if ds.hrv_value_ms is not None]
                raw_cv = calculate_hrv_cv(valid_avgs)
                if not math.isnan(raw_cv):
                    hrv_cv = raw_cv
                    resilience_score = self._hrv_cv_to_resilience_score(raw_cv)

            results[ref_date] = HrvCvScoreResult(
                hrv_cv=hrv_cv,
                resilience_score=resilience_score,
                metric_type=metric_type if filtered_hrv else None,
                days_counted=days_counted,
                lookback_days=resilience_config.lookback_days,
                daily_scores=daily_scores,
            )

        return results


resilience_score_service = ResilienceScoreService(log=getLogger(__name__))
