"""Sleep score calculation algorithms."""

import math
import statistics
from datetime import datetime

from app.algorithms.config_algorithms import (
    SleepConsistencyConfig,
    SleepInterruptionsConfig,
    SleepMasterWeightsConfig,
    sleep_consistency_config,
    sleep_interruptions_config,
    sleep_master_weights_config,
)


def _score_duration_hours(duration_hours: float) -> int:
    """Score a sleep duration (in hours) on a 0-100 scale.

    Perfect score for 7-9 hours. Steep sigmoid drop-off for under-sleeping,
    gentler drop-off for over-sleeping (floor at 50).
    """
    if 7.0 <= duration_hours <= 9.0:
        return 100

    if duration_hours < 7.0:
        # Steep sigmoid: 7h → 100, drops near 0 around 3h.
        k = 1.5
        midpoint = 5.0
        score = 100 / (1 + math.exp(-k * (duration_hours - midpoint)))
        scale_factor = 100 / (100 / (1 + math.exp(-k * (7.0 - midpoint))))
        return int(score * scale_factor)

    # Gentler sigmoid for over-sleeping: 9h → 100, drops slowly.
    k = 0.8
    midpoint = 11.0
    score = 100 / (1 + math.exp(k * (duration_hours - midpoint)))
    scale_factor = 100 / (100 / (1 + math.exp(k * (9.0 - midpoint))))
    return max(50, int(score * scale_factor))


def calculate_duration_score(
    day_start_iso: str, day_end_iso: str, awake_minutes: float = 0.0
) -> dict[str, float | int]:
    """Calculate a sleep duration score (0-100) based on actual sleep hours.

    Subtracts awake_minutes (WASO) from the raw session length before scoring.
    """
    start_time = datetime.fromisoformat(day_start_iso)
    end_time = datetime.fromisoformat(day_end_iso)
    duration_hours = (end_time - start_time).total_seconds() / 3600 - awake_minutes / 60.0
    return {"duration_hours": round(duration_hours, 2), "duration_score": _score_duration_hours(duration_hours)}


def calculate_stage_score(stage_duration_minutes: float, optimal_target_minutes: float = 90.0) -> int:
    """Calculate a 0-100 score for a sleep stage based on absolute duration.

    Standard target for both Deep and REM is 90 minutes. Uses linear drop-off
    below the target (e.g. 45 min out of 90 min target = 50 points).
    """
    if stage_duration_minutes >= optimal_target_minutes:
        return 100
    if stage_duration_minutes <= 0:
        return 0
    return int((stage_duration_minutes / optimal_target_minutes) * 100)


def calculate_total_stages_score(deep_minutes: float, rem_minutes: float) -> int:
    """Combine Deep and REM into a single 0-100 stages score (50% weight each)."""
    deep_score = calculate_stage_score(deep_minutes, optimal_target_minutes=90.0)
    rem_score = calculate_stage_score(rem_minutes, optimal_target_minutes=90.0)
    return int((deep_score * 0.5) + (rem_score * 0.5))


# Consistency — rolling median bedtime


def time_to_hours_past_noon(dt: datetime) -> float:
    """Convert a datetime to continuous hours past noon to handle the midnight boundary."""
    hours = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    if hours < 12.0:
        hours += 24.0
    return hours - 12.0


def calculate_bedtime_consistency_score(
    historical_bedtimes_iso: list[str],
    tonight_bedtime_iso: str,
    config: SleepConsistencyConfig = sleep_consistency_config,
) -> int:
    """Calculate a 0-100 consistency score based on a rolling median bedtime."""
    if not historical_bedtimes_iso:
        return int(config.base_score)

    historical_hours = [time_to_hours_past_noon(datetime.fromisoformat(bt)) for bt in historical_bedtimes_iso]
    median_hours_past_noon = statistics.median(historical_hours)

    tonight_hours = time_to_hours_past_noon(datetime.fromisoformat(tonight_bedtime_iso))
    diff_minutes = (tonight_hours - median_hours_past_noon) * 60
    score = config.base_score

    if diff_minutes > config.grace_period_mins:
        late_mins = diff_minutes - config.grace_period_mins
        penalty_ratio = late_mins / config.max_late_penalty_window_mins
        penalty = penalty_ratio * config.base_score
        score = max(0.0, config.base_score - penalty)

    elif diff_minutes < -config.grace_period_mins:
        early_mins = abs(diff_minutes) - config.grace_period_mins
        penalty_ratio = early_mins / config.max_early_penalty_window_mins
        penalty = min(config.max_early_penalty_points, penalty_ratio * config.base_score)
        score = max(0.0, config.base_score - penalty)

    return int(score)


# Interruptions — true WASO duration + awakening frequency


def calculate_interruptions_score(
    total_awake_minutes: float,
    awakening_durations: list[float],
    config: SleepInterruptionsConfig = sleep_interruptions_config,
) -> int:
    """Calculate a 0-100 interruptions score based on WASO and awakening frequency."""
    duration_score = config.duration_weight_points
    if total_awake_minutes > config.grace_period_mins:
        excess_awake_mins = total_awake_minutes - config.grace_period_mins
        penalty_ratio = excess_awake_mins / config.max_penalty_window_mins
        duration_penalty = penalty_ratio * config.duration_weight_points
        duration_score = max(0.0, config.duration_weight_points - duration_penalty)

    significant_awakenings = [d for d in awakening_durations if d > config.significant_wake_threshold_mins]
    n = len(significant_awakenings)
    if n <= 1:
        freq_score = 20.0
    elif n == 2:
        freq_score = 15.0
    elif n == 3:
        freq_score = 10.0
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

    return {"total_awake_minutes": waso_total_minutes, "awakening_durations": awakening_durations}


def calculate_overall_sleep_score(
    total_sleep_minutes: float,
    deep_minutes: float,
    rem_minutes: float,
    session_start: str,
    historical_bedtimes: list[str],
    total_awake_minutes: float,
    awakening_durations: list[float],
    weights: SleepMasterWeightsConfig = sleep_master_weights_config,
) -> dict:
    """Combine all four pillars into a single overall sleep score (0-100).

    Uses total_sleep_minutes (pre-computed net sleep) for duration scoring.
    session_start is the bedtime ISO string used only for consistency scoring.

    Returns a dict with keys: overall_score, metrics, breakdown.
    """
    duration_hours = total_sleep_minutes / 60.0
    duration_score = _score_duration_hours(duration_hours)
    stages_score = calculate_total_stages_score(deep_minutes, rem_minutes)
    consistency_score = calculate_bedtime_consistency_score(historical_bedtimes, session_start)
    interruptions_score = calculate_interruptions_score(total_awake_minutes, awakening_durations)

    overall = int(
        duration_score * weights.duration
        + stages_score * weights.stages
        + consistency_score * weights.consistency
        + interruptions_score * weights.interruptions
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
