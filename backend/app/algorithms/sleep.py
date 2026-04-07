"""Sleep score calculation algorithms."""

import math
import statistics
from datetime import datetime
from typing import NamedTuple

from app.algorithms.config_algorithms import SleepScoreConfig, sleep_config


class ScoreBounds(NamedTuple):
    min: int
    max: int


# Score bounds (min, max) for each component and the final score
DURATION_SCORE_BOUNDS = ScoreBounds(0, 100)
STAGE_SCORE_BOUNDS = ScoreBounds(0, 100)
CONSISTENCY_SCORE_BOUNDS = ScoreBounds(0, 100)
INTERRUPTIONS_SCORE_BOUNDS = ScoreBounds(0, 100)
OVERALL_SCORE_BOUNDS = ScoreBounds(0, 100)


def score_sigmoid(
    x: float, k: float, base: float, midpoint: float, anchor: float
) -> float:
    """Scaled sigmoid that equals base exactly at anchor.

    Pass a negative k for a rising curve (under-sleeping) and a positive k for
    a falling curve (over-sleeping).
    """
    return (
        base
        * (1 + math.exp(k * (anchor - midpoint)))
        / (1 + math.exp(k * (x - midpoint)))
    )


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
                base=DURATION_SCORE_BOUNDS.max,
                midpoint=config.oversleep_midpoint,
                anchor=config.optimal_max_hours,
            )
        ),
    )


def calculate_duration_score(
    day_start_iso: str, day_end_iso: str, awake_minutes: float = 0.0
) -> dict[str, float | int]:
    """Calculate a sleep duration score (0-100) based on actual sleep hours.

    Subtracts awake_minutes (WASO) from the raw session length before scoring.
    """
    start_time = datetime.fromisoformat(day_start_iso)
    end_time = datetime.fromisoformat(day_end_iso)
    duration_hours = (
        end_time - start_time
    ).total_seconds() / 3600 - awake_minutes / 60.0
    return {
        "duration_hours": round(duration_hours, 2),
        "duration_score": _score_duration_hours(duration_hours),
    }


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
    deep_score = _calculate_stage_score(
        deep_minutes, config.deep_target_mins, score_bounds
    )
    rem_score = _calculate_stage_score(
        rem_minutes, config.rem_target_mins, score_bounds
    )
    return int((deep_score * config.deep_weight) + (rem_score * config.rem_weight))


def time_to_hours_past_noon(dt: datetime) -> float:
    """Convert a datetime to continuous hours past noon to handle the midnight boundary."""
    hours = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    if hours < 12.0:
        hours += 24.0
    return hours - 12.0


def calculate_bedtime_consistency_score(
    historical_bedtimes_iso: list[str],
    tonight_bedtime_iso: str,
    score_bounds: ScoreBounds = CONSISTENCY_SCORE_BOUNDS,
    config: SleepScoreConfig = sleep_config,
) -> int:
    """Calculate a consistency score based on a rolling median bedtime."""
    if not historical_bedtimes_iso:
        return score_bounds.max

    historical_hours = [
        time_to_hours_past_noon(datetime.fromisoformat(bt))
        for bt in historical_bedtimes_iso
    ]
    median_hours_past_noon = statistics.median(historical_hours)

    tonight_hours = time_to_hours_past_noon(datetime.fromisoformat(tonight_bedtime_iso))
    diff_minutes = (tonight_hours - median_hours_past_noon) * 60
    score = float(score_bounds.max)

    if diff_minutes > config.consistency_grace_period_mins:
        late_mins = diff_minutes - config.consistency_grace_period_mins
        penalty_ratio = late_mins / config.max_late_penalty_window_mins
        penalty = penalty_ratio * score_bounds.max
        score = max(float(score_bounds.min), score_bounds.max - penalty)

    elif diff_minutes < -config.consistency_grace_period_mins:
        early_mins = abs(diff_minutes) - config.consistency_grace_period_mins
        penalty_ratio = early_mins / config.max_early_penalty_window_mins
        penalty = min(config.max_early_penalty_points, penalty_ratio * score_bounds.max)
        score = max(float(score_bounds.min), score_bounds.max - penalty)

    return int(score)


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
        duration_score = max(
            float(score_bounds.min),
            config.duration_weight_points - duration_penalty,
        )

    significant_awakenings = [
        d for d in awakening_durations if d > config.significant_wake_threshold_mins
    ]
    n = len(significant_awakenings)
    freq = config.frequency_weight_points
    if n <= 1:
        freq_score = freq
    elif n == 2:
        freq_score = freq * 0.75
    elif n == 3:
        freq_score = freq * 0.5
    else:  # 4+
        freq_score = 0.0

    return int(duration_score + freq_score)


def parse_wearable_stages_for_interruptions(
    raw_stage_blocks: list[dict[str, str | float]],
) -> dict[str, float | list[float]]:
    """Strip sleep latency and morning lying-in-bed periods to calculate true WASO.

    Expected input: [{"stage": "awake"|"light"|..., "duration_mins": float}, ...]
    Returns total WASO minutes and individual awakening durations.
    """
    if not raw_stage_blocks:
        return {"total_awake_minutes": 0.0, "awakening_durations": []}

    first_sleep_idx = 0
    for i, block in enumerate(raw_stage_blocks):
        if block["stage"].lower() != "awake":
            first_sleep_idx = i
            break

    last_sleep_idx = len(raw_stage_blocks) - 1
    for i in range(len(raw_stage_blocks) - 1, -1, -1):
        if raw_stage_blocks[i]["stage"].lower() != "awake":
            last_sleep_idx = i
            break

    true_sleep_period = raw_stage_blocks[first_sleep_idx : last_sleep_idx + 1]

    waso_total_minutes = 0.0
    awakening_durations: list[float] = []
    for block in true_sleep_period:
        if block["stage"].lower() == "awake":
            waso_total_minutes += float(block["duration_mins"])
            awakening_durations.append(float(block["duration_mins"]))

    return {
        "total_awake_minutes": waso_total_minutes,
        "awakening_durations": awakening_durations,
    }


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
) -> dict:
    """Combine all four pillars into a single overall sleep score.

    Uses total_sleep_minutes (pre-computed net sleep) for duration scoring.
    session_start is the bedtime ISO string used only for consistency scoring.

    Returns a dict with keys: overall_score, metrics, breakdown.
    """
    duration_hours = total_sleep_minutes / 60.0
    duration_score = _score_duration_hours(
        duration_hours, DURATION_SCORE_BOUNDS, config
    )
    stages_score = calculate_total_stages_score(
        deep_minutes, rem_minutes, STAGE_SCORE_BOUNDS, config
    )
    consistency_score = calculate_bedtime_consistency_score(
        historical_bedtimes, session_start, CONSISTENCY_SCORE_BOUNDS, config
    )
    interruptions_score = calculate_interruptions_score(
        total_awake_minutes, awakening_durations, INTERRUPTIONS_SCORE_BOUNDS, config
    )

    overall = max(
        score_bounds.min,
        min(
            score_bounds.max,
            int(
                duration_score * config.duration_impact
                + stages_score * config.stages_impact
                + consistency_score * config.consistency_impact
                + interruptions_score * config.interruptions_impact
            ),
        ),
    )

    return {
        "overall_score": overall,
        "metrics": {"duration_hours": round(duration_hours, 2)},
        "breakdown": {
            "duration": {"score": duration_score},
            "stages": {"score": stages_score},
            "consistency": {"score": consistency_score},
            "interruptions": {"score": interruptions_score},
        },
    }


def convert_stages_to_duration_blocks(
    raw_stages_json: list[dict[str, str]],
) -> list[dict[str, str | float]]:
    """Convert start_time/end_time stage blocks to duration_mins format.

    Input:  [{"stage": "...", "start_time": "...", "end_time": "..."}, ...]
    Output: [{"stage": "...", "duration_mins": float}, ...]
    """
    result: list[dict[str, str | float]] = []
    for block in raw_stages_json:
        start = datetime.fromisoformat(block["start_time"].rstrip("Z"))
        end = datetime.fromisoformat(block["end_time"].rstrip("Z"))
        duration_mins = (end - start).total_seconds() / 60.0
        result.append({"stage": block["stage"], "duration_mins": duration_mins})
    return result
