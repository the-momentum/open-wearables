"""Sleep score calculation algorithms."""

import statistics
from datetime import datetime

from pydantic import BaseModel

from app.algorithms.config_algorithms import sleep_config
from app.algorithms.scoring_primitives import ScoreBounds, score_sigmoid, time_to_hours_past_noon


class SleepComponentScore(BaseModel):
    score: int


class SleepScoreBreakdown(BaseModel):
    duration: SleepComponentScore
    stages: SleepComponentScore
    consistency: SleepComponentScore
    interruptions: SleepComponentScore


class SleepScoreMetrics(BaseModel):
    duration_hours: float


class SleepScoreResult(BaseModel):
    overall_score: int
    metrics: SleepScoreMetrics
    breakdown: SleepScoreBreakdown


# Score bounds (min, max) for each component and the final score
DURATION_SCORE_BOUNDS = ScoreBounds(0, 100)
STAGE_SCORE_BOUNDS = ScoreBounds(0, 100)
CONSISTENCY_SCORE_BOUNDS = ScoreBounds(0, 100)
INTERRUPTIONS_SCORE_BOUNDS = ScoreBounds(0, 100)
OVERALL_SCORE_BOUNDS = ScoreBounds(0, 100)


def _score_duration_hours(duration_hours: float) -> int:
    """Score a sleep duration (in hours) on a set scale.

    Perfect score within the optimal range. Steep sigmoid drop-off for
    under-sleeping, gentler drop-off for over-sleeping (floor at half max bound).
    """
    if sleep_config.optimal_min_hours <= duration_hours <= sleep_config.optimal_max_hours:
        return DURATION_SCORE_BOUNDS.max

    if duration_hours < sleep_config.optimal_min_hours:
        raw = score_sigmoid(
            duration_hours,
            k=-sleep_config.undersleep_k,
            base=DURATION_SCORE_BOUNDS.max,
            midpoint=sleep_config.undersleep_midpoint,
            anchor=sleep_config.optimal_min_hours,
        )
        return max(DURATION_SCORE_BOUNDS.min, min(DURATION_SCORE_BOUNDS.max, int(raw)))

    oversleep_floor = max(DURATION_SCORE_BOUNDS.min, int(DURATION_SCORE_BOUNDS.max / 2))
    oversleep_raw = min(
        DURATION_SCORE_BOUNDS.max,
        int(
            score_sigmoid(
                duration_hours,
                k=sleep_config.oversleep_k,
                base=DURATION_SCORE_BOUNDS.max,
                midpoint=sleep_config.oversleep_midpoint,
                anchor=sleep_config.optimal_max_hours,
            )
        ),
    )
    return max(oversleep_floor, oversleep_raw)


def calculate_duration_score(day_start_iso: str, day_end_iso: str, awake_minutes: float = 0.0) -> int:
    """Calculate a sleep duration score (0-100) based on actual sleep hours.

    Subtracts awake_minutes (WASO) from the raw session length before scoring.
    """
    start_time = datetime.fromisoformat(day_start_iso)
    end_time = datetime.fromisoformat(day_end_iso)
    duration_hours = (end_time - start_time).total_seconds() / 3600 - awake_minutes / 60.0
    return _score_duration_hours(duration_hours)


def _calculate_stage_score(stage_duration_minutes: float, optimal_target_minutes: float) -> int:
    """Calculate a bounded score for a sleep stage based on absolute duration.

    Uses linear drop-off below the target
    (e.g. 45 min out of 90 min target = 50 points).
    """
    if stage_duration_minutes >= optimal_target_minutes:
        return STAGE_SCORE_BOUNDS.max
    if stage_duration_minutes <= 0:
        return STAGE_SCORE_BOUNDS.min
    return int((stage_duration_minutes / optimal_target_minutes) * STAGE_SCORE_BOUNDS.max)


def calculate_total_stages_score(deep_minutes: float, rem_minutes: float) -> int:
    """Combine Deep and REM into a single stages score using configured targets and weights."""
    deep_score = _calculate_stage_score(deep_minutes, sleep_config.deep_target_mins)
    rem_score = _calculate_stage_score(rem_minutes, sleep_config.rem_target_mins)
    total = (deep_score * sleep_config.deep_weight) + (rem_score * sleep_config.rem_weight)
    return max(STAGE_SCORE_BOUNDS.min, min(STAGE_SCORE_BOUNDS.max, int(total)))


def calculate_bedtime_consistency_score(
    historical_bedtimes_iso: list[str],
    tonight_bedtime_iso: str,
) -> int:
    """Calculate a consistency score based on a rolling median bedtime."""
    if not historical_bedtimes_iso:
        return CONSISTENCY_SCORE_BOUNDS.min

    historical_hours = [time_to_hours_past_noon(datetime.fromisoformat(bt)) for bt in historical_bedtimes_iso]
    median_hours_past_noon = statistics.median(historical_hours)

    tonight_hours = time_to_hours_past_noon(datetime.fromisoformat(tonight_bedtime_iso))
    diff_minutes = (tonight_hours - median_hours_past_noon) * 60
    penalty = 0.0

    if diff_minutes > sleep_config.consistency_grace_period_mins:
        late_mins = diff_minutes - sleep_config.consistency_grace_period_mins
        penalty = (late_mins / sleep_config.max_late_penalty_window_mins) * CONSISTENCY_SCORE_BOUNDS.max

    elif diff_minutes < -sleep_config.consistency_grace_period_mins:
        early_mins = abs(diff_minutes) - sleep_config.consistency_grace_period_mins
        penalty = min(
            sleep_config.max_early_penalty_points,
            (early_mins / sleep_config.max_early_penalty_window_mins) * CONSISTENCY_SCORE_BOUNDS.max,
        )

    return max(CONSISTENCY_SCORE_BOUNDS.min, int(CONSISTENCY_SCORE_BOUNDS.max - penalty))


def calculate_interruptions_score(
    total_awake_minutes: float,
    awakening_durations: list[float],
) -> int:
    """Calculate an interruptions score based on WASO and awakening frequency."""
    # Scale weight points proportionally to score_bounds.max so the result stays
    # within bounds regardless of the configured scale (e.g. ScoreBounds(0, 50)).
    scale = INTERRUPTIONS_SCORE_BOUNDS.max / 100.0
    dur_full = sleep_config.duration_weight_points * scale
    freq_full = sleep_config.frequency_weight_points * scale

    duration_score = dur_full
    if total_awake_minutes > sleep_config.interruptions_grace_period_mins:
        excess_awake_mins = total_awake_minutes - sleep_config.interruptions_grace_period_mins
        penalty_ratio = excess_awake_mins / sleep_config.max_penalty_window_mins
        duration_penalty = penalty_ratio * dur_full
        duration_score = max(INTERRUPTIONS_SCORE_BOUNDS.min, dur_full - duration_penalty)

    n = sum(1 for d in awakening_durations if d > sleep_config.significant_wake_threshold_mins)
    freq_score = freq_full * sleep_config.freq_score_fractions[min(n, len(sleep_config.freq_score_fractions) - 1)]

    return max(INTERRUPTIONS_SCORE_BOUNDS.min, min(INTERRUPTIONS_SCORE_BOUNDS.max, int(duration_score + freq_score)))


def calculate_overall_sleep_score(
    total_sleep_minutes: float,
    deep_minutes: float,
    rem_minutes: float,
    session_start: str,
    historical_bedtimes: list[str],
    total_awake_minutes: float,
    awakening_durations: list[float],
) -> SleepScoreResult:
    """Combine all four pillars into a single overall sleep score.

    Uses total_sleep_minutes (pre-computed net sleep) for duration scoring.
    session_start is the bedtime ISO string used only for consistency scoring.
    Returns a SleepScoreResult.
    """
    if not total_sleep_minutes or total_sleep_minutes <= 0:
        raise ValueError(f"Cannot calculate sleep score: total_sleep_minutes must be > 0, got {total_sleep_minutes}")

    duration_hours = total_sleep_minutes / 60.0
    duration_score = _score_duration_hours(duration_hours)
    stages_score = calculate_total_stages_score(deep_minutes, rem_minutes)
    consistency_score = calculate_bedtime_consistency_score(historical_bedtimes, session_start)
    interruptions_score = calculate_interruptions_score(total_awake_minutes, awakening_durations)

    weighted_fraction = (
        (duration_score / DURATION_SCORE_BOUNDS.max) * sleep_config.duration_impact
        + (stages_score / STAGE_SCORE_BOUNDS.max) * sleep_config.stages_impact
        + (consistency_score / CONSISTENCY_SCORE_BOUNDS.max) * sleep_config.consistency_impact
        + (interruptions_score / INTERRUPTIONS_SCORE_BOUNDS.max) * sleep_config.interruptions_impact
    )
    scaled = OVERALL_SCORE_BOUNDS.min + (OVERALL_SCORE_BOUNDS.max - OVERALL_SCORE_BOUNDS.min) * weighted_fraction
    overall = max(OVERALL_SCORE_BOUNDS.min, min(OVERALL_SCORE_BOUNDS.max, int(scaled)))

    return SleepScoreResult(
        overall_score=overall,
        metrics=SleepScoreMetrics(duration_hours=round(duration_hours, 2)),
        breakdown=SleepScoreBreakdown(
            duration=SleepComponentScore(score=duration_score),
            stages=SleepComponentScore(score=stages_score),
            consistency=SleepComponentScore(score=consistency_score),
            interruptions=SleepComponentScore(score=interruptions_score),
        ),
    )
