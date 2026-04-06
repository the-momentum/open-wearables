"""Sleep score calculation: 4-component model.

Components (master weights must sum to 1.0):
  - Duration     40%  — sigmoid curves around 7–9 h ideal
  - Stages       20%  — deep + REM vs 90-min target each
  - Consistency  20%  — bedtime deviation from rolling median
  - Interruptions 20% — WASO duration + awakening frequency
"""

import math
import statistics
from datetime import datetime

MASTER_WEIGHTS_CONFIG = {
    "duration": 0.40,
    "stages": 0.20,
    "consistency": 0.20,
    "interruptions": 0.20,
}

CONSISTENCY_CONFIG = {
    "base_score": 100.0,
    "grace_period_mins": 15.0,
    "max_late_penalty_window_mins": 105.0,
    "max_early_penalty_window_mins": 105.0,
    "max_early_penalty_points": 20.0,
}

INTERRUPTIONS_CONFIG = {
    "duration_weight_points": 80.0,
    "frequency_weight_points": 20.0,
    "grace_period_mins": 20.0,
    "max_penalty_window_mins": 70.0,
    "significant_wake_threshold_mins": 5.0,
    "max_allowed_wakes_count": 4,
}

_FMT = "%Y-%m-%dT%H:%M:%S"


def _sigmoid_score(hours: float, k: float, midpoint: float, boundary: float, clamp_min: int = 0) -> int:
    """Scaled sigmoid that hits exactly 100 at *boundary* and clamps at *clamp_min*."""
    raw = 100 / (1 + math.exp(k * (hours - midpoint)))
    scale = 100 / (100 / (1 + math.exp(k * (boundary - midpoint))))
    return max(clamp_min, int(raw * scale))


def calculate_duration_score(day_start_iso: str, day_end_iso: str) -> dict:
    """0-100 duration score using sigmoid curves around the 7–9 h ideal."""
    start_time = datetime.strptime(day_start_iso[:19], _FMT)
    end_time = datetime.strptime(day_end_iso[:19], _FMT)
    duration_hours = (end_time - start_time).total_seconds() / 3600

    if 7.0 <= duration_hours <= 9.0:
        score = 100
    elif duration_hours < 7.0:
        # k=1.8, midpoint=5.5h: ensures 6h scores clearly lower than 10h,
        # penalising undersleeping more harshly than oversleeping.
        score = _sigmoid_score(duration_hours, k=-1.8, midpoint=5.5, boundary=7.0)
    else:
        # Gentle drop with a 50-point floor — oversleeping is not heavily penalised.
        score = _sigmoid_score(duration_hours, k=0.8, midpoint=11.0, boundary=9.0, clamp_min=50)

    return {"duration_hours": round(duration_hours, 2), "duration_score": score}


def calculate_stage_score(
    stage_duration_minutes: float,
    optimal_target_minutes: float = 90.0,
) -> int:
    """0-100 score for a single stage vs its target."""
    if stage_duration_minutes >= optimal_target_minutes:
        return 100
    if stage_duration_minutes <= 0:
        return 0
    return int((stage_duration_minutes / optimal_target_minutes) * 100)


def calculate_total_stages_score(deep_minutes: float, rem_minutes: float) -> int:
    """Combined deep + REM stages score (50/50 weight)."""
    return int(calculate_stage_score(deep_minutes) * 0.5 + calculate_stage_score(rem_minutes) * 0.5)


def _time_to_hours_past_noon(dt: datetime) -> float:
    hours = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    if hours < 12.0:
        hours += 24.0
    return hours - 12.0


def calculate_bedtime_consistency_score(
    historical_bedtimes_iso: list[str],
    tonight_bedtime_iso: str,
    config: dict = CONSISTENCY_CONFIG,
) -> int:
    """0-100 consistency score: deviation from rolling median bedtime."""
    if not historical_bedtimes_iso:
        return int(config["base_score"])

    historical_hours = [_time_to_hours_past_noon(datetime.strptime(bt[:19], _FMT)) for bt in historical_bedtimes_iso]
    median_hours = statistics.median(historical_hours)
    tonight_hours = _time_to_hours_past_noon(datetime.strptime(tonight_bedtime_iso[:19], _FMT))

    diff_minutes = (tonight_hours - median_hours) * 60
    score = config["base_score"]

    if diff_minutes > config["grace_period_mins"]:
        late_mins = diff_minutes - config["grace_period_mins"]
        penalty = (late_mins / config["max_late_penalty_window_mins"]) * config["base_score"]
        score = max(0.0, config["base_score"] - penalty)
    elif diff_minutes < -config["grace_period_mins"]:
        early_mins = abs(diff_minutes) - config["grace_period_mins"]
        penalty = min(
            config["max_early_penalty_points"],
            (early_mins / config["max_early_penalty_window_mins"]) * config["max_early_penalty_points"],
        )
        score = max(0.0, config["base_score"] - penalty)

    return int(score)


def calculate_interruptions_score(
    total_awake_minutes: float,
    awakening_durations: list[float],
    config: dict = INTERRUPTIONS_CONFIG,
) -> int:
    """0-100 interruptions score: WASO duration + significant awakening count."""
    duration_score = config["duration_weight_points"]
    if total_awake_minutes > config["grace_period_mins"]:
        excess = total_awake_minutes - config["grace_period_mins"]
        penalty = (excess / config["max_penalty_window_mins"]) * config["duration_weight_points"]
        duration_score = max(0.0, config["duration_weight_points"] - penalty)

    freq_score = config["frequency_weight_points"]
    significant = [d for d in awakening_durations if d > config["significant_wake_threshold_mins"]]
    if len(significant) >= config["max_allowed_wakes_count"]:
        freq_score = 0.0

    return int(duration_score + freq_score)


def parse_wearable_stages_for_interruptions(raw_stage_blocks: list[dict]) -> dict:
    """Extract true WASO from a stage timeline, ignoring latency and lie-in.

    Accepts blocks with keys ``stage`` and ``duration_mins`` or with
    ``start_time`` / ``end_time`` datetime strings (SleepStage format).
    """
    if not raw_stage_blocks:
        return {"total_awake_minutes": 0.0, "awakening_durations": []}

    awake_stages = {"awake", "in_bed"}

    # Single pass: normalise input and track sleep boundary indices simultaneously.
    blocks: list[tuple[str, float]] = []
    first_sleep_idx = last_sleep_idx = None
    for i, b in enumerate(raw_stage_blocks):
        stage = (b.get("stage") or "").lower()
        if "duration_mins" in b:
            duration = float(b["duration_mins"])
        elif "start_time" in b and "end_time" in b:
            try:
                start = datetime.fromisoformat(str(b["start_time"]).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(b["end_time"]).replace("Z", "+00:00"))
                duration = (end - start).total_seconds() / 60
            except Exception:
                duration = 0.0
        else:
            duration = 0.0
        blocks.append((stage, duration))
        if stage not in awake_stages:
            if first_sleep_idx is None:
                first_sleep_idx = i
            last_sleep_idx = i

    if first_sleep_idx is None:
        return {"total_awake_minutes": 0.0, "awakening_durations": []}
    assert last_sleep_idx is not None  # set whenever first_sleep_idx is set

    waso_total = 0.0
    awakening_durations = []
    for stage, duration in blocks[first_sleep_idx : last_sleep_idx + 1]:
        if stage in awake_stages:
            waso_total += duration
            awakening_durations.append(duration)

    return {"total_awake_minutes": waso_total, "awakening_durations": awakening_durations}


def calculate_overall_sleep_score(
    session_start: str,
    session_end: str,
    deep_minutes: float,
    rem_minutes: float,
    historical_bedtimes: list[str],
    total_awake_minutes: float,
    awakening_durations: list[float],
    weights: dict = MASTER_WEIGHTS_CONFIG,
) -> dict:
    """Compute the overall sleep score and return the full breakdown payload."""
    duration_score = calculate_duration_score(session_start, session_end)["duration_score"]
    stages_score = calculate_total_stages_score(deep_minutes, rem_minutes)
    consistency_score = calculate_bedtime_consistency_score(historical_bedtimes, session_start)
    interruptions_score = calculate_interruptions_score(total_awake_minutes, awakening_durations)

    overall = int(
        duration_score * weights["duration"]
        + stages_score * weights["stages"]
        + consistency_score * weights["consistency"]
        + interruptions_score * weights["interruptions"]
    )

    return {
        "overall_score": overall,
        "breakdown": {
            "duration": {"weight": f"{int(weights['duration'] * 100)}%", "score": duration_score},
            "stages": {"weight": f"{int(weights['stages'] * 100)}%", "score": stages_score},
            "consistency": {"weight": f"{int(weights['consistency'] * 100)}%", "score": consistency_score},
            "interruptions": {"weight": f"{int(weights['interruptions'] * 100)}%", "score": interruptions_score},
        },
    }
