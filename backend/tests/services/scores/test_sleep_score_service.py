"""End-to-end tests for SleepScoreService.

Covers both layers:
- get_sleep_score      – pure calculation, no DB
- get_sleep_score_for_user – DB-backed, uses real Postgres via testcontainers

All DB tests use the transaction-rollback fixture from conftest so they leave
no side-effects.
"""

import logging
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.constants.sleep import SleepStageType
from app.models.data_source import DataSource
from app.models.event_record import EventRecord
from app.schemas.model_crud.activities.sleep import SleepStage
from app.services.scores.sleep_service import SleepScoreService
from tests.factories import DataSourceFactory, EventRecordFactory, SleepDetailsFactory, UserFactory

_log = logging.getLogger(__name__)
service = SleepScoreService(log=_log)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def _make_stages(
    start_iso: str,
    blocks: list[tuple[str, int]],  # (stage, duration_mins)
) -> list[SleepStage]:
    """Build a list of SleepStage with contiguous start/end times."""
    stages = []
    current = _utc(start_iso)
    for stage, mins in blocks:
        end = current + timedelta(minutes=mins)
        stages.append(SleepStage(stage=SleepStageType(stage), start_time=current, end_time=end))
        current = end
    return stages


# ---------------------------------------------------------------------------
# Pure-calculation tests (no DB)
# ---------------------------------------------------------------------------


class TestGetSleepScore:
    """Tests for SleepScoreService.get_sleep_score (pure calculation)."""

    def test_happy_path_full_stages(self) -> None:
        """Good night's sleep with full stage data returns sensible scores."""
        stages = _make_stages(
            "2026-03-10T23:00:00",
            [
                ("light", 30),
                ("deep", 90),
                ("rem", 60),
                ("awake", 10),
                ("deep", 60),
                ("light", 60),
                ("rem", 50),
                ("light", 30),
            ],
        )
        result = service.get_sleep_score(
            total_sleep_duration_minutes=390.0,
            deep_minutes=150.0,
            rem_minutes=110.0,
            awake_minutes=10.0,
            session_start=_utc("2026-03-10T23:00:00"),
            historical_bedtimes=[],
            sleep_stages=stages,
        )

        assert 0 <= result.overall_score <= 100
        assert result.breakdown.duration.score > 0
        assert result.breakdown.stages.score > 0
        # No history → consistency must be 0
        assert result.breakdown.consistency.score == 0
        assert result.breakdown.interruptions.score > 0
        assert result.metrics.duration_hours > 0

    def test_happy_path_no_stages_fallback(self) -> None:
        """When sleep_stages is omitted, awake_minutes is used for interruptions."""
        result = service.get_sleep_score(
            total_sleep_duration_minutes=450.0,
            deep_minutes=90.0,
            rem_minutes=80.0,
            awake_minutes=20.0,
            session_start=_utc("2026-03-10T22:30:00"),
            historical_bedtimes=[],
            sleep_stages=None,
        )

        assert 0 <= result.overall_score <= 100
        assert result.breakdown.duration.score > 0

    def test_consistency_score_with_history(self) -> None:
        """Consistent bedtime over prior nights yields a non-zero consistency score."""
        history = [_utc(f"2026-03-0{d}T23:00:00") for d in range(1, 8)]
        result = service.get_sleep_score(
            total_sleep_duration_minutes=450.0,
            deep_minutes=90.0,
            rem_minutes=80.0,
            awake_minutes=10.0,
            session_start=_utc("2026-03-08T23:05:00"),  # within grace period
            historical_bedtimes=history,
            sleep_stages=None,
        )

        assert result.breakdown.consistency.score > 0

    def test_consistency_score_no_history_returns_zero(self) -> None:
        """No historical bedtimes → consistency component must be 0."""
        result = service.get_sleep_score(
            total_sleep_duration_minutes=480.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-10T23:00:00"),
            historical_bedtimes=[],
            sleep_stages=None,
        )

        assert result.breakdown.consistency.score == 0

    def test_stages_score_zero_when_no_stage_data(self) -> None:
        """deep=0, rem=0 (no stage tracking) → stages component must be 0."""
        result = service.get_sleep_score(
            total_sleep_duration_minutes=420.0,
            deep_minutes=0.0,
            rem_minutes=0.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-10T23:00:00"),
            historical_bedtimes=[],
            sleep_stages=None,
        )

        assert result.breakdown.stages.score == 0

    def test_duration_zero_raises(self) -> None:
        """total_sleep_duration_minutes=0 must raise ValueError."""
        with pytest.raises(ValueError, match="total_sleep_duration_minutes"):
            service.get_sleep_score(
                total_sleep_duration_minutes=0.0,
                deep_minutes=90.0,
                rem_minutes=90.0,
                awake_minutes=0.0,
                session_start=_utc("2026-03-10T23:00:00"),
                historical_bedtimes=[],
            )

    def test_duration_negative_raises(self) -> None:
        """Negative duration must also raise ValueError."""
        with pytest.raises(ValueError, match="total_sleep_duration_minutes"):
            service.get_sleep_score(
                total_sleep_duration_minutes=-30.0,
                deep_minutes=0.0,
                rem_minutes=0.0,
                awake_minutes=0.0,
                session_start=_utc("2026-03-10T23:00:00"),
                historical_bedtimes=[],
            )

    def test_overall_score_bounded(self) -> None:
        """Overall score must always be in [0, 100]."""
        result = service.get_sleep_score(
            total_sleep_duration_minutes=720.0,  # 12 h (oversleep)
            deep_minutes=300.0,
            rem_minutes=300.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-10T23:00:00"),
            historical_bedtimes=[],
        )

        assert 0 <= result.overall_score <= 100

    def test_short_sleep_low_duration_score(self) -> None:
        """Very short sleep (2 h) should produce a low duration score."""
        result = service.get_sleep_score(
            total_sleep_duration_minutes=120.0,
            deep_minutes=10.0,
            rem_minutes=10.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-10T03:00:00"),
            historical_bedtimes=[],
        )

        assert result.breakdown.duration.score < 50


# ---------------------------------------------------------------------------
# DB-backed E2E tests
# ---------------------------------------------------------------------------


class TestGetSleepScoreForUser:
    """E2E tests for SleepScoreService.get_sleep_score_for_user (hits real DB)."""

    def _make_sleep_record(
        self,
        db: Session,
        data_source: DataSource,
        sleep_date: date,
        start_hour: int = 23,
        duration_minutes: int = 480,
        deep_minutes: int | None = 120,
        rem_minutes: int | None = 90,
        awake_minutes: int = 20,
        sleep_stages: list[SleepStage] | None = None,
        is_nap: bool = False,
    ) -> EventRecord:
        """Create an EventRecord + SleepDetails for the given data_source and date."""
        start = datetime(
            sleep_date.year,
            sleep_date.month,
            sleep_date.day,
            start_hour,
            0,
            0,
            tzinfo=timezone.utc,
        )
        end = start + timedelta(minutes=duration_minutes + awake_minutes)

        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=start,
            end_datetime=end,
            duration_seconds=(duration_minutes + awake_minutes) * 60,
            data_source=data_source,
        )
        SleepDetailsFactory(
            event_record=record,
            sleep_total_duration_minutes=duration_minutes,
            sleep_deep_minutes=deep_minutes,
            sleep_rem_minutes=rem_minutes,
            sleep_awake_minutes=awake_minutes,
            sleep_light_minutes=(max(0, duration_minutes - (deep_minutes or 0) - (rem_minutes or 0))),
            is_nap=is_nap,
            sleep_stages=[s.model_dump(mode="json") for s in sleep_stages] if sleep_stages else None,
        )
        db.flush()
        return record

    def test_basic_score_no_stages_no_history(self, db: Session) -> None:
        """Single night, no stage data, no prior history → score is calculable."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        sleep_date = date(2026, 3, 10)
        self._make_sleep_record(db, ds, sleep_date)

        result = service.get_sleep_score_for_user(db, user.id, sleep_date)

        assert 0 <= result.overall_score <= 100
        assert result.metrics.duration_hours > 0
        assert result.breakdown.consistency.score == 0  # no history
        assert result.breakdown.stages.score > 0  # deep+rem provided

    def test_score_with_sleep_stages_waso_calculated(self, db: Session) -> None:
        """Stage blocks are used to derive true WASO instead of the summary field."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        sleep_date = date(2026, 3, 11)
        stages = _make_stages(
            "2026-03-11T23:00:00",
            [
                ("light", 30),
                ("deep", 90),
                ("rem", 60),
                ("awake", 15),
                ("light", 60),
                ("deep", 60),
                ("rem", 45),
                ("light", 30),
            ],
        )
        self._make_sleep_record(
            db,
            ds,
            sleep_date,
            duration_minutes=375,
            deep_minutes=150,
            rem_minutes=105,
            awake_minutes=15,
            sleep_stages=stages,
        )

        result = service.get_sleep_score_for_user(db, user.id, sleep_date)

        assert 0 <= result.overall_score <= 100
        assert result.breakdown.stages.score > 0
        assert result.breakdown.interruptions.score > 0

    def test_consistency_score_with_prior_history(self, db: Session) -> None:
        """Seven nights of consistent history should give a non-zero consistency score."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        # Plant 7 prior nights at consistent 23:00 bedtime
        for delta in range(7, 0, -1):
            prior_date = date(2026, 3, 10) - timedelta(days=delta)
            self._make_sleep_record(db, ds, prior_date, start_hour=23)

        # Tonight's session, also around 23:00
        sleep_date = date(2026, 3, 10)
        self._make_sleep_record(db, ds, sleep_date, start_hour=23)
        db.flush()

        result = service.get_sleep_score_for_user(db, user.id, sleep_date)

        assert result.breakdown.consistency.score > 0

    def test_nap_records_are_excluded(self, db: Session) -> None:
        """Nap sessions on the same date must not be used for scoring."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        sleep_date = date(2026, 3, 10)
        # Plant a nap — should be ignored
        self._make_sleep_record(
            db,
            ds,
            sleep_date,
            start_hour=14,
            duration_minutes=30,
            is_nap=True,
        )
        # Plant the main sleep — should be used
        self._make_sleep_record(db, ds, sleep_date, start_hour=23)
        db.flush()

        result = service.get_sleep_score_for_user(db, user.id, sleep_date)
        # Duration should match the 8-hour main session, not the 30-min nap
        assert result.metrics.duration_hours > 4.0

    def test_only_nap_no_main_sleep_raises(self, db: Session) -> None:
        """When only nap records exist, no main sleep → 404."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        sleep_date = date(2026, 3, 10)
        self._make_sleep_record(
            db,
            ds,
            sleep_date,
            start_hour=14,
            duration_minutes=30,
            is_nap=True,
        )
        db.flush()

        with pytest.raises(HTTPException) as exc_info:
            service.get_sleep_score_for_user(db, user.id, sleep_date)
        assert exc_info.value.status_code == 404

    def test_no_sleep_record_raises(self, db: Session) -> None:
        """No records at all for the date → 404."""
        user = UserFactory()
        db.flush()

        with pytest.raises(HTTPException) as exc_info:
            service.get_sleep_score_for_user(db, user.id, date(2026, 3, 10))
        assert exc_info.value.status_code == 404

    def test_zero_duration_in_db_raises(self, db: Session) -> None:
        """A DB record with sleep_total_duration_minutes=0 must raise ValueError."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        sleep_date = date(2026, 3, 10)
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=datetime(2026, 3, 10, 23, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 3, 11, 7, 0, tzinfo=timezone.utc),
            data_source=ds,
        )
        SleepDetailsFactory(
            event_record=record,
            sleep_total_duration_minutes=0,
            sleep_deep_minutes=0,
            sleep_rem_minutes=0,
            sleep_awake_minutes=0,
            is_nap=False,
        )
        db.flush()

        with pytest.raises(ValueError, match="Cannot calculate sleep score"):
            service.get_sleep_score_for_user(db, user.id, sleep_date)

    def test_longest_session_selected_when_multiple(self, db: Session) -> None:
        """When multiple non-nap sessions exist on the same date, the longest is used."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        sleep_date = date(2026, 3, 10)
        # Short session
        self._make_sleep_record(
            db,
            ds,
            sleep_date,
            start_hour=22,
            duration_minutes=120,
            deep_minutes=20,
            rem_minutes=20,
        )
        # Long session
        self._make_sleep_record(
            db,
            ds,
            sleep_date,
            start_hour=23,
            duration_minutes=480,
            deep_minutes=120,
            rem_minutes=90,
        )
        db.flush()

        result = service.get_sleep_score_for_user(db, user.id, sleep_date)

        # Duration should match the 8-hour session, not the 2-hour one
        assert result.metrics.duration_hours == pytest.approx(8.0, abs=0.1)

    def test_stages_score_zero_when_no_deep_rem(self, db: Session) -> None:
        """Record with no deep/rem minutes (older device) → stages score = 0."""
        user = UserFactory()
        ds = DataSourceFactory(user=user)
        db.flush()

        sleep_date = date(2026, 3, 10)
        record = EventRecordFactory(
            category="sleep",
            type_="sleep",
            start_datetime=datetime(2026, 3, 10, 23, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 3, 11, 6, 30, tzinfo=timezone.utc),
            data_source=ds,
        )
        SleepDetailsFactory(
            event_record=record,
            sleep_total_duration_minutes=420,
            sleep_deep_minutes=None,
            sleep_rem_minutes=None,
            sleep_awake_minutes=0,
            is_nap=False,
            sleep_stages=None,
        )
        db.flush()

        result = service.get_sleep_score_for_user(db, user.id, sleep_date)

        assert result.breakdown.stages.score == 0


# ---------------------------------------------------------------------------
# Helper: _parse_wearable_stages_for_interruptions
# ---------------------------------------------------------------------------


class TestParseWearableStagesForInterruptions:
    """Tests for SleepScoreService._parse_wearable_stages_for_interruptions."""

    def _stages(self, *pairs: tuple[str, int]) -> list[SleepStage]:
        """Build SleepStage objects with contiguous times from (stage, duration_mins) pairs."""
        result = []
        current = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        for stage_name, mins in pairs:
            end = current + timedelta(minutes=mins)
            result.append(SleepStage(stage=SleepStageType(stage_name), start_time=current, end_time=end))
            current = end
        return result

    def test_empty_blocks_returns_zero(self) -> None:
        result = service._parse_wearable_stages_for_interruptions([])
        assert result.total_awake_minutes == 0.0
        assert result.awakening_durations == []

    def test_no_awake_blocks_returns_zero_waso(self) -> None:
        stages = self._stages(("light", 30), ("deep", 90), ("rem", 60))
        result = service._parse_wearable_stages_for_interruptions(stages)
        assert result.total_awake_minutes == 0.0
        assert result.awakening_durations == []

    def test_leading_awake_stripped_as_sleep_latency(self) -> None:
        """An awake block at the start (latency) must not count as WASO."""
        stages = self._stages(("awake", 20), ("light", 30), ("deep", 90))
        result = service._parse_wearable_stages_for_interruptions(stages)
        assert result.total_awake_minutes == 0.0

    def test_trailing_awake_stripped_as_morning_lying_in(self) -> None:
        """An awake block at the end must not count as WASO."""
        stages = self._stages(("light", 30), ("deep", 90), ("awake", 15))
        result = service._parse_wearable_stages_for_interruptions(stages)
        assert result.total_awake_minutes == 0.0

    def test_middle_awake_counted_as_waso(self) -> None:
        """Awake block sandwiched between sleep stages counts as WASO."""
        stages = self._stages(("light", 30), ("awake", 15), ("rem", 60))
        result = service._parse_wearable_stages_for_interruptions(stages)
        assert result.total_awake_minutes == pytest.approx(15.0)
        assert result.awakening_durations == [15.0]

    def test_multiple_middle_awakes_all_counted(self) -> None:
        stages = self._stages(
            ("light", 30),
            ("awake", 10),
            ("deep", 60),
            ("awake", 20),
            ("rem", 45),
        )
        result = service._parse_wearable_stages_for_interruptions(stages)
        assert result.total_awake_minutes == pytest.approx(30.0)
        assert result.awakening_durations == [10.0, 20.0]

    def test_leading_and_trailing_stripped_middle_counted(self) -> None:
        """All three edge types in one session — only middle awake counts."""
        stages = self._stages(
            ("awake", 15),  # latency — stripped
            ("light", 30),
            ("awake", 12),  # WASO — counted
            ("deep", 90),
            ("awake", 10),  # morning — stripped
        )
        result = service._parse_wearable_stages_for_interruptions(stages)
        assert result.total_awake_minutes == pytest.approx(12.0)
        assert result.awakening_durations == [12.0]

    def test_waso_data_model_fields(self) -> None:
        """Result must expose total_awake_minutes and awakening_durations."""
        stages = self._stages(("light", 30), ("awake", 10), ("rem", 60))
        result = service._parse_wearable_stages_for_interruptions(stages)
        assert hasattr(result, "total_awake_minutes")
        assert hasattr(result, "awakening_durations")


# ---------------------------------------------------------------------------
# Additional get_sleep_score edge cases
# ---------------------------------------------------------------------------


class TestGetSleepScoreEdgeCases:
    """Extra edge cases not covered by TestGetSleepScore."""

    def test_sleep_stages_strips_latency_before_scoring(self) -> None:
        """Sleep latency awake at start is not penalised in interruptions."""
        stages_with_latency = _make_stages(
            "2026-03-10T23:00:00",
            [
                ("awake", 30),  # latency
                ("light", 60),
                ("deep", 90),
                ("rem", 90),
                ("light", 30),
            ],
        )
        stages_no_latency = _make_stages(
            "2026-03-10T23:00:00",
            [
                ("light", 60),
                ("deep", 90),
                ("rem", 90),
                ("light", 30),
            ],
        )
        result_with = service.get_sleep_score(
            total_sleep_duration_minutes=300.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-10T23:00:00"),
            historical_bedtimes=[],
            sleep_stages=stages_with_latency,
        )
        result_without = service.get_sleep_score(
            total_sleep_duration_minutes=300.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-10T23:00:00"),
            historical_bedtimes=[],
            sleep_stages=stages_no_latency,
        )
        # Latency stripped → interruption scores should be equal
        assert result_with.breakdown.interruptions.score == result_without.breakdown.interruptions.score

    def test_late_inconsistent_bedtime_penalises_consistency(self) -> None:
        """Going to bed 2 hours later than usual lowers consistency score."""
        consistent_history = [_utc(f"2026-03-0{d}T23:00:00") for d in range(1, 8)]
        result_on_time = service.get_sleep_score(
            total_sleep_duration_minutes=450.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-08T23:00:00"),
            historical_bedtimes=consistent_history,
        )
        result_late = service.get_sleep_score(
            total_sleep_duration_minutes=450.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-08T01:00:00"),
            historical_bedtimes=consistent_history,
        )
        assert result_late.breakdown.consistency.score < result_on_time.breakdown.consistency.score

    def test_optimal_sleep_high_overall_score(self) -> None:
        """Perfect inputs across all pillars should yield a high overall score."""
        history = [_utc(f"2026-03-0{d}T23:00:00") for d in range(1, 8)]
        result = service.get_sleep_score(
            total_sleep_duration_minutes=480.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-08T23:00:00"),
            historical_bedtimes=history,
        )
        assert result.overall_score >= 75

    def test_overall_score_always_in_bounds(self) -> None:
        """Even with extreme inputs the score must remain in [0, 100]."""
        result = service.get_sleep_score(
            total_sleep_duration_minutes=900.0,  # 15 h
            deep_minutes=500.0,
            rem_minutes=500.0,
            awake_minutes=0.0,
            session_start=_utc("2026-03-10T23:00:00"),
            historical_bedtimes=[],
        )
        assert 0 <= result.overall_score <= 100

    def test_stages_fallback_uses_awake_minutes_for_waso(self) -> None:
        """Without stage data awake_minutes is used directly for interruption scoring."""
        result_low_awake = service.get_sleep_score(
            total_sleep_duration_minutes=480.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            awake_minutes=5.0,
            session_start=_utc("2026-03-10T23:00:00"),
            historical_bedtimes=[],
            sleep_stages=None,
        )
        result_high_awake = service.get_sleep_score(
            total_sleep_duration_minutes=480.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            awake_minutes=90.0,
            session_start=_utc("2026-03-10T23:00:00"),
            historical_bedtimes=[],
            sleep_stages=None,
        )
        assert result_high_awake.breakdown.interruptions.score < result_low_awake.breakdown.interruptions.score
