"""Unit tests for sleep score algorithm functions.

Covers every public (and key private) function in:
  - app.algorithms.scoring_primitives   (time_to_hours_past_noon, score_sigmoid)
  - app.algorithms.sleep   (all scoring sub-functions and the top-level combiner)

These tests exercise pure-Python logic only — no database, no factories.
"""

from datetime import datetime

import pytest

from app.algorithms.scoring_primitives import score_sigmoid, time_to_hours_past_noon
from app.algorithms.sleep import (
    STAGE_SCORE_BOUNDS,
    _calculate_stage_score,
    _score_duration_hours,
    calculate_bedtime_consistency_score,
    calculate_duration_score,
    calculate_interruptions_score,
    calculate_overall_sleep_score,
    calculate_total_stages_score,
)

# ---------------------------------------------------------------------------
# app.algorithms.scoring_primitives
# ---------------------------------------------------------------------------


class TestTimeToHoursPastNoon:
    """time_to_hours_past_noon returns hours on a continuous [0, 24) axis anchored at noon."""

    def test_noon_is_zero(self) -> None:
        assert time_to_hours_past_noon(datetime(2026, 3, 10, 12, 0, 0)) == pytest.approx(0.0)

    def test_11pm_is_11_hours(self) -> None:
        assert time_to_hours_past_noon(datetime(2026, 3, 10, 23, 0, 0)) == pytest.approx(11.0)

    def test_midnight_wraps_to_12(self) -> None:
        """Midnight (0:00) is 12 hours past noon on the continuous axis."""
        assert time_to_hours_past_noon(datetime(2026, 3, 10, 0, 0, 0)) == pytest.approx(12.0)

    def test_1am_is_13_hours(self) -> None:
        assert time_to_hours_past_noon(datetime(2026, 3, 10, 1, 0, 0)) == pytest.approx(13.0)

    def test_6pm_is_6_hours(self) -> None:
        assert time_to_hours_past_noon(datetime(2026, 3, 10, 18, 0, 0)) == pytest.approx(6.0)

    def test_fractional_minutes(self) -> None:
        """23:30 should return 11.5 hours past noon."""
        assert time_to_hours_past_noon(datetime(2026, 3, 10, 23, 30, 0)) == pytest.approx(11.5)

    def test_just_before_noon_wraps(self) -> None:
        """11:59 is < 12 so it adds 24 → 23.983… hours past noon."""
        result = time_to_hours_past_noon(datetime(2026, 3, 10, 11, 59, 0))
        assert result == pytest.approx(23 + 59 / 60.0, rel=1e-4)

    def test_returns_float(self) -> None:
        result = time_to_hours_past_noon(datetime(2026, 3, 10, 22, 0, 0))
        assert isinstance(result, float)


class TestScoreSigmoid:
    """score_sigmoid(x, k, base, midpoint, anchor) equals base exactly at x=anchor."""

    def test_anchoring_property_positive_k(self) -> None:
        """At x=anchor the function must return base exactly (falling curve)."""
        base = 100.0
        result = score_sigmoid(9.0, k=0.8, base=base, midpoint=11.0, anchor=9.0)
        assert result == pytest.approx(base, rel=1e-9)

    def test_anchoring_property_negative_k(self) -> None:
        """At x=anchor the function must return base exactly (rising curve)."""
        base = 100.0
        result = score_sigmoid(7.0, k=-1.5, base=base, midpoint=5.0, anchor=7.0)
        assert result == pytest.approx(base, rel=1e-9)

    def test_falling_curve_decreases_with_x(self) -> None:
        """Positive k → value decreases as x increases past anchor."""
        v1 = score_sigmoid(10.0, k=0.8, base=100.0, midpoint=11.0, anchor=9.0)
        v2 = score_sigmoid(11.0, k=0.8, base=100.0, midpoint=11.0, anchor=9.0)
        v3 = score_sigmoid(12.0, k=0.8, base=100.0, midpoint=11.0, anchor=9.0)
        assert v1 > v2 > v3

    def test_rising_curve_increases_with_x(self) -> None:
        """Negative k → value increases as x increases toward anchor."""
        v1 = score_sigmoid(3.0, k=-1.5, base=100.0, midpoint=5.0, anchor=7.0)
        v2 = score_sigmoid(5.0, k=-1.5, base=100.0, midpoint=5.0, anchor=7.0)
        v3 = score_sigmoid(6.5, k=-1.5, base=100.0, midpoint=5.0, anchor=7.0)
        assert v1 < v2 < v3

    def test_returns_float(self) -> None:
        result = score_sigmoid(7.0, k=-1.5, base=100.0, midpoint=5.0, anchor=7.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# app.algorithms.sleep — duration scoring
# ---------------------------------------------------------------------------


class TestScoreDurationHours:
    """_score_duration_hours scores a sleep duration in hours on [0, 100]."""

    def test_optimal_range_returns_max(self) -> None:
        """Any value strictly inside [7, 9] hours should return 100."""
        for hours in (7.0, 8.0, 9.0, 7.5, 8.5):
            assert _score_duration_hours(hours) == 100

    def test_just_below_optimal_is_under_100(self) -> None:
        assert _score_duration_hours(6.99) < 100

    def test_just_above_optimal_is_under_100(self) -> None:
        assert _score_duration_hours(9.01) < 100

    def test_very_short_sleep_is_low(self) -> None:
        """Two hours of sleep should score much below 50."""
        assert _score_duration_hours(2.0) < 30

    def test_zero_hours_is_very_low(self) -> None:
        assert _score_duration_hours(0.0) < 5

    def test_oversleep_floored_at_half_max(self) -> None:
        """Oversleeping returns at least score_bounds.max / 2 (i.e. 50)."""
        assert _score_duration_hours(12.0) >= 50
        assert _score_duration_hours(15.0) >= 50

    def test_undersleep_score_increases_with_duration(self) -> None:
        """More sleep hours in the undersleep range means a higher score."""
        assert _score_duration_hours(4.0) < _score_duration_hours(6.0)

    def test_returns_int(self) -> None:
        assert isinstance(_score_duration_hours(8.0), int)

    def test_optimal_boundaries_are_inclusive(self) -> None:
        """Default optimal range [7, 9] is inclusive on both ends."""
        assert _score_duration_hours(7.0) == 100
        assert _score_duration_hours(9.0) == 100
        assert _score_duration_hours(6.99) < 100
        assert _score_duration_hours(9.01) < 100


class TestCalculateDurationScore:
    """calculate_duration_score takes start/end ISO strings and optional awake minutes."""

    def test_8h_window_returns_100(self) -> None:
        score = calculate_duration_score("2026-03-10T23:00:00", "2026-03-11T07:00:00")
        assert score == 100

    def test_subtracts_awake_minutes(self) -> None:
        """8 h window minus 60 min awake = 7 h net — still optimal."""
        score = calculate_duration_score("2026-03-10T23:00:00", "2026-03-11T07:00:00", awake_minutes=60.0)
        assert score == 100  # 7 h is within [7, 9]

    def test_excessive_awake_drops_score(self) -> None:
        """8 h window minus 2.5 h awake = 5.5 h net — well below optimal."""
        score = calculate_duration_score("2026-03-10T23:00:00", "2026-03-11T07:00:00", awake_minutes=150.0)
        assert score < 100

    def test_very_short_session_is_low(self) -> None:
        score = calculate_duration_score("2026-03-10T03:00:00", "2026-03-10T05:00:00")
        assert score < 50


# ---------------------------------------------------------------------------
# app.algorithms.sleep — stage scoring
# ---------------------------------------------------------------------------


class TestCalculateStageScore:
    """_calculate_stage_score scores a single stage duration against a target."""

    def test_at_target_returns_max(self) -> None:
        assert _calculate_stage_score(90.0, 90.0) == STAGE_SCORE_BOUNDS.max

    def test_above_target_returns_max(self) -> None:
        assert _calculate_stage_score(120.0, 90.0) == STAGE_SCORE_BOUNDS.max

    def test_zero_duration_returns_min(self) -> None:
        assert _calculate_stage_score(0.0, 90.0) == STAGE_SCORE_BOUNDS.min

    def test_negative_duration_returns_min(self) -> None:
        assert _calculate_stage_score(-10.0, 90.0) == STAGE_SCORE_BOUNDS.min

    def test_half_target_returns_50(self) -> None:
        """45 out of 90 target minutes → 50 points."""
        assert _calculate_stage_score(45.0, 90.0) == 50

    def test_quarter_target_returns_25(self) -> None:
        assert _calculate_stage_score(22.5, 90.0) == 25

    def test_linear_proportionality(self) -> None:
        """Score should scale linearly between 0 and target."""
        s30 = _calculate_stage_score(30.0, 90.0)
        s60 = _calculate_stage_score(60.0, 90.0)
        assert s30 == pytest.approx(s60 / 2, abs=1)

    def test_score_bounded_at_zero_and_max(self) -> None:
        """Score is always within [STAGE_SCORE_BOUNDS.min, STAGE_SCORE_BOUNDS.max]."""
        assert _calculate_stage_score(0.0, 90.0) == STAGE_SCORE_BOUNDS.min
        assert _calculate_stage_score(90.0, 90.0) == STAGE_SCORE_BOUNDS.max


class TestCalculateTotalStagesScore:
    """calculate_total_stages_score combines deep and REM into one score."""

    def test_optimal_deep_and_rem_returns_100(self) -> None:
        assert calculate_total_stages_score(90.0, 90.0) == 100

    def test_zero_deep_and_rem_returns_0(self) -> None:
        assert calculate_total_stages_score(0.0, 0.0) == 0

    def test_half_deep_optimal_rem(self) -> None:
        """deep=45 → 50 pts; rem=90 → 100 pts; avg = 75."""
        assert calculate_total_stages_score(45.0, 90.0) == 75

    def test_optimal_deep_half_rem(self) -> None:
        assert calculate_total_stages_score(90.0, 45.0) == 75

    def test_over_target_still_max(self) -> None:
        assert calculate_total_stages_score(200.0, 200.0) == 100

    def test_zero_deep_only_rem(self) -> None:
        """Only REM contributes — deep=0, rem=90 → 0*0.5 + 100*0.5 = 50."""
        assert calculate_total_stages_score(0.0, 90.0) == 50

    def test_only_deep_no_rem(self) -> None:
        assert calculate_total_stages_score(90.0, 0.0) == 50

    def test_default_weights_equal_contribution(self) -> None:
        """Default 0.5/0.5 weights mean deep=90 rem=0 and deep=0 rem=90 both score 50."""
        assert calculate_total_stages_score(90.0, 0.0) == calculate_total_stages_score(0.0, 90.0)

    def test_returns_int(self) -> None:
        assert isinstance(calculate_total_stages_score(60.0, 60.0), int)


# ---------------------------------------------------------------------------
# app.algorithms.sleep — consistency scoring
# ---------------------------------------------------------------------------


class TestCalculateBedtimeConsistencyScore:
    """calculate_bedtime_consistency_score measures bedtime regularity."""

    def test_empty_history_returns_0(self) -> None:
        score = calculate_bedtime_consistency_score([], "2026-03-10T23:00:00")
        assert score == 0

    def test_on_time_within_grace_returns_100(self) -> None:
        """Bedtime within the 15-minute grace window → no penalty → 100."""
        history = ["2026-03-09T23:00:00"]
        score = calculate_bedtime_consistency_score(history, "2026-03-10T23:05:00")
        assert score == 100

    def test_exactly_on_median_returns_100(self) -> None:
        history = ["2026-03-09T23:00:00", "2026-03-08T23:00:00"]
        score = calculate_bedtime_consistency_score(history, "2026-03-10T23:00:00")
        assert score == 100

    def test_late_bedtime_is_penalized(self) -> None:
        """30 min late (15 beyond grace) incurs a partial penalty."""
        history = ["2026-03-09T23:00:00"]
        score = calculate_bedtime_consistency_score(history, "2026-03-10T23:30:00")
        # late_mins=15, penalty=(15/105)*100≈14.28 → score≈85
        assert score == 85

    def test_very_late_bedtime_reaches_zero(self) -> None:
        """Extremely late bedtime (2.75 h late, max penalty window = 105 min) → score = 0."""
        history = ["2026-03-09T23:00:00"]
        # 23:00 + 15 grace + 105 penalty = 00:40 next day → 120 min late
        score = calculate_bedtime_consistency_score(history, "2026-03-11T01:40:00")
        assert score == 0

    def test_early_bedtime_capped_penalty(self) -> None:
        """Going to bed too early has a max penalty of 20 pts → score ≥ 80."""
        history = ["2026-03-09T23:00:00"]
        # 21:00 = 2h early → well past grace + penalty window → capped at 20
        score = calculate_bedtime_consistency_score(history, "2026-03-10T21:00:00")
        assert score == 80

    def test_median_used_for_multiple_nights(self) -> None:
        """The median, not mean, is used; outlier should not dominate."""
        # Three nights at 23:00 and one wild outlier at 01:00
        history = [
            "2026-03-06T23:00:00",
            "2026-03-07T23:00:00",
            "2026-03-08T23:00:00",
            "2026-03-09T01:00:00",  # outlier
        ]
        score_consistent = calculate_bedtime_consistency_score(history, "2026-03-10T23:00:00")
        # Median should be around 23:00 so tonight is on time
        assert score_consistent == 100

    def test_score_bounded_0_to_100(self) -> None:
        history = ["2026-03-09T23:00:00"]
        score = calculate_bedtime_consistency_score(history, "2026-03-10T06:00:00")
        assert 0 <= score <= 100

    def test_returns_int(self) -> None:
        history = ["2026-03-09T23:00:00"]
        assert isinstance(calculate_bedtime_consistency_score(history, "2026-03-10T23:00:00"), int)


# ---------------------------------------------------------------------------
# app.algorithms.sleep — interruptions scoring
# ---------------------------------------------------------------------------


class TestCalculateInterruptionsScore:
    """calculate_interruptions_score penalises WASO duration and awakening frequency."""

    def test_no_awake_no_awakenings_perfect_score(self) -> None:
        """Zero WASO and no awakenings → full 100 points."""
        assert calculate_interruptions_score(0.0, []) == 100

    def test_within_grace_period_no_duration_penalty(self) -> None:
        """WASO exactly at grace period limit (20 min) → no penalty."""
        assert calculate_interruptions_score(20.0, []) == 100

    def test_excess_awake_penalises_duration_component(self) -> None:
        """1 min over grace → tiny penalty, score just below 100."""
        score = calculate_interruptions_score(21.0, [])
        assert score < 100
        assert score >= 90  # small excess → small penalty

    def test_full_duration_penalty(self) -> None:
        """WASO = grace + max_penalty_window (20+70=90 min) wipes out duration component."""
        score = calculate_interruptions_score(90.0, [])
        # duration_score = 0, freq_score = 20 → total = 20
        assert score == 20

    def test_single_significant_awakening_no_freq_penalty(self) -> None:
        """1 significant awakening → fractions[1]=1.0, no frequency penalty."""
        score = calculate_interruptions_score(0.0, [6.0])
        assert score == 100

    def test_two_significant_awakenings_reduce_freq(self) -> None:
        """2 significant awakenings → fractions[2]=0.75, freq_score=15."""
        score = calculate_interruptions_score(0.0, [6.0, 6.0])
        # duration=80, freq=20*0.75=15 → 95
        assert score == 95

    def test_three_significant_awakenings(self) -> None:
        """3 significant awakenings → fractions[3]=0.5, freq_score=10."""
        score = calculate_interruptions_score(0.0, [6.0, 6.0, 6.0])
        assert score == 90

    def test_four_or_more_significant_awakenings_zero_freq(self) -> None:
        """4+ significant awakenings → fractions[4]=0.0, freq_score=0."""
        score_4 = calculate_interruptions_score(0.0, [6.0, 6.0, 6.0, 6.0])
        score_10 = calculate_interruptions_score(0.0, [6.0] * 10)
        assert score_4 == 80
        assert score_10 == 80

    def test_minor_awakenings_below_threshold_not_counted(self) -> None:
        """Awakenings <= significant_wake_threshold_mins (5 min) don't count."""
        score = calculate_interruptions_score(0.0, [3.0, 4.0, 5.0])
        # n = sum(d > 5.0 for d in [3, 4, 5]) = 0 → fractions[0]=1.0
        assert score == 100

    def test_mixed_awakenings(self) -> None:
        """Mix of minor and significant awakenings — only significant ones count."""
        score = calculate_interruptions_score(0.0, [3.0, 6.0, 4.0, 7.0])
        # n = 2 significant → fractions[2]=0.75 → freq_score=15 → 80+15=95
        assert score == 95

    def test_combined_duration_and_frequency_penalty(self) -> None:
        """Both duration penalty and frequency penalty apply simultaneously."""
        # 90 min awake: duration_score=0; 4 significant → freq_score=0 → total=0
        score = calculate_interruptions_score(90.0, [6.0, 6.0, 6.0, 6.0])
        assert score == 0

    def test_returns_int(self) -> None:
        assert isinstance(calculate_interruptions_score(0.0, []), int)

    def test_score_bounded_0_to_100(self) -> None:
        score = calculate_interruptions_score(0.0, [])
        assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# app.algorithms.sleep — overall score (integration)
# ---------------------------------------------------------------------------


class TestCalculateOverallSleepScore:
    """calculate_overall_sleep_score: end-to-end combiner with all four pillars."""

    _GOOD_NIGHT = dict(
        total_sleep_minutes=450.0,
        deep_minutes=90.0,
        rem_minutes=90.0,
        session_start="2026-03-10T23:00:00",
        historical_bedtimes=["2026-03-09T23:00:00", "2026-03-08T23:00:00"],
        total_awake_minutes=10.0,
        awakening_durations=[],
    )

    def test_returns_correct_schema_fields(self) -> None:
        result = calculate_overall_sleep_score(**self._GOOD_NIGHT)
        assert hasattr(result, "overall_score")
        assert hasattr(result, "metrics")
        assert hasattr(result, "breakdown")
        assert hasattr(result.breakdown, "duration")
        assert hasattr(result.breakdown, "stages")
        assert hasattr(result.breakdown, "consistency")
        assert hasattr(result.breakdown, "interruptions")

    def test_overall_score_bounded_0_to_100(self) -> None:
        result = calculate_overall_sleep_score(**self._GOOD_NIGHT)
        assert 0 <= result.overall_score <= 100

    def test_zero_sleep_minutes_raises(self) -> None:
        with pytest.raises(ValueError, match="total_sleep_minutes"):
            calculate_overall_sleep_score(
                total_sleep_minutes=0.0,
                deep_minutes=90.0,
                rem_minutes=90.0,
                session_start="2026-03-10T23:00:00",
                historical_bedtimes=[],
                total_awake_minutes=0.0,
                awakening_durations=[],
            )

    def test_negative_sleep_minutes_raises(self) -> None:
        with pytest.raises(ValueError, match="total_sleep_minutes must be"):
            calculate_overall_sleep_score(
                total_sleep_minutes=-30.0,
                deep_minutes=0.0,
                rem_minutes=0.0,
                session_start="2026-03-10T23:00:00",
                historical_bedtimes=[],
                total_awake_minutes=0.0,
                awakening_durations=[],
            )

    def test_good_night_high_score(self) -> None:
        """Optimal duration, stages, consistent history, minimal WASO → high score."""
        result = calculate_overall_sleep_score(**self._GOOD_NIGHT)
        assert result.overall_score >= 70

    def test_metrics_duration_hours_matches_input(self) -> None:
        result = calculate_overall_sleep_score(**self._GOOD_NIGHT)
        # 450 min / 60 = 7.5 h
        assert result.metrics.duration_hours == pytest.approx(7.5, abs=0.01)

    def test_no_history_zeroes_consistency(self) -> None:
        result = calculate_overall_sleep_score(
            total_sleep_minutes=480.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            session_start="2026-03-10T23:00:00",
            historical_bedtimes=[],
            total_awake_minutes=0.0,
            awakening_durations=[],
        )
        assert result.breakdown.consistency.score == 0

    def test_no_stage_data_zeroes_stages(self) -> None:
        result = calculate_overall_sleep_score(
            total_sleep_minutes=480.0,
            deep_minutes=0.0,
            rem_minutes=0.0,
            session_start="2026-03-10T23:00:00",
            historical_bedtimes=[],
            total_awake_minutes=0.0,
            awakening_durations=[],
        )
        assert result.breakdown.stages.score == 0

    def test_default_weights_produce_expected_overall(self) -> None:
        """Default impacts (0.40/0.20/0.20/0.20) with known component scores yield a predictable overall.

        Inputs chosen so each component score is unambiguous:
          duration=100 (8 h), stages=0 (no deep/rem),
          consistency=0 (no history), interruptions=100 (0 awake).
        Expected: int((100*0.40 + 0*0.20 + 0*0.20 + 100*0.20) / 100 * 100) = 60
        """
        result = calculate_overall_sleep_score(
            total_sleep_minutes=480.0,
            deep_minutes=0.0,
            rem_minutes=0.0,
            session_start="2026-03-10T23:00:00",
            historical_bedtimes=[],
            total_awake_minutes=0.0,
            awakening_durations=[],
        )
        assert result.overall_score == 60

    def test_short_sleep_lowers_overall(self) -> None:
        """2 h of sleep must produce a noticeably lower overall score than 8 h."""
        result_short = calculate_overall_sleep_score(
            total_sleep_minutes=120.0,
            deep_minutes=10.0,
            rem_minutes=10.0,
            session_start="2026-03-10T04:00:00",
            historical_bedtimes=[],
            total_awake_minutes=0.0,
            awakening_durations=[],
        )
        result_good = calculate_overall_sleep_score(**self._GOOD_NIGHT)
        assert result_short.overall_score < result_good.overall_score

    def test_excessive_waso_lowers_overall(self) -> None:
        """High WASO should reduce the overall score compared to minimal WASO."""
        base = dict(
            total_sleep_minutes=450.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            session_start="2026-03-10T23:00:00",
            historical_bedtimes=[],
            awakening_durations=[],
        )
        result_low_waso = calculate_overall_sleep_score(**base, total_awake_minutes=0.0)
        result_high_waso = calculate_overall_sleep_score(**base, total_awake_minutes=90.0)
        assert result_high_waso.overall_score < result_low_waso.overall_score

    def test_consistent_history_raises_overall(self) -> None:
        """Adding consistent history raises the overall score vs. no history."""
        base = dict(
            total_sleep_minutes=450.0,
            deep_minutes=90.0,
            rem_minutes=90.0,
            session_start="2026-03-10T23:00:00",
            total_awake_minutes=0.0,
            awakening_durations=[],
        )
        result_no_history = calculate_overall_sleep_score(**base, historical_bedtimes=[])
        result_with_history = calculate_overall_sleep_score(
            **base,
            historical_bedtimes=[f"2026-03-0{d}T23:00:00" for d in range(1, 8)],
        )
        assert result_with_history.overall_score > result_no_history.overall_score
