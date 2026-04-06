"""Tests for the 4-component sleep score utility (app/utils/sleep_score.py).

Components under test:
  1. Duration score   — sigmoid curves, ideal 7-9 h
  2. Stage score      — deep + REM vs 90-min target each
  3. Consistency score — bedtime deviation from rolling median
  4. Interruptions score — WASO duration + significant awakening count
  5. Stage-interval parser — strips latency / morning lie-in
  6. Overall score    — weighted combination of the four components
"""

import pytest

from app.utils.sleep_score import (
    INTERRUPTIONS_CONFIG,
    calculate_bedtime_consistency_score,
    calculate_duration_score,
    calculate_interruptions_score,
    calculate_overall_sleep_score,
    calculate_stage_score,
    calculate_total_stages_score,
    parse_wearable_stages_for_interruptions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _start_end(start_hour: float, duration_hours: float) -> tuple[str, str]:
    """Build ISO strings for a session that starts at *start_hour* (decimal)."""
    start_h = int(start_hour)
    start_m = int((start_hour % 1) * 60)
    end_total = start_hour + duration_hours
    end_h = int(end_total) % 24
    end_m = int((end_total % 1) * 60)
    return (
        f"2024-01-15T{start_h:02d}:{start_m:02d}:00",
        f"2024-01-16T{end_h:02d}:{end_m:02d}:00" if end_total >= 24 else f"2024-01-15T{end_h:02d}:{end_m:02d}:00",
    )


# ---------------------------------------------------------------------------
# Component 1: Duration score
# ---------------------------------------------------------------------------


class TestDurationScore:
    def test_ideal_range_returns_100(self) -> None:
        """7-9 hours should return exactly 100."""
        for hours in [7.0, 8.0, 9.0]:
            start, end = _start_end(22, hours)
            result = calculate_duration_score(start, end)
            assert result["duration_score"] == 100, f"Expected 100 for {hours}h"
            assert result["duration_hours"] == hours

    def test_severe_undersleep_approaches_zero(self) -> None:
        """3 hours (the floor) should score close to 0."""
        start, end = _start_end(3, 3.0)
        result = calculate_duration_score(start, end)
        assert result["duration_score"] < 10

    def test_undersleep_midpoint_is_near_50(self) -> None:
        """5.5 hours (the sigmoid midpoint) should score near 50."""
        start, end = _start_end(1, 5.5)
        result = calculate_duration_score(start, end)
        assert 45 <= result["duration_score"] <= 60

    def test_undersleep_is_monotonically_increasing(self) -> None:
        """More sleep below ideal should always score higher."""
        scores = []
        for hours in [4.0, 5.0, 6.0, 7.0]:
            s, e = _start_end(0, hours)
            scores.append(calculate_duration_score(s, e)["duration_score"])
        assert scores == sorted(scores)

    def test_oversleep_floor_at_50(self) -> None:
        """Severe oversleeping (12+ h) should not drop below 50."""
        start, end = _start_end(22, 12.5)
        result = calculate_duration_score(start, end)
        assert result["duration_score"] >= 50

    def test_undersleep_penalised_more_than_oversleep(self) -> None:
        """6h (1h below ideal) should score lower than 10h (1h above ideal).

        This verifies the asymmetric design intent: undersleeping is penalised
        more harshly than equivalent oversleeping.
        """
        s_over, e_over = _start_end(22, 10.0)  # 1 h over 9 h ideal
        s_under, e_under = _start_end(22, 6.0)  # 1 h under 7 h ideal
        score_over = calculate_duration_score(s_over, e_over)["duration_score"]
        score_under = calculate_duration_score(s_under, e_under)["duration_score"]
        assert score_under < score_over

    def test_duration_hours_precision(self) -> None:
        """duration_hours should be rounded to 2 decimal places."""
        start, end = _start_end(22, 7.5)
        result = calculate_duration_score(start, end)
        assert result["duration_hours"] == 7.5


# ---------------------------------------------------------------------------
# Component 2: Stage score
# ---------------------------------------------------------------------------


class TestStageScore:
    def test_at_or_above_target_returns_100(self) -> None:
        assert calculate_stage_score(90.0) == 100
        assert calculate_stage_score(120.0) == 100

    def test_zero_minutes_returns_0(self) -> None:
        assert calculate_stage_score(0.0) == 0

    def test_negative_minutes_returns_0(self) -> None:
        assert calculate_stage_score(-5.0) == 0

    def test_half_target_returns_50(self) -> None:
        assert calculate_stage_score(45.0, 90.0) == 50

    def test_linear_interpolation(self) -> None:
        """Score at 75 min (of 90 target) should be 83."""
        assert calculate_stage_score(75.0, 90.0) == 83

    def test_custom_target(self) -> None:
        assert calculate_stage_score(60.0, 120.0) == 50


class TestTotalStagesScore:
    def test_perfect_deep_and_rem(self) -> None:
        assert calculate_total_stages_score(90.0, 90.0) == 100

    def test_zero_stages(self) -> None:
        assert calculate_total_stages_score(0.0, 0.0) == 0

    def test_equal_weight_deep_rem(self) -> None:
        """75 min deep (83/100) + 90 min REM (100/100) → avg 91."""
        score = calculate_total_stages_score(75.0, 90.0)
        assert score == 91

    def test_only_deep_half_total(self) -> None:
        """90 min deep, 0 REM → 50."""
        assert calculate_total_stages_score(90.0, 0.0) == 50

    def test_score_capped_at_100(self) -> None:
        assert calculate_total_stages_score(200.0, 200.0) == 100


# ---------------------------------------------------------------------------
# Component 3: Bedtime consistency score
# ---------------------------------------------------------------------------

BASELINE = [
    "2024-01-08T22:30:00",
    "2024-01-09T22:45:00",
    "2024-01-10T22:30:00",
    "2024-01-11T22:15:00",
    "2024-01-12T22:30:00",
    "2024-01-13T22:30:00",
    "2024-01-14T22:40:00",
]  # Median ≈ 22:30


class TestConsistencyScore:
    def test_no_history_returns_100(self) -> None:
        assert calculate_bedtime_consistency_score([], "2024-01-15T22:30:00") == 100

    def test_within_grace_period_returns_100(self) -> None:
        """10 minutes late is within the 15-minute grace → 100."""
        assert calculate_bedtime_consistency_score(BASELINE, "2024-01-15T22:40:00") == 100

    def test_exactly_at_grace_boundary(self) -> None:
        """15 minutes late → still 100."""
        assert calculate_bedtime_consistency_score(BASELINE, "2024-01-15T22:45:00") == 100

    def test_very_late_scores_zero(self) -> None:
        """120+ minutes late (15 grace + 105 window) → 0."""
        score = calculate_bedtime_consistency_score(BASELINE, "2024-01-16T00:30:00")
        assert score == 0

    def test_going_early_has_gentle_penalty(self) -> None:
        """120 minutes early should lose at most 20 points (max_early_penalty_points)."""
        score = calculate_bedtime_consistency_score(BASELINE, "2024-01-15T20:30:00")
        assert score >= 80

    def test_late_is_penalised_more_than_early(self) -> None:
        """Going 60 min late should score lower than going 60 min early."""
        late = calculate_bedtime_consistency_score(BASELINE, "2024-01-15T23:30:00")
        early = calculate_bedtime_consistency_score(BASELINE, "2024-01-15T21:30:00")
        assert late < early

    def test_midnight_boundary_handling(self) -> None:
        """Bedtimes crossing midnight should be compared correctly."""
        baseline_late = [
            "2024-01-08T23:30:00",
            "2024-01-09T23:45:00",
            "2024-01-10T23:30:00",
        ]
        # 23:35 is within 15 minutes of median ~23:35 → should score 100
        score = calculate_bedtime_consistency_score(baseline_late, "2024-01-15T23:35:00")
        assert score == 100

    def test_score_decreases_monotonically_with_lateness(self) -> None:
        """Scores should decrease as the user goes to bed later."""
        bedtimes = [
            "2024-01-15T22:30:00",  # on time
            "2024-01-15T23:00:00",  # 30 min late
            "2024-01-15T23:30:00",  # 60 min late
            "2024-01-16T00:00:00",  # 90 min late
        ]
        scores = [calculate_bedtime_consistency_score(BASELINE, bt) for bt in bedtimes]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Component 4: Interruptions score
# ---------------------------------------------------------------------------


class TestInterruptionsScore:
    def test_within_grace_no_wakes_returns_100(self) -> None:
        """20 min WASO is within the grace period; no significant wakes → 100."""
        score = calculate_interruptions_score(20.0, [5.0, 5.0])
        assert score == 100

    def test_zero_awake_returns_100(self) -> None:
        assert calculate_interruptions_score(0.0, []) == 100

    def test_max_duration_penalty_removes_80_points(self) -> None:
        """90 min WASO (20 grace + 70 window) → duration score hits 0 → only freq remains."""
        score = calculate_interruptions_score(90.0, [45.0, 45.0])
        assert score == int(INTERRUPTIONS_CONFIG["frequency_weight_points"])

    def test_four_or_more_significant_wakes_removes_freq_points(self) -> None:
        """4 awakenings > 5 min → frequency score = 0."""
        score = calculate_interruptions_score(15.0, [6.0, 6.0, 6.0, 6.0])
        # duration within grace → 80, freq → 0
        assert score == int(INTERRUPTIONS_CONFIG["duration_weight_points"])

    def test_both_penalties_zero(self) -> None:
        """Max WASO + 4 significant wakes → 0."""
        score = calculate_interruptions_score(100.0, [20.0, 20.0, 20.0, 20.0])
        assert score == 0

    def test_short_wakes_dont_count_toward_frequency(self) -> None:
        """Wakes ≤ 5 min are below the significant threshold."""
        score = calculate_interruptions_score(15.0, [3.0, 3.0, 3.0, 3.0, 3.0])
        assert score == 100

    def test_halfway_duration_penalty(self) -> None:
        """55 min WASO: 35 excess / 70 window = 50% penalty on 80 pts = 40 pts off → 40 + 20 = 60."""
        score = calculate_interruptions_score(55.0, [15.0, 10.0])
        assert score == 60


# ---------------------------------------------------------------------------
# Component 5: Stage-interval parser
# ---------------------------------------------------------------------------


class TestParseWearableStages:
    def test_strips_leading_and_trailing_awake(self) -> None:
        blocks = [
            {"stage": "awake", "duration_mins": 25.0},  # latency — ignore
            {"stage": "light", "duration_mins": 60.0},
            {"stage": "awake", "duration_mins": 8.0},  # WASO — count
            {"stage": "deep", "duration_mins": 45.0},
            {"stage": "awake", "duration_mins": 12.0},  # WASO — count
            {"stage": "rem", "duration_mins": 30.0},
            {"stage": "awake", "duration_mins": 15.0},  # morning lie-in — ignore
        ]
        result = parse_wearable_stages_for_interruptions(blocks)
        assert result["total_awake_minutes"] == 20.0
        assert result["awakening_durations"] == [8.0, 12.0]

    def test_no_interruptions_returns_zeros(self) -> None:
        blocks = [
            {"stage": "light", "duration_mins": 60.0},
            {"stage": "deep", "duration_mins": 90.0},
            {"stage": "rem", "duration_mins": 90.0},
        ]
        result = parse_wearable_stages_for_interruptions(blocks)
        assert result["total_awake_minutes"] == 0.0
        assert result["awakening_durations"] == []

    def test_empty_input_returns_zeros(self) -> None:
        result = parse_wearable_stages_for_interruptions([])
        assert result["total_awake_minutes"] == 0.0
        assert result["awakening_durations"] == []

    def test_start_end_time_format(self) -> None:
        """Should accept SleepStage-style dicts with start_time/end_time."""
        blocks = [
            {"stage": "light", "start_time": "2024-01-15T22:00:00+00:00", "end_time": "2024-01-15T23:00:00+00:00"},
            {"stage": "awake", "start_time": "2024-01-15T23:00:00+00:00", "end_time": "2024-01-15T23:10:00+00:00"},
            {"stage": "deep", "start_time": "2024-01-15T23:10:00+00:00", "end_time": "2024-01-16T00:40:00+00:00"},
        ]
        result = parse_wearable_stages_for_interruptions(blocks)
        assert result["total_awake_minutes"] == pytest.approx(10.0, abs=0.1)
        assert len(result["awakening_durations"]) == 1

    def test_in_bed_stage_treated_as_awake(self) -> None:
        """in_bed stages should be excluded from WASO (they are latency/lie-in)."""
        blocks = [
            {"stage": "in_bed", "duration_mins": 20.0},
            {"stage": "light", "duration_mins": 60.0},
            {"stage": "deep", "duration_mins": 90.0},
            {"stage": "in_bed", "duration_mins": 10.0},
        ]
        result = parse_wearable_stages_for_interruptions(blocks)
        assert result["total_awake_minutes"] == 0.0

    def test_multiple_consecutive_awake_blocks(self) -> None:
        """Each awake block within sleep is counted separately."""
        blocks = [
            {"stage": "light", "duration_mins": 30.0},
            {"stage": "awake", "duration_mins": 5.0},
            {"stage": "awake", "duration_mins": 7.0},
            {"stage": "deep", "duration_mins": 90.0},
        ]
        result = parse_wearable_stages_for_interruptions(blocks)
        assert result["total_awake_minutes"] == 12.0
        assert result["awakening_durations"] == [5.0, 7.0]


# ---------------------------------------------------------------------------
# Overall score: integration tests
# ---------------------------------------------------------------------------

STANDARD_BASELINE = [
    "2024-01-08T22:00:00",
    "2024-01-09T22:15:00",
    "2024-01-10T21:45:00",
    "2024-01-11T22:00:00",
    "2024-01-12T22:00:00",
]


class TestOverallSleepScore:
    def test_perfect_sleeper_scores_high(self) -> None:
        """8 h, >90 min stages, on-time bedtime, minimal waking → ≥ 95."""
        result = calculate_overall_sleep_score(
            session_start="2024-01-13T22:00:00",
            session_end="2024-01-14T06:00:00",
            deep_minutes=110.0,
            rem_minutes=105.0,
            historical_bedtimes=STANDARD_BASELINE,
            total_awake_minutes=10.0,
            awakening_durations=[2.0, 5.0, 3.0],
        )
        assert result["overall_score"] >= 95

    def test_deprived_restless_sleeper_scores_low(self) -> None:
        """4.5 h, poor stages, very late bedtime, heavily interrupted → ≤ 50."""
        result = calculate_overall_sleep_score(
            session_start="2024-01-13T02:00:00",  # 4 hours late
            session_end="2024-01-13T06:30:00",
            deep_minutes=45.0,
            rem_minutes=30.0,
            historical_bedtimes=STANDARD_BASELINE,
            total_awake_minutes=55.0,
            awakening_durations=[10.0, 15.0, 8.0, 12.0],
        )
        assert result["overall_score"] <= 50

    def test_social_jetlag_scores_moderate(self) -> None:
        """Good duration/stages/interruptions, but shifted 5 h late → consistency drags score."""
        result = calculate_overall_sleep_score(
            session_start="2024-01-13T03:00:00",  # 5 hours late
            session_end="2024-01-13T10:30:00",
            deep_minutes=90.0,
            rem_minutes=90.0,
            historical_bedtimes=STANDARD_BASELINE,
            total_awake_minutes=15.0,
            awakening_durations=[6.0, 4.0],
        )
        score = result["overall_score"]
        assert 50 <= score <= 85

    def test_no_history_consistency_defaults_to_100(self) -> None:
        """Without historical bedtimes the consistency component should not penalise."""
        result = calculate_overall_sleep_score(
            session_start="2024-01-13T22:00:00",
            session_end="2024-01-14T06:00:00",
            deep_minutes=110.0,
            rem_minutes=105.0,
            historical_bedtimes=[],
            total_awake_minutes=10.0,
            awakening_durations=[],
        )
        assert result["breakdown"]["consistency"]["score"] == 100

    def test_breakdown_keys_present(self) -> None:
        result = calculate_overall_sleep_score(
            session_start="2024-01-13T22:00:00",
            session_end="2024-01-14T06:00:00",
            deep_minutes=90.0,
            rem_minutes=90.0,
            historical_bedtimes=STANDARD_BASELINE,
            total_awake_minutes=0.0,
            awakening_durations=[],
        )
        bd = result["breakdown"]
        for key in ("duration", "stages", "consistency", "interruptions"):
            assert key in bd
            assert "score" in bd[key]
            assert "weight" in bd[key]

    def test_weights_sum_to_100_percent(self) -> None:
        """The weight labels in the breakdown must sum to 100%."""
        result = calculate_overall_sleep_score(
            session_start="2024-01-13T22:00:00",
            session_end="2024-01-14T06:00:00",
            deep_minutes=90.0,
            rem_minutes=90.0,
            historical_bedtimes=[],
            total_awake_minutes=0.0,
            awakening_durations=[],
        )
        total = sum(int(v["weight"].rstrip("%")) for v in result["breakdown"].values())
        assert total == 100

    def test_overall_score_is_int(self) -> None:
        result = calculate_overall_sleep_score(
            session_start="2024-01-13T22:00:00",
            session_end="2024-01-14T06:00:00",
            deep_minutes=90.0,
            rem_minutes=90.0,
            historical_bedtimes=[],
            total_awake_minutes=0.0,
            awakening_durations=[],
        )
        assert isinstance(result["overall_score"], int)

    def test_custom_weights_are_respected(self) -> None:
        """Passing all weight to duration and 0 to others should make score equal duration score."""
        custom_weights = {"duration": 1.0, "stages": 0.0, "consistency": 0.0, "interruptions": 0.0}
        result = calculate_overall_sleep_score(
            session_start="2024-01-13T22:00:00",
            session_end="2024-01-14T06:00:00",
            deep_minutes=0.0,
            rem_minutes=0.0,
            historical_bedtimes=[],
            total_awake_minutes=0.0,
            awakening_durations=[],
            weights=custom_weights,
        )
        duration_score = calculate_duration_score("2024-01-13T22:00:00", "2024-01-14T06:00:00")["duration_score"]
        assert result["overall_score"] == duration_score

    def test_score_bounded_0_to_100(self) -> None:
        """Overall score must always be 0–100."""
        for hours in [2.0, 5.0, 7.5, 9.0, 11.0]:
            s, e = _start_end(22, hours)
            result = calculate_overall_sleep_score(
                session_start=s,
                session_end=e,
                deep_minutes=0.0,
                rem_minutes=0.0,
                historical_bedtimes=[],
                total_awake_minutes=0.0,
                awakening_durations=[],
            )
            assert 0 <= result["overall_score"] <= 100, f"Score out of bounds for {hours}h"
