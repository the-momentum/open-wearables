import numpy as np


def calculate_hrv_cv(hrv_series: list[float]) -> float:
    """Calculate the coefficient of variation for a HRV series in milliseconds.

    Args:
        hrv_series: HRV values in milliseconds.

    Returns:
        Coefficient of variation (std / mean), or NaN if fewer than 2 valid samples
        or if the mean is zero.
    """
    hrv_ms = np.asarray(hrv_series, dtype=float)
    if hrv_ms.size == 0:
        return np.nan
    hrv_ms = hrv_ms[np.isfinite(hrv_ms) & (hrv_ms > 0)]
    if hrv_ms.size < 2:
        return np.nan
    mean_ms = np.mean(hrv_ms)
    if mean_ms == 0:
        return np.nan
    return float(np.std(hrv_ms, ddof=1) / mean_ms)
