import numpy as np


def hr_to_rr_intervals_ms(hr_series: list[float]) -> np.ndarray:
    """Convert raw HR (bpm) measurements to RR intervals in milliseconds.

    Args:
        hr_series: Heart rate values in beats per minute.

    Returns:
        Array of RR intervals in milliseconds, with non-positive and non-finite values removed.
    """
    hr_array = np.asarray(hr_series, dtype=float)
    if hr_array.size == 0:
        return hr_array
    hr_array = hr_array[np.isfinite(hr_array) & (hr_array > 0)]
    if hr_array.size == 0:
        return hr_array
    return 60000 / hr_array


def calculate_rmssd(hr_series: list[float]) -> float:
    """Calculate RMSSD from raw HR (bpm) measurements.

    Args:
        hr_series: Heart rate values in beats per minute.

    Returns:
        RMSSD value in milliseconds, or NaN if fewer than 2 valid samples.
    """
    rr_intervals_ms = hr_to_rr_intervals_ms(hr_series)
    if rr_intervals_ms.size < 2:
        return np.nan
    return float(np.sqrt(np.mean(np.diff(rr_intervals_ms) ** 2)))


def calculate_sdnn(hr_series: list[float]) -> float:
    """Calculate SDNN from raw HR (bpm) measurements.

    Args:
        hr_series: Heart rate values in beats per minute.

    Returns:
        SDNN value in milliseconds, or NaN if fewer than 2 valid samples.
    """
    rr_intervals_ms = hr_to_rr_intervals_ms(hr_series)
    if rr_intervals_ms.size < 2:
        return np.nan
    return float(np.std(rr_intervals_ms, ddof=1))


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
