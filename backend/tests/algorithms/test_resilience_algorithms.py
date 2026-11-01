"""Unit tests for HRV resilience algorithm functions.

Covers every function in app.algorithms.resilience:
  - calculate_hrv_cv

Pure-Python only — no database, no factories.
"""

import math

import numpy as np
import pytest

from app.algorithms.resilience import calculate_hrv_cv

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
