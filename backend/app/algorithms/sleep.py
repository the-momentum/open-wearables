"""Sleep score calculation algorithms."""

import statistics
from datetime import datetime

from pydantic import BaseModel

from app.algorithms.config_algorithms import SleepScoreConfig, sleep_config
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


def _score_duration_hours(
    duration_hours: float,
    score_bounds: ScoreBounds = DURATION_SCORE_BOUNDS,
    config: SleepScoreConfig = sleep_config,
) -> int:
    """Score a sleep duration (in hours) on a set scale.

    Perfect score within the optimal range. Steep sigmoid drop-off for
    under-sleeping, gentler drop-off for over-sleeping (floor at half max bound).
    """
    if config.optimal_min_hours <= duration_hours <= config.optimal_max_hours:
        return score_bounds.max

    if duration_hours < config.optimal_min_hours:
        return int(
            score_sigmoid(
                duration_hours,
                k=-config.undersleep_k,
                base=score_bounds.max,
                midpoint=config.undersleep_midpoint,
                anchor=config.optimal_min_hours,
            )
        )

    return max(
        int(score_bounds.max / 2),
        int(
            score_sigmoid(
                duration_hours,
                k=config.oversleep_k,
                base=score_bounds.max,
                midpoint=config.oversleep_midpoint,
                anchor=config.optimal_max_hours,
            )
        ),
    )


def calculate_duration_score(day_start_iso: str, day_end_iso: str, awake_minutes: float = 0.0) -> int:
    """Calculate a sleep duration score (0-100) based on actual sleep hours.

    Subtracts awake_minutes (WASO) from the raw session length before scoring.
    """
    start_time = datetime.fromisoformat(day_start_iso)
    end_time = datetime.fromisoformat(day_end_iso)
    duration_hours = (end_time - start_time).total_seconds() / 3600 - awake_minutes / 60.0
    return _score_duration_hours(duration_hours)


def _calculate_stage_score(
    stage_duration_minutes: float,
    optimal_target_minutes: float,
    score_bounds: ScoreBounds = STAGE_SCORE_BOUNDS,
) -> int:
    """Calculate a bounded score for a sleep stage based on absolute duration.

    Uses linear drop-off below the target
    (e.g. 45 min out of 90 min target = 50 points).
    """
    if stage_duration_minutes >= optimal_target_minutes:
        return score_bounds.max
    if stage_duration_minutes <= 0:
        return score_bounds.min
    return int((stage_duration_minutes / optimal_target_minutes) * score_bounds.max)


def calculate_total_stages_score(
    deep_minutes: float,
    rem_minutes: float,
    score_bounds: ScoreBounds = STAGE_SCORE_BOUNDS,
    config: SleepScoreConfig = sleep_config,
) -> int:
    """Combine Deep and REM into a single stages score using configured targets and weights."""
    deep_score = _calculate_stage_score(deep_minutes, config.deep_target_mins, score_bounds)
    rem_score = _calculate_stage_score(rem_minutes, config.rem_target_mins, score_bounds)
    total = (deep_score * config.deep_weight) + (rem_score * config.rem_weight)
    return max(score_bounds.min, min(score_bounds.max, int(total)))


def calculate_bedtime_consistency_score(
    historical_bedtimes_iso: list[str],
    tonight_bedtime_iso: str,
    score_bounds: ScoreBounds = CONSISTENCY_SCORE_BOUNDS,
    config: SleepScoreConfig = sleep_config,
) -> int:
    """Calculate a consistency score based on a rolling median bedtime."""
    if not historical_bedtimes_iso:
        return score_bounds.min

    historical_hours = [time_to_hours_past_noon(datetime.fromisoformat(bt)) for bt in historical_bedtimes_iso]
    median_hours_past_noon = statistics.median(historical_hours)

    tonight_hours = time_to_hours_past_noon(datetime.fromisoformat(tonight_bedtime_iso))
    diff_minutes = (tonight_hours - median_hours_past_noon) * 60
    penalty = 0.0

    if diff_minutes > config.consistency_grace_period_mins:
        late_mins = diff_minutes - config.consistency_grace_period_mins
        penalty = (late_mins / config.max_late_penalty_window_mins) * score_bounds.max

    elif diff_minutes < -config.consistency_grace_period_mins:
        early_mins = abs(diff_minutes) - config.consistency_grace_period_mins
        penalty = min(
            config.max_early_penalty_points,
            (early_mins / config.max_early_penalty_window_mins) * score_bounds.max,
        )

    return max(score_bounds.min, int(score_bounds.max - penalty))


def calculate_interruptions_score(
    total_awake_minutes: float,
    awakening_durations: list[float],
    score_bounds: ScoreBounds = INTERRUPTIONS_SCORE_BOUNDS,
    config: SleepScoreConfig = sleep_config,
) -> int:
    """Calculate an interruptions score based on WASO and awakening frequency."""
    duration_score = config.duration_weight_points
    if total_awake_minutes > config.interruptions_grace_period_mins:
        excess_awake_mins = total_awake_minutes - config.interruptions_grace_period_mins
        penalty_ratio = excess_awake_mins / config.max_penalty_window_mins
        duration_penalty = penalty_ratio * config.duration_weight_points
        duration_score = max(score_bounds.min, config.duration_weight_points - duration_penalty)

    n = sum(1 for d in awakening_durations if d > config.significant_wake_threshold_mins)
    freq_score = (
        config.frequency_weight_points * config.freq_score_fractions[min(n, len(config.freq_score_fractions) - 1)]
    )

    return max(score_bounds.min, min(score_bounds.max, int(duration_score + freq_score)))


def calculate_overall_sleep_score(
    total_sleep_minutes: float,
    deep_minutes: float,
    rem_minutes: float,
    session_start: str,
    historical_bedtimes: list[str],
    total_awake_minutes: float,
    awakening_durations: list[float],
    score_bounds: ScoreBounds = OVERALL_SCORE_BOUNDS,
    config: SleepScoreConfig = sleep_config,
) -> SleepScoreResult:
    """Combine all four pillars into a single overall sleep score.

    Uses total_sleep_minutes (pre-computed net sleep) for duration scoring.
    session_start is the bedtime ISO string used only for consistency scoring.
    Returns a SleepScoreResult.
    """
    if not total_sleep_minutes or total_sleep_minutes <= 0:
        raise ValueError(f"Cannot calculate sleep score: total_sleep_minutes must be > 0, got {total_sleep_minutes}")

    duration_hours = total_sleep_minutes / 60.0
    duration_score = _score_duration_hours(duration_hours, DURATION_SCORE_BOUNDS, config)
    stages_score = calculate_total_stages_score(deep_minutes, rem_minutes, STAGE_SCORE_BOUNDS, config)
    consistency_score = calculate_bedtime_consistency_score(
        historical_bedtimes, session_start, CONSISTENCY_SCORE_BOUNDS, config
    )
    interruptions_score = calculate_interruptions_score(
        total_awake_minutes, awakening_durations, INTERRUPTIONS_SCORE_BOUNDS, config
    )

    weighted_fraction = (
        (duration_score / DURATION_SCORE_BOUNDS.max) * config.duration_impact
        + (stages_score / STAGE_SCORE_BOUNDS.max) * config.stages_impact
        + (consistency_score / CONSISTENCY_SCORE_BOUNDS.max) * config.consistency_impact
        + (interruptions_score / INTERRUPTIONS_SCORE_BOUNDS.max) * config.interruptions_impact
    )
    scaled = score_bounds.min + (score_bounds.max - score_bounds.min) * weighted_fraction
    overall = max(score_bounds.min, min(score_bounds.max, int(scaled)))

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
