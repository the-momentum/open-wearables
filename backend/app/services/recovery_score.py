"""Recovery score calculation using physiological baselines (HRV, RHR, Sleep).

Based on an empirical z-score framework:
- HRV (40%): nervous system stress indicator
- RHR (30%): cardiovascular load
- Sleep (30%): behavioral recovery

Scores are normalized to 0-100 using the Empirical Rule where Z=0 → 70 and Z=±2 → 100/0.
"""

import math
import statistics
from typing import Optional

MASTER_RECOVERY_WEIGHTS: dict[str, float] = {
    "hrv_score": 0.40,
    "rhr_score": 0.30,
    "sleep_score": 0.30,
}

RECOVERY_PHYSIO_CONFIG: dict[str, float | int] = {
    "neutral_score": 70.0,
    "max_z_score": 2.0,
    "min_z_score": -2.0,
    "min_baseline_days": 3,
}


def _transform_metric(value: float, metric_type: str) -> float:
    """Apply log normalization to skewed physiological data.

    HRV metrics (rmssd, sdnn) are log-transformed per Marco Altini's framework.
    RHR requires no transformation.
    """
    if value <= 0:
        return 0.0
    if metric_type in ("rmssd", "sdnn"):
        return math.log(value)
    return value


def _z_score_to_0_100(z_score: float, is_hrv: bool, config: dict) -> int:
    """Map a Z-score to 0-100 using the Empirical Rule.

    HRV: higher Z = better (higher HRV = better recovery).
    RHR: lower Z = better, so invert before scaling.
    Z=0 → neutral_score (70), Z=+2 → 100, Z=-2 → 0.
    """
    if not is_hrv:
        z_score = -z_score

    neutral = config["neutral_score"]
    if z_score >= 0:
        bonus = (z_score / config["max_z_score"]) * (100.0 - neutral)
        score = neutral + bonus
    else:
        penalty = (abs(z_score) / abs(config["min_z_score"])) * neutral
        score = neutral - penalty

    return int(max(0.0, min(100.0, score)))


def calculate_physio_score(
    daily_value: float,
    historical_values: list[float],
    metric_type: str,
    config: dict = RECOVERY_PHYSIO_CONFIG,
) -> dict:
    """Compute a 0-100 score for a physiological metric relative to a personal baseline.

    Args:
        daily_value: Today's raw measurement.
        historical_values: Prior days' raw measurements (the baseline).
        metric_type: One of "rmssd", "sdnn", or "rhr".
        config: Scoring configuration (neutral score, z-score bounds, min days).

    Returns:
        Dict with keys: score (int), z_score (float), status (str).
    """
    transformed_daily = _transform_metric(daily_value, metric_type)
    transformed_history = [_transform_metric(v, metric_type) for v in historical_values]

    if len(transformed_history) < config["min_baseline_days"]:
        return {
            "score": int(config["neutral_score"]),
            "z_score": 0.0,
            "status": "calculating_baseline",
        }

    mean_val = statistics.mean(transformed_history)
    std_dev = statistics.stdev(transformed_history)

    z_score = 0.0 if std_dev == 0 else (transformed_daily - mean_val) / std_dev
    is_hrv = metric_type in ("rmssd", "sdnn")

    return {
        "score": _z_score_to_0_100(z_score, is_hrv, config),
        "z_score": round(z_score, 2),
        "status": "active",
    }


def calculate_master_recovery_score(
    user_id: str,
    daily_sleep_score: Optional[int] = None,
    daily_hrv: Optional[float] = None,
    historical_hrv: Optional[list[float]] = None,
    hrv_metric_type: str = "sdnn",
    daily_rhr: Optional[float] = None,
    historical_rhr: Optional[list[float]] = None,
    weights: dict = MASTER_RECOVERY_WEIGHTS,
) -> dict:
    """Compute the master recovery score from sub-components.

    Dynamically re-weights if a wearable fails to record a metric.
    Refuses to return a score when no physiological data (HRV or RHR) is present
    to prevent sleep-only scores from masking poor physiological recovery.

    Args:
        user_id: User identifier (for response payload).
        daily_sleep_score: Sleep efficiency score 0-100 (optional).
        daily_hrv: Today's HRV reading (ms).
        historical_hrv: Prior days' HRV readings for baseline.
        hrv_metric_type: Transformation type — "sdnn" or "rmssd".
        daily_rhr: Today's resting heart rate (bpm).
        historical_rhr: Prior days' RHR readings for baseline.
        weights: Component weight overrides.

    Returns:
        Dict with: user_id, recovery_score, status, component_scores, applied_weights.
    """
    if historical_hrv is None:
        historical_hrv = []
    if historical_rhr is None:
        historical_rhr = []

    # Require at least one physiological metric — sleep alone is insufficient.
    if daily_hrv is None and daily_rhr is None:
        return {
            "user_id": user_id,
            "recovery_score": None,
            "status": "insufficient_data",
            "component_scores": {},
            "applied_weights": {},
        }

    available_scores: dict[str, int] = {}

    if daily_sleep_score is not None:
        available_scores["sleep_score"] = daily_sleep_score

    if daily_hrv is not None:
        hrv_result = calculate_physio_score(daily_hrv, historical_hrv, hrv_metric_type)
        available_scores["hrv_score"] = hrv_result["score"]

    if daily_rhr is not None:
        rhr_result = calculate_physio_score(daily_rhr, historical_rhr, "rhr")
        available_scores["rhr_score"] = rhr_result["score"]

    # Redistribute missing component weight proportionally across available components.
    total_available_weight = sum(weights[k] for k in available_scores)
    final_score = 0.0
    applied_weights: dict[str, float] = {}

    for key, score in available_scores.items():
        dynamic_weight = weights[key] / total_available_weight
        applied_weights[key] = round(dynamic_weight, 2)
        final_score += score * dynamic_weight

    return {
        "user_id": user_id,
        "recovery_score": int(final_score),
        "status": "success",
        "component_scores": available_scores,
        "applied_weights": applied_weights,
    }
