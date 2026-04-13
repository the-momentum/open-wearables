"""Unit tests for HRV resilience algorithm functions.

Covers every function in app.algorithms.resilience:
  - hr_to_rr_intervals_ms
  - calculate_rmssd
  - calculate_sdnn
  - calculate_hrv_cv

Pure-Python only — no database, no factories.
"""

import math

import numpy as np
import pytest

from app.algorithms.resilience import (
    calculate_hrv_cv,
    calculate_rmssd,
    calculate_sdnn,
    hr_to_rr_intervals_ms,
)

# ---------------------------------------------------------------------------
# hr_to_rr_intervals_ms
# ---------------------------------------------------------------------------


class TestHrToRrIntervalsMs:
    """hr_to_rr_intervals_ms converts HR (bpm) to RR intervals (ms)."""

    def test_single_value(self) -> None:
        """60 bpm → 1000 ms."""
        result = hr_to_rr_intervals_ms([60.0])
        assert result.tolist() == pytest.approx([1000.0])

    def test_multiple_values(self) -> None:
        """120 bpm → 500 ms, 60 bpm → 1000 ms."""
        result = hr_to_rr_intervals_ms([120.0, 60.0])
        assert result.tolist() == pytest.approx([500.0, 1000.0])

    def test_empty_input_returns_empty_array(self) -> None:
        result = hr_to_rr_intervals_ms([])
        assert result.size == 0

    def test_all_nan_returns_empty_array(self) -> None:
        result = hr_to_rr_intervals_ms([float("nan"), float("nan")])
        assert result.size == 0

    def test_nan_values_are_removed(self) -> None:
        """NaN entries are stripped; valid values remain."""
        result = hr_to_rr_intervals_ms([60.0, float("nan"), 120.0])
        assert result.size == 2
        assert result.tolist() == pytest.approx([1000.0, 500.0])

    def test_returns_numpy_array(self) -> None:
        result = hr_to_rr_intervals_ms([60.0])
        assert isinstance(result, np.ndarray)

    def test_high_hr_produces_short_rr(self) -> None:
        """200 bpm → 300 ms."""
        result = hr_to_rr_intervals_ms([200.0])
        assert result.tolist() == pytest.approx([300.0])

    def test_zero_hr_removed(self) -> None:
        """0 bpm would cause division by zero; it is stripped."""
        result = hr_to_rr_intervals_ms([0.0, 60.0])
        assert result.tolist() == pytest.approx([1000.0])

    def test_negative_hr_removed(self) -> None:
        """Negative HR values are invalid and must be stripped."""
        result = hr_to_rr_intervals_ms([-10.0, 60.0])
        assert result.tolist() == pytest.approx([1000.0])

    def test_inf_hr_removed(self) -> None:
        """Infinite HR values are invalid and must be stripped."""
        result = hr_to_rr_intervals_ms([float("inf"), 60.0])
        assert result.tolist() == pytest.approx([1000.0])

    def test_all_invalid_returns_empty(self) -> None:
        """All-zero/negative/inf → empty array, not inf or error."""
        result = hr_to_rr_intervals_ms([0.0, -5.0, float("inf")])
        assert result.size == 0


# ---------------------------------------------------------------------------
# calculate_rmssd
# ---------------------------------------------------------------------------


class TestCalculateRmssd:
    """calculate_rmssd computes Root Mean Square of Successive Differences."""

    def test_constant_hr_produces_zero_rmssd(self) -> None:
        """Perfectly constant HR → zero successive differences → RMSSD = 0."""
        result = calculate_rmssd([60.0] * 10)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_single_value_returns_nan(self) -> None:
        """Need at least 2 samples to compute a difference."""
        result = calculate_rmssd([60.0])
        assert math.isnan(result)

    def test_empty_input_returns_nan(self) -> None:
        result = calculate_rmssd([])
        assert math.isnan(result)

    def test_two_values_produces_nonzero_result(self) -> None:
        """Two different HR values → one difference → non-NaN result."""
        result = calculate_rmssd([60.0, 80.0])
        assert not math.isnan(result)
        assert result > 0

    def test_all_nan_returns_nan(self) -> None:
        result = calculate_rmssd([float("nan"), float("nan")])
        assert math.isnan(result)

    def test_returns_float(self) -> None:
        result = calculate_rmssd([60.0, 65.0, 70.0])
        assert isinstance(result, float)

    def test_returns_positive_value(self) -> None:
        """RMSSD is always non-negative."""
        result = calculate_rmssd([55.0, 65.0, 60.0, 70.0, 62.0])
        assert result >= 0.0

    def test_higher_variability_yields_higher_rmssd(self) -> None:
        """More variable HR → higher RMSSD."""
        low_var = calculate_rmssd([60.0, 61.0, 60.0, 61.0, 60.0])
        high_var = calculate_rmssd([50.0, 80.0, 50.0, 80.0, 50.0])
        assert high_var > low_var

    def test_nan_mixed_with_valid_values(self) -> None:
        """NaN values are stripped before calculation; result uses remaining samples."""
        result_clean = calculate_rmssd([60.0, 65.0, 70.0])
        result_with_nan = calculate_rmssd([60.0, float("nan"), 65.0, 70.0])
        assert result_clean == pytest.approx(result_with_nan, rel=1e-6)


# ---------------------------------------------------------------------------
# calculate_sdnn
# ---------------------------------------------------------------------------


class TestCalculateSdnn:
    """calculate_sdnn computes Standard Deviation of NN intervals."""

    def test_constant_hr_produces_zero_sdnn(self) -> None:
        """No variation in HR → RR intervals identical → SDNN = 0."""
        result = calculate_sdnn([60.0] * 10)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_single_value_returns_nan(self) -> None:
        result = calculate_sdnn([60.0])
        assert math.isnan(result)

    def test_empty_input_returns_nan(self) -> None:
        result = calculate_sdnn([])
        assert math.isnan(result)

    def test_two_values_produces_nonzero_result(self) -> None:
        result = calculate_sdnn([60.0, 80.0])
        assert not math.isnan(result)
        assert result > 0

    def test_all_nan_returns_nan(self) -> None:
        result = calculate_sdnn([float("nan"), float("nan")])
        assert math.isnan(result)

    def test_returns_float(self) -> None:
        result = calculate_sdnn([60.0, 65.0, 70.0])
        assert isinstance(result, float)

    def test_returns_positive_value(self) -> None:
        result = calculate_sdnn([55.0, 65.0, 60.0, 70.0, 62.0])
        assert result >= 0.0

    def test_higher_variability_yields_higher_sdnn(self) -> None:
        low_var = calculate_sdnn([60.0, 61.0, 60.0, 61.0, 60.0])
        high_var = calculate_sdnn([50.0, 80.0, 50.0, 80.0, 50.0])
        assert high_var > low_var

    def test_uses_ddof_1(self) -> None:
        """Verify sample std (ddof=1), not population std."""
        # Two-sample std: |a - b| / sqrt(2) * sqrt(2) = |RR1 - RR2| / sqrt(2) ... but
        # easier: just verify it differs from population std.
        hr = [60.0, 80.0, 70.0]
        rr = 60000.0 / np.array(hr)
        population_std = float(np.std(rr, ddof=0))
        sample_std = float(np.std(rr, ddof=1))
        result = calculate_sdnn(hr)
        assert result == pytest.approx(sample_std, rel=1e-9)
        assert result != pytest.approx(population_std, rel=1e-9)

    def test_nan_mixed_with_valid_values(self) -> None:
        result_clean = calculate_sdnn([60.0, 65.0, 70.0])
        result_with_nan = calculate_sdnn([60.0, float("nan"), 65.0, 70.0])
        assert result_clean == pytest.approx(result_with_nan, rel=1e-6)


# ---------------------------------------------------------------------------
# calculate_hrv_cv
# ---------------------------------------------------------------------------


class TestCalculateHrvCv:
    """calculate_hrv_cv computes coefficient of variation of a HRV series."""

    def test_identical_values_produce_zero_cv(self) -> None:
        """std=0, mean>0 → CV = 0."""
        result = calculate_hrv_cv([50.0, 50.0, 50.0])
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_cv_equals_std_over_mean(self) -> None:
        values = [40.0, 50.0, 60.0]
        arr = np.array(values)
        expected = float(np.std(arr, ddof=1) / np.mean(arr))
        assert calculate_hrv_cv(values) == pytest.approx(expected, rel=1e-9)

    def test_single_value_returns_nan(self) -> None:
        result = calculate_hrv_cv([50.0])
        assert math.isnan(result)

    def test_empty_input_returns_nan(self) -> None:
        result = calculate_hrv_cv([])
        assert math.isnan(result)

    def test_all_nan_returns_nan(self) -> None:
        result = calculate_hrv_cv([float("nan"), float("nan")])
        assert math.isnan(result)

    def test_nan_stripped_leaving_one_value_returns_nan(self) -> None:
        result = calculate_hrv_cv([float("nan"), 50.0])
        assert math.isnan(result)

    def test_nan_stripped_leaving_two_values_is_valid(self) -> None:
        result = calculate_hrv_cv([float("nan"), 40.0, 60.0])
        assert not math.isnan(result)
        assert result > 0.0

    def test_returns_float(self) -> None:
        result = calculate_hrv_cv([40.0, 50.0, 60.0])
        assert isinstance(result, float)

    def test_returns_positive_value_for_variable_series(self) -> None:
        result = calculate_hrv_cv([30.0, 50.0, 70.0])
        assert result > 0.0

    def test_higher_spread_yields_higher_cv(self) -> None:
        low_spread = calculate_hrv_cv([48.0, 50.0, 52.0])
        high_spread = calculate_hrv_cv([30.0, 50.0, 70.0])
        assert high_spread > low_spread

    def test_two_values_minimum_valid_input(self) -> None:
        result = calculate_hrv_cv([40.0, 60.0])
        assert not math.isnan(result)
        assert result > 0.0

    def test_zero_values_removed(self) -> None:
        """0 ms HRV is non-physiological; zero values are stripped."""
        result = calculate_hrv_cv([0.0, 50.0, 60.0])
        expected = calculate_hrv_cv([50.0, 60.0])
        assert result == pytest.approx(expected, rel=1e-9)

    def test_negative_values_removed(self) -> None:
        """Negative HRV values are invalid and must be stripped."""
        result = calculate_hrv_cv([-10.0, 50.0, 60.0])
        expected = calculate_hrv_cv([50.0, 60.0])
        assert result == pytest.approx(expected, rel=1e-9)

    def test_inf_values_removed(self) -> None:
        """Infinite HRV values are invalid and must be stripped."""
        result = calculate_hrv_cv([float("inf"), 50.0, 60.0])
        expected = calculate_hrv_cv([50.0, 60.0])
        assert result == pytest.approx(expected, rel=1e-9)

    def test_all_invalid_returns_nan(self) -> None:
        """All-zero/negative/inf → NaN, not an error."""
        result = calculate_hrv_cv([0.0, -5.0, float("inf")])
        assert math.isnan(result)
