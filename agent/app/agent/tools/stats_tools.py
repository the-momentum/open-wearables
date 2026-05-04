"""Statistical analysis tools for the reasoning agent.

Pure computation — no I/O, no RunContext required.
The agent first retrieves raw data via OW tools, then calls these tools
to compute statistical insights from the extracted numeric values.

All functions accept a list of floats and return a human-readable string
so the LLM can directly include the result in its answer.
"""

from __future__ import annotations

import statistics


def calculate_mean(values: list[float]) -> str:
    """Compute the arithmetic mean (average) of a numeric series.

    Use this to summarise a health metric over a time window after fetching
    it from one of the OW data tools.

    Args:
        values: List of numeric values (e.g. daily step counts, sleep hours).
    """
    if not values:
        return "Error: empty values list — cannot compute mean."
    try:
        mean = statistics.mean(values)
        return f"Mean: {mean:.4g} (n={len(values)})"
    except Exception as exc:
        return f"Error computing mean: {exc}"


def calculate_stdev(values: list[float]) -> str:
    """Compute the sample standard deviation of a numeric series.

    Use this to measure variability or consistency in a health metric.
    A high CV (coefficient of variation) indicates erratic behaviour;
    a low CV indicates consistency.

    Args:
        values: List of numeric values. Requires at least 2 data points.
    """
    if len(values) < 2:
        return "Error: need at least 2 values to compute standard deviation."
    try:
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        cv = (stdev / mean * 100) if mean != 0 else float("inf")
        return f"Mean: {mean:.4g}, Std dev: {stdev:.4g}, CV: {cv:.1f}%"
    except Exception as exc:
        return f"Error computing standard deviation: {exc}"


def calculate_trend(values: list[float]) -> str:
    """Estimate the linear trend in a time-ordered numeric series.

    Fits a least-squares line to the data and reports slope, direction,
    and the total change over the observed window.

    Args:
        values: Time-ordered list of numeric values (oldest first).
                Requires at least 2 data points.
    """
    if len(values) < 2:
        return "Error: need at least 2 values to compute trend."
    try:
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(values)
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return "Trend: flat (all x values identical)."
        slope = numerator / denominator
        total_change = slope * (n - 1)
        pct_change = (total_change / abs(y_mean) * 100) if y_mean != 0 else float("inf")
        if slope > 0:
            direction = "increasing"
        elif slope < 0:
            direction = "decreasing"
        else:
            direction = "flat"
        return (
            f"Trend: {direction}, slope={slope:.4g} per step, "
            f"total change over {n} points: {total_change:+.4g} ({pct_change:+.1f}%)."
        )
    except Exception as exc:
        return f"Error computing trend: {exc}"


def detect_seasonality(values: list[float], period: int = 7) -> str:
    """Detect periodic patterns in a time-ordered numeric series via autocorrelation.

    Checks whether the series repeats with the given period (default 7 = weekly).
    |autocorrelation| ≥ 0.7 → strong pattern; 0.4–0.7 → moderate; < 0.4 → weak/absent.

    Use this after fetching several weeks of daily data to check for weekly cycles
    in sleep, activity, or recovery metrics.

    Args:
        values: Time-ordered list of numeric values (oldest first).
                Requires at least 2 × period data points.
        period: Number of time steps per cycle to test (default 7 for weekly patterns).
    """
    if len(values) < 2 * period:
        return f"Error: need at least {2 * period} values to test for period={period} seasonality (got {len(values)})."
    try:
        n = len(values)
        mean = statistics.mean(values)
        variance = sum((v - mean) ** 2 for v in values) / n
        if variance == 0:
            return "Seasonality: constant series — no pattern detectable."
        autocov = sum((values[i] - mean) * (values[i - period] - mean) for i in range(period, n)) / n
        autocorr = autocov / variance
        if abs(autocorr) >= 0.7:
            strength = "strong"
        elif abs(autocorr) >= 0.4:
            strength = "moderate"
        else:
            strength = "weak"
        direction = "positive" if autocorr >= 0 else "negative"
        has_pattern = abs(autocorr) >= 0.4
        return f"Seasonality (period={period}): {strength} {direction} autocorrelation = {autocorr:.3f}. " + (
            f"A repeating {period}-step cycle is likely present."
            if has_pattern
            else f"No clear {period}-step cycle detected."
        )
    except Exception as exc:
        return f"Error detecting seasonality: {exc}"


STATS_TOOLS: list = [
    calculate_mean,
    calculate_stdev,
    calculate_trend,
    detect_seasonality,
]
