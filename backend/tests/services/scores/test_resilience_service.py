"""Tests for ResilienceScoreService.

Covers two layers:
- Pure helpers (_ensure_utc, _filter_points_to_windows, _group_by_day,
  _extract_asleep_windows, _empty_daily_scores) — no DB.
- DB-backed methods (get_hrv_cv_score, calculate_rmssd_ow, calculate_sdnn_ow)
  using real Postgres via testcontainers with transaction-rollback isolation.
"""

import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.algorithms.config_algorithms import resilience_config
from app.constants.sleep import SleepStageType
from app.models import DataSource, SeriesTypeDefinition
from app.services.scores.resilience_service import ResilienceScoreService
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    SleepDetailsFactory,
    UserFactory,
)

_log = logging.getLogger(__name__)
service = ResilienceScoreService(log=_log)


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _utc(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def _make_stage_dict(stage: str, start_iso: str, end_iso: str) -> dict:
    return {"stage": stage, "start_time": start_iso, "end_time": end_iso}


def _make_stages(start_iso: str, blocks: list[tuple[str, int]]) -> list[dict]:
    """Build contiguous stage dicts from (stage, duration_mins) pairs."""
    stages = []
    current = _utc(start_iso)
    for stage, mins in blocks:
        end = current + timedelta(minutes=mins)
        stages.append(_make_stage_dict(stage, current.isoformat(), end.isoformat()))
        current = end
    return stages


# ---------------------------------------------------------------------------
# Pure helper: _ensure_utc
# ---------------------------------------------------------------------------


class TestEnsureUtc:
    def test_naive_datetime_becomes_utc_aware(self) -> None:
        naive = datetime(2026, 3, 10, 23, 0, 0)
        result = service._ensure_utc(naive)
        assert result.tzinfo == timezone.utc
        assert result.replace(tzinfo=None) == naive

    def test_already_utc_aware_datetime_unchanged(self) -> None:
        aware = datetime(2026, 3, 10, 23, 0, 0, tzinfo=timezone.utc)
        result = service._ensure_utc(aware)
        assert result == aware

    def test_non_utc_aware_datetime_converted_to_utc(self) -> None:
        tz_plus2 = timezone(timedelta(hours=2))
        dt_plus2 = datetime(2026, 3, 10, 13, 0, 0, tzinfo=tz_plus2)  # 13:00+02:00 == 11:00 UTC
        result = service._ensure_utc(dt_plus2)
        assert result.tzinfo == timezone.utc
        assert result == datetime(2026, 3, 10, 11, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Pure helper: _filter_points_to_windows
# ---------------------------------------------------------------------------


class TestFilterPointsToWindows:
    def _pts(self, *isos: str) -> list[tuple[datetime, float]]:
        return [(_utc(iso), float(i + 1) * 10) for i, iso in enumerate(isos)]

    def _win(self, start: str, end: str) -> tuple[datetime, datetime]:
        return (_utc(start), _utc(end))

    def test_empty_windows_returns_empty(self) -> None:
        pts = self._pts("2026-03-10T01:00:00")
        assert service._filter_points_to_windows(pts, []) == []

    def test_empty_points_returns_empty(self) -> None:
        win = [self._win("2026-03-10T00:00:00", "2026-03-10T08:00:00")]
        assert service._filter_points_to_windows([], win) == []

    def test_point_inside_window_is_included(self) -> None:
        pts = self._pts("2026-03-10T02:00:00")
        win = [self._win("2026-03-10T00:00:00", "2026-03-10T08:00:00")]
        result = service._filter_points_to_windows(pts, win)
        assert len(result) == 1

    def test_point_outside_window_is_excluded(self) -> None:
        pts = self._pts("2026-03-10T10:00:00")
        win = [self._win("2026-03-10T00:00:00", "2026-03-10T08:00:00")]
        assert service._filter_points_to_windows(pts, win) == []

    def test_point_at_window_start_included(self) -> None:
        """Half-open [start, end) — start is included."""
        pts = self._pts("2026-03-10T00:00:00")
        win = [self._win("2026-03-10T00:00:00", "2026-03-10T08:00:00")]
        assert len(service._filter_points_to_windows(pts, win)) == 1

    def test_point_at_window_end_excluded(self) -> None:
        """Half-open [start, end) — end is excluded."""
        pts = self._pts("2026-03-10T08:00:00")
        win = [self._win("2026-03-10T00:00:00", "2026-03-10T08:00:00")]
        assert service._filter_points_to_windows(pts, win) == []

    def test_point_in_overlapping_windows_counted_once(self) -> None:
        """Overlapping windows must not double-count a point."""
        pts = self._pts("2026-03-10T02:00:00")
        win = [
            self._win("2026-03-10T00:00:00", "2026-03-10T04:00:00"),
            self._win("2026-03-10T01:00:00", "2026-03-10T05:00:00"),
        ]
        assert len(service._filter_points_to_windows(pts, win)) == 1

    def test_multiple_points_multiple_windows(self) -> None:
        pts = self._pts("2026-03-10T01:00:00", "2026-03-10T05:00:00", "2026-03-10T12:00:00")
        win = [
            self._win("2026-03-10T00:00:00", "2026-03-10T03:00:00"),
            self._win("2026-03-10T04:00:00", "2026-03-10T07:00:00"),
        ]
        result = service._filter_points_to_windows(pts, win)
        assert len(result) == 2  # 12:00 outside both windows

    def test_naive_timestamps_handled_via_ensure_utc(self) -> None:
        """Points with naive datetimes are treated as UTC."""
        naive_ts = datetime(2026, 3, 10, 2, 0, 0)  # no tzinfo
        pts = [(naive_ts, 45.0)]
        win = [self._win("2026-03-10T00:00:00", "2026-03-10T08:00:00")]
        assert len(service._filter_points_to_windows(pts, win)) == 1


# ---------------------------------------------------------------------------
# Pure helper: _group_by_day
# ---------------------------------------------------------------------------


class TestGroupByDay:
    def test_single_point_single_day(self) -> None:
        pts = [(_utc("2026-03-10T02:00:00"), 45.0)]
        result = service._group_by_day(pts)
        assert result == {date(2026, 3, 10): [45.0]}

    def test_multiple_points_same_day_grouped_together(self) -> None:
        pts = [
            (_utc("2026-03-10T01:00:00"), 40.0),
            (_utc("2026-03-10T03:00:00"), 50.0),
        ]
        result = service._group_by_day(pts)
        assert result[date(2026, 3, 10)] == [40.0, 50.0]

    def test_points_across_multiple_days(self) -> None:
        pts = [
            (_utc("2026-03-10T02:00:00"), 40.0),
            (_utc("2026-03-11T03:00:00"), 50.0),
        ]
        result = service._group_by_day(pts)
        assert date(2026, 3, 10) in result
        assert date(2026, 3, 11) in result

    def test_empty_input_returns_empty_dict(self) -> None:
        assert service._group_by_day([]) == {}

    def test_naive_timestamp_treated_as_utc(self) -> None:
        naive_ts = datetime(2026, 3, 10, 2, 0, 0)
        result = service._group_by_day([(naive_ts, 45.0)])
        assert result == {date(2026, 3, 10): [45.0]}

    def test_non_utc_aware_timestamp_normalized_before_bucketing(self) -> None:
        """A +02:00 timestamp at 01:00 local is 2026-03-09 23:00 UTC — buckets under March 9."""
        tz_plus2 = timezone(timedelta(hours=2))
        ts_plus2 = datetime(2026, 3, 10, 1, 0, 0, tzinfo=tz_plus2)
        result = service._group_by_day([(ts_plus2, 45.0)])
        assert result == {date(2026, 3, 9): [45.0]}


# ---------------------------------------------------------------------------
# Pure helper: _empty_daily_scores
# ---------------------------------------------------------------------------


class TestEmptyDailyScores:
    def test_length_matches_lookback_days(self) -> None:
        result = service._empty_daily_scores(date(2026, 3, 10), 7)
        assert len(result) == 7

    def test_all_entries_have_no_data(self) -> None:
        result = service._empty_daily_scores(date(2026, 3, 10), 7)
        assert all(not ds.has_data for ds in result)
        assert all(ds.hrv_value_ms is None for ds in result)

    def test_dates_are_ordered_oldest_to_newest(self) -> None:
        ref = date(2026, 3, 10)
        result = service._empty_daily_scores(ref, 7)
        dates = [ds.date for ds in result]
        assert dates == sorted(dates)
        assert dates[-1] == ref - timedelta(days=1)
        assert dates[0] == ref - timedelta(days=7)


# ---------------------------------------------------------------------------
# Pure helper: _extract_asleep_windows (no DB — uses empty record lists)
# ---------------------------------------------------------------------------


class TestExtractAsleepWindowsLogic:
    """Tests the window extraction logic using a real DB session."""

    _ASLEEP = frozenset(
        {
            SleepStageType.SLEEPING,
            SleepStageType.LIGHT,
            SleepStageType.DEEP,
            SleepStageType.REM,
        }
    )

    def test_no_records_returns_empty(self, db: Session) -> None:
        user = UserFactory()
        db.flush()
        result = service._extract_asleep_windows(
            db,
            user.id,
            _utc("2026-03-03T00:00:00"),
            _utc("2026-03-10T00:00:00"),
            self._ASLEEP,
        )
        assert result == []

    def test_no_sleep_details_uses_full_session_window(self, db: Session) -> None:
        """Session without SleepDetails → whole session treated as asleep."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        start = _utc("2026-03-09T23:00:00")
        end = _utc("2026-03-10T07:00:00")
        EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=start,
            end_datetime=end,
            data_source=ds,
        )
        db.flush()
        windows = service._extract_asleep_windows(
            db,
            user.id,
            _utc("2026-03-09T00:00:00"),
            _utc("2026-03-10T12:00:00"),
            self._ASLEEP,
        )
        assert len(windows) == 1
        assert windows[0] == (start, end)

    def test_empty_sleep_stages_uses_full_session_window(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        start = _utc("2026-03-09T23:00:00")
        end = _utc("2026-03-10T07:00:00")
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=start,
            end_datetime=end,
            data_source=ds,
        )
        SleepDetailsFactory(event_record=record, sleep_stages=[])
        db.flush()
        windows = service._extract_asleep_windows(
            db,
            user.id,
            _utc("2026-03-09T00:00:00"),
            _utc("2026-03-10T12:00:00"),
            self._ASLEEP,
        )
        assert len(windows) == 1

    def test_awake_stages_excluded(self, db: Session) -> None:
        """AWAKE stages must not produce windows."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        stages = _make_stages("2026-03-09T23:00:00", [("awake", 30), ("light", 60)])
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=_utc("2026-03-09T23:00:00"),
            end_datetime=_utc("2026-03-10T00:30:00"),
            data_source=ds,
        )
        SleepDetailsFactory(event_record=record, sleep_stages=stages)
        db.flush()
        windows = service._extract_asleep_windows(
            db,
            user.id,
            _utc("2026-03-09T00:00:00"),
            _utc("2026-03-10T12:00:00"),
            self._ASLEEP,
        )
        # Only the "light" stage produces a window
        assert len(windows) == 1

    def test_unknown_stage_excluded(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        stages = [_make_stage_dict("unknown", "2026-03-09T23:00:00", "2026-03-09T23:30:00")]
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=_utc("2026-03-09T23:00:00"),
            end_datetime=_utc("2026-03-09T23:30:00"),
            data_source=ds,
        )
        SleepDetailsFactory(event_record=record, sleep_stages=stages)
        db.flush()
        windows = service._extract_asleep_windows(
            db,
            user.id,
            _utc("2026-03-09T00:00:00"),
            _utc("2026-03-10T12:00:00"),
            self._ASLEEP,
        )
        assert windows == []

    def test_zero_duration_stage_skipped(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        stages = [_make_stage_dict("deep", "2026-03-09T23:00:00", "2026-03-09T23:00:00")]
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=_utc("2026-03-09T23:00:00"),
            end_datetime=_utc("2026-03-09T23:00:00"),
            data_source=ds,
        )
        SleepDetailsFactory(event_record=record, sleep_stages=stages)
        db.flush()
        windows = service._extract_asleep_windows(
            db,
            user.id,
            _utc("2026-03-09T00:00:00"),
            _utc("2026-03-10T12:00:00"),
            self._ASLEEP,
        )
        assert windows == []

    def test_deep_only_filter(self, db: Session) -> None:
        """When allowed_stages = {DEEP}, only deep windows are returned."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        stages = _make_stages("2026-03-09T23:00:00", [("light", 30), ("deep", 60), ("rem", 30)])
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=_utc("2026-03-09T23:00:00"),
            end_datetime=_utc("2026-03-10T01:00:00"),
            data_source=ds,
        )
        SleepDetailsFactory(event_record=record, sleep_stages=stages)
        db.flush()
        windows = service._extract_asleep_windows(
            db,
            user.id,
            _utc("2026-03-09T00:00:00"),
            _utc("2026-03-10T12:00:00"),
            frozenset({SleepStageType.DEEP}),
        )
        assert len(windows) == 1  # only the deep stage


# ---------------------------------------------------------------------------
# DB-backed: get_hrv_cv_score
# ---------------------------------------------------------------------------


class TestGetHrvCvScore:
    """E2E tests for ResilienceScoreService.get_hrv_cv_score."""

    def _insert_hrv(
        self,
        db: Session,
        data_source: DataSource,
        series_type: SeriesTypeDefinition,
        timestamps: list[datetime],
        value: float = 45.0,
    ) -> None:
        for ts in timestamps:
            DataPointSeriesFactory(
                data_source=data_source,
                series_type=series_type,
                recorded_at=ts,
                value=Decimal(str(value)),
            )
        db.flush()

    def _make_sleep(
        self,
        db: Session,
        data_source: DataSource,
        start: datetime,
        end: datetime,
        stages: list[dict] | None = None,
    ) -> None:
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=start,
            end_datetime=end,
            data_source=data_source,
        )
        SleepDetailsFactory(event_record=record, sleep_stages=stages)
        db.flush()

    def test_no_data_returns_none_hrv_cv(self, db: Session) -> None:
        """No HRV data at all → hrv_cv=None, metric_type=None."""
        user = UserFactory()
        db.flush()
        result = service.get_hrv_cv_score(db, user.id, date(2026, 3, 10))
        assert result.hrv_cv is None
        assert result.metric_type is None
        assert result.days_counted == 0
        assert len(result.daily_scores) == resilience_config.lookback_days

    def test_all_daily_scores_have_no_data_when_empty(self, db: Session) -> None:
        user = UserFactory()
        db.flush()
        result = service.get_hrv_cv_score(db, user.id, date(2026, 3, 10))
        assert all(not ds.has_data for ds in result.daily_scores)

    def test_rmssd_preferred_over_sdnn(self, db: Session) -> None:
        """When both RMSSD and SDNN exist, RMSSD is used."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        rmssd_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_rmssd()
        sdnn_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_sdnn()

        ref = date(2026, 3, 10)
        # Insert 3 days within the lookback window (ref-3, ref-2, ref-1), each with a
        # sleep window so the points survive the sleep filter step.
        for days_back in [1, 2, 3]:
            day = ref - timedelta(days=days_back)
            self._make_sleep(
                db,
                ds,
                datetime.combine(day, time(0), tzinfo=timezone.utc),
                datetime.combine(day, time(8), tzinfo=timezone.utc),
            )
            ts = datetime.combine(day, time(2), tzinfo=timezone.utc)
            DataPointSeriesFactory(data_source=ds, series_type=rmssd_type, recorded_at=ts, value=Decimal("45"))
            DataPointSeriesFactory(data_source=ds, series_type=sdnn_type, recorded_at=ts, value=Decimal("30"))
        db.flush()

        result = service.get_hrv_cv_score(db, user.id, ref)
        assert result.metric_type == "RMSSD"

    def test_falls_back_to_sdnn_when_no_rmssd(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        sdnn_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_sdnn()
        ref = date(2026, 3, 10)
        # Insert 6 days within the lookback window, each with a sleep window.
        for days_back in range(1, 7):
            day = ref - timedelta(days=days_back)
            self._make_sleep(
                db,
                ds,
                datetime.combine(day, time(0), tzinfo=timezone.utc),
                datetime.combine(day, time(8), tzinfo=timezone.utc),
            )
            ts = datetime.combine(day, time(2), tzinfo=timezone.utc)
            DataPointSeriesFactory(data_source=ds, series_type=sdnn_type, recorded_at=ts, value=Decimal("30"))
        db.flush()

        result = service.get_hrv_cv_score(db, user.id, ref)
        assert result.metric_type == "SDNN"

    def test_falls_back_to_sdnn_when_rmssd_only_outside_sleep(self, db: Session) -> None:
        """Daytime RMSSD (no overnight data) + overnight SDNN → SDNN is used."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        rmssd_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_rmssd()
        sdnn_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_sdnn()

        ref = date(2026, 3, 10)
        day = ref - timedelta(days=1)

        # Sleep window: midnight → 08:00
        self._make_sleep(
            db,
            ds,
            datetime.combine(day, time(0), tzinfo=timezone.utc),
            datetime.combine(day, time(8), tzinfo=timezone.utc),
        )
        # RMSSD point at 14:00 (outside sleep window)
        DataPointSeriesFactory(
            data_source=ds,
            series_type=rmssd_type,
            recorded_at=datetime.combine(day, time(14), tzinfo=timezone.utc),
            value=Decimal("45"),
        )
        # SDNN point at 02:00 (inside sleep window)
        DataPointSeriesFactory(
            data_source=ds,
            series_type=sdnn_type,
            recorded_at=datetime.combine(day, time(2), tzinfo=timezone.utc),
            value=Decimal("30"),
        )
        db.flush()

        result = service.get_hrv_cv_score(db, user.id, ref)
        assert result.metric_type == "SDNN"
        assert result.days_counted == 1

    def test_hrv_cv_none_when_fewer_than_min_days(self, db: Session) -> None:
        """Fewer valid days than min_days_required → hrv_cv stays None."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        rmssd_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_rmssd()
        ref = date(2026, 3, 10)

        # Insert only 2 days of data (min required is 5 by default).
        # Each HRV point is at 02:00 on the given day; create a matching sleep window
        # so the points survive the sleep-filter step.
        for days_back in [1, 2]:
            day = ref - timedelta(days=days_back)
            sleep_start = datetime.combine(day - timedelta(days=1), time(23), tzinfo=timezone.utc)
            sleep_end = datetime.combine(day, time(7), tzinfo=timezone.utc)
            self._make_sleep(db, ds, sleep_start, sleep_end)
            ts = datetime.combine(day, time(2), tzinfo=timezone.utc)
            DataPointSeriesFactory(data_source=ds, series_type=rmssd_type, recorded_at=ts, value=Decimal("45"))
        db.flush()

        result = service.get_hrv_cv_score(db, user.id, ref)
        assert result.hrv_cv is None
        assert result.days_counted == 2

    def test_hrv_cv_computed_when_enough_days(self, db: Session) -> None:
        """5+ days with sleep-filtered HRV data → hrv_cv is a valid float."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        rmssd_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_rmssd()
        ref = date(2026, 3, 10)

        for days_back in range(1, 7):  # 6 days
            day = ref - timedelta(days=days_back)
            sleep_start = datetime.combine(day - timedelta(days=1), time(23), tzinfo=timezone.utc)
            sleep_end = datetime.combine(day, time(7), tzinfo=timezone.utc)
            self._make_sleep(db, ds, sleep_start, sleep_end)
            # HRV point during sleep
            hrv_ts = datetime.combine(day, time(2), tzinfo=timezone.utc)
            DataPointSeriesFactory(
                data_source=ds,
                series_type=rmssd_type,
                recorded_at=hrv_ts,
                value=Decimal(str(40 + days_back * 2)),
            )
        db.flush()

        result = service.get_hrv_cv_score(db, user.id, ref)
        assert result.hrv_cv is not None
        assert not math.isnan(result.hrv_cv)
        assert result.days_counted >= resilience_config.min_days_required

    def test_hrv_outside_sleep_windows_not_counted(self, db: Session) -> None:
        """HRV data points outside sleep periods are excluded from daily averages."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        rmssd_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_rmssd()
        ref = date(2026, 3, 10)

        # Insert HRV during waking hours only (no sleep sessions)
        for days_back in range(1, 7):
            ts = datetime.combine(ref - timedelta(days=days_back), time(14), tzinfo=timezone.utc)
            DataPointSeriesFactory(data_source=ds, series_type=rmssd_type, recorded_at=ts, value=Decimal("45"))
        db.flush()

        result = service.get_hrv_cv_score(db, user.id, ref)
        # No sleep sessions → all HRV points filtered out
        assert result.days_counted == 0
        assert result.hrv_cv is None

    def test_daily_scores_ordered_oldest_to_newest(self, db: Session) -> None:
        user = UserFactory()
        db.flush()
        ref = date(2026, 3, 10)
        result = service.get_hrv_cv_score(db, user.id, ref)
        dates = [ds.date for ds in result.daily_scores]
        assert dates == sorted(dates)

    def test_lookback_days_reflected_in_result(self, db: Session) -> None:
        user = UserFactory()
        db.flush()
        result = service.get_hrv_cv_score(db, user.id, date(2026, 3, 10))
        assert result.lookback_days == resilience_config.lookback_days

    def test_reference_date_itself_not_included(self, db: Session) -> None:
        """Data on reference_date must not count; data from the prior day must count."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        rmssd_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_rmssd()
        ref = date(2026, 3, 10)

        # Overnight sleep session spanning ref-1 into ref
        sleep_start = _utc("2026-03-09T23:00:00")
        sleep_end = _utc("2026-03-10T07:00:00")
        self._make_sleep(db, ds, sleep_start, sleep_end)

        # Point inside the sleep window and inside the query window → must count
        DataPointSeriesFactory(
            data_source=ds,
            series_type=rmssd_type,
            recorded_at=_utc("2026-03-09T23:30:00"),
            value=Decimal("45"),
        )
        # Point exactly at reference_date midnight → excluded by query boundary (< end_dt)
        DataPointSeriesFactory(
            data_source=ds,
            series_type=rmssd_type,
            recorded_at=datetime.combine(ref, time.min, tzinfo=timezone.utc),
            value=Decimal("45"),
        )
        db.flush()

        result = service.get_hrv_cv_score(db, user.id, ref)
        assert result.days_counted == 1
        assert any(s.date == date(2026, 3, 9) and s.has_data for s in result.daily_scores)

    def test_daily_score_has_data_true_when_hrv_present(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        rmssd_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate_variability_rmssd()
        ref = date(2026, 3, 10)
        target_day = ref - timedelta(days=1)  # 2026-03-09

        # Sleep runs from March 9 23:00 → March 10 07:00.
        # HRV point must be within the sleep window AND within the query window
        # [March 3 00:00, March 10 00:00), so place it at 23:30 on March 9.
        # ts.date() == March 9 == target_day, so it groups under the right day.
        sleep_start = _utc("2026-03-09T23:00:00")
        sleep_end = _utc("2026-03-10T07:00:00")
        self._make_sleep(db, ds, sleep_start, sleep_end)
        DataPointSeriesFactory(
            data_source=ds,
            series_type=rmssd_type,
            recorded_at=_utc("2026-03-09T23:30:00"),
            value=Decimal("45"),
        )
        db.flush()

        result = service.get_hrv_cv_score(db, user.id, ref)
        score_for_day = next(s for s in result.daily_scores if s.date == target_day)
        assert score_for_day.has_data is True
        assert score_for_day.hrv_value_ms == pytest.approx(45.0)


# ---------------------------------------------------------------------------
# DB-backed: calculate_rmssd_ow (RMSSD_OW)
# ---------------------------------------------------------------------------


class TestCalculateRmssdOw:
    """Tests for ResilienceScoreService.calculate_rmssd_ow (RMSSD_OW)."""

    def _insert_hr(self, db: Session, data_source: DataSource, timestamps: list[datetime], value: float = 65.0) -> None:
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for ts in timestamps:
            DataPointSeriesFactory(
                data_source=data_source,
                series_type=hr_type,
                recorded_at=ts,
                value=Decimal(str(value)),
            )
        db.flush()

    def _make_sleep(
        self, db: Session, data_source: DataSource, start: datetime, end: datetime, stages: list[dict] | None = None
    ) -> None:
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=start,
            end_datetime=end,
            data_source=data_source,
        )
        SleepDetailsFactory(event_record=record, sleep_stages=stages)
        db.flush()

    def test_no_hr_data_returns_none(self, db: Session) -> None:
        user = UserFactory()
        db.flush()
        result = service.calculate_rmssd_ow(
            db,
            user.id,
            _utc("2026-03-09T22:00:00"),
            _utc("2026-03-10T08:00:00"),
        )
        assert result is None

    def test_insufficient_samples_returns_none(self, db: Session) -> None:
        """Fewer than min_rr_samples HR points → None."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        # Insert just 5 points (min is 20)
        self._insert_hr(db, ds, [_utc(f"2026-03-10T0{i}:00:00") for i in range(1, 6)], value=65.0)
        self._make_sleep(db, ds, _utc("2026-03-09T23:00:00"), _utc("2026-03-10T07:00:00"))
        result = service.calculate_rmssd_ow(
            db,
            user.id,
            _utc("2026-03-09T22:00:00"),
            _utc("2026-03-10T08:00:00"),
        )
        assert result is None

    def test_sufficient_samples_returns_float(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        # 25 points every 10 minutes during sleep
        base = _utc("2026-03-10T01:00:00")
        timestamps = [base + timedelta(minutes=10 * i) for i in range(25)]
        self._insert_hr(db, ds, timestamps, value=65.0)
        self._make_sleep(db, ds, _utc("2026-03-09T23:00:00"), _utc("2026-03-10T07:00:00"))
        result = service.calculate_rmssd_ow(
            db,
            user.id,
            _utc("2026-03-09T22:00:00"),
            _utc("2026-03-10T08:00:00"),
        )
        # Constant HR → RMSSD = 0
        assert result is not None
        assert isinstance(result, float)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_hr_outside_sleep_window_excluded(self, db: Session) -> None:
        """HR points during waking hours must be filtered out."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        # 25 points during the day (outside sleep window)
        base = _utc("2026-03-10T14:00:00")
        timestamps = [base + timedelta(minutes=10 * i) for i in range(25)]
        self._insert_hr(db, ds, timestamps, value=65.0)
        self._make_sleep(db, ds, _utc("2026-03-09T23:00:00"), _utc("2026-03-10T07:00:00"))
        result = service.calculate_rmssd_ow(
            db,
            user.id,
            _utc("2026-03-09T22:00:00"),
            _utc("2026-03-10T08:00:00"),
        )
        assert result is None  # filtered out → insufficient samples

    def test_deep_sleep_only_flag(self, db: Session) -> None:
        """deep_sleep_only=True restricts HR to DEEP stage windows."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        stages = _make_stages(
            "2026-03-09T23:00:00",
            [
                ("light", 60),  # 23:00–00:00
                ("deep", 120),  # 00:00–02:00
                ("rem", 60),  # 02:00–03:00
            ],
        )
        self._make_sleep(db, ds, _utc("2026-03-09T23:00:00"), _utc("2026-03-10T03:00:00"), stages=stages)

        # 25 points all during the "light" window
        base = _utc("2026-03-09T23:05:00")
        timestamps = [base + timedelta(minutes=2 * i) for i in range(25)]
        self._insert_hr(db, ds, timestamps, value=70.0)

        # With deep_sleep_only=True those points fall outside deep window → None
        result = service.calculate_rmssd_ow(
            db,
            user.id,
            _utc("2026-03-09T22:00:00"),
            _utc("2026-03-10T08:00:00"),
            deep_sleep_only=True,
        )
        assert result is None

    def test_no_sleep_sessions_returns_none(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        base = _utc("2026-03-10T01:00:00")
        timestamps = [base + timedelta(minutes=10 * i) for i in range(25)]
        self._insert_hr(db, ds, timestamps, value=65.0)
        result = service.calculate_rmssd_ow(
            db,
            user.id,
            _utc("2026-03-09T22:00:00"),
            _utc("2026-03-10T08:00:00"),
        )
        assert result is None


# ---------------------------------------------------------------------------
# DB-backed: calculate_sdnn_ow (SDNN_OW)
# ---------------------------------------------------------------------------


class TestCalculateSdnnOw:
    """Tests for ResilienceScoreService.calculate_sdnn_ow (SDNN_OW)."""

    def _insert_hr(self, db: Session, data_source: DataSource, timestamps: list[datetime], value: float = 65.0) -> None:
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for ts in timestamps:
            DataPointSeriesFactory(
                data_source=data_source,
                series_type=hr_type,
                recorded_at=ts,
                value=Decimal(str(value)),
            )
        db.flush()

    def _make_sleep(self, db: Session, data_source: DataSource, start: datetime, end: datetime) -> None:
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=start,
            end_datetime=end,
            data_source=data_source,
        )
        SleepDetailsFactory(event_record=record)
        db.flush()

    def test_no_hr_data_returns_none(self, db: Session) -> None:
        user = UserFactory()
        db.flush()
        result = service.calculate_sdnn_ow(
            db,
            user.id,
            _utc("2026-03-09T22:00:00"),
            _utc("2026-03-10T08:00:00"),
        )
        assert result is None

    def test_insufficient_samples_returns_none(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        self._insert_hr(db, ds, [_utc(f"2026-03-10T0{i}:00:00") for i in range(1, 6)], value=65.0)
        self._make_sleep(db, ds, _utc("2026-03-09T23:00:00"), _utc("2026-03-10T07:00:00"))
        result = service.calculate_sdnn_ow(
            db,
            user.id,
            _utc("2026-03-09T22:00:00"),
            _utc("2026-03-10T08:00:00"),
        )
        assert result is None

    def test_sufficient_samples_constant_hr_returns_zero(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        base = _utc("2026-03-10T01:00:00")
        timestamps = [base + timedelta(minutes=10 * i) for i in range(25)]
        self._insert_hr(db, ds, timestamps, value=65.0)
        self._make_sleep(db, ds, _utc("2026-03-09T23:00:00"), _utc("2026-03-10T07:00:00"))
        result = service.calculate_sdnn_ow(
            db,
            user.id,
            _utc("2026-03-09T22:00:00"),
            _utc("2026-03-10T08:00:00"),
        )
        assert result is not None
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_rmssd_and_sdnn_differ_for_same_input(self, db: Session) -> None:
        """RMSSD_OW and SDNN_OW should generally return different values for variable HR."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()
        # Alternating HR → non-trivial RMSSD and SDNN
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        base = _utc("2026-03-10T01:00:00")
        for i in range(25):
            hr_val = 60.0 if i % 2 == 0 else 80.0
            ts = base + timedelta(minutes=5 * i)
            DataPointSeriesFactory(data_source=ds, series_type=hr_type, recorded_at=ts, value=Decimal(str(hr_val)))
        db.flush()
        self._make_sleep(db, ds, _utc("2026-03-09T23:00:00"), _utc("2026-03-10T07:00:00"))

        rmssd = service.calculate_rmssd_ow(db, user.id, _utc("2026-03-09T22:00:00"), _utc("2026-03-10T08:00:00"))
        sdnn = service.calculate_sdnn_ow(db, user.id, _utc("2026-03-09T22:00:00"), _utc("2026-03-10T08:00:00"))

        assert rmssd is not None
        assert sdnn is not None
        assert rmssd != pytest.approx(sdnn, rel=1e-3)
