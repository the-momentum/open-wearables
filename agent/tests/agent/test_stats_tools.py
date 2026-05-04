"""Tests for statistical analysis tools."""

from __future__ import annotations

from app.agent.tools.stats_tools import (
    calculate_mean,
    calculate_stdev,
    calculate_trend,
    detect_seasonality,
)


class TestCalculateMean:
    def test_basic_mean(self) -> None:
        result = calculate_mean([1.0, 2.0, 3.0, 4.0, 5.0])

        assert "3" in result

    def test_returns_count(self) -> None:
        result = calculate_mean([10.0, 20.0, 30.0])

        assert "n=3" in result

    def test_single_value(self) -> None:
        result = calculate_mean([42.0])

        assert "42" in result

    def test_empty_list_returns_error(self) -> None:
        result = calculate_mean([])

        assert "Error" in result

    def test_returns_string(self) -> None:
        assert isinstance(calculate_mean([1.0, 2.0]), str)


class TestCalculateStdev:
    def test_basic_stdev(self) -> None:
        # stdev of [2,4,4,4,5,5,7,9] is 2.0
        result = calculate_stdev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])

        assert isinstance(result, str)
        assert "Std dev" in result

    def test_uniform_series_has_zero_stdev(self) -> None:
        result = calculate_stdev([5.0, 5.0, 5.0, 5.0])

        assert "0" in result

    def test_single_value_returns_error(self) -> None:
        result = calculate_stdev([5.0])

        assert "Error" in result

    def test_empty_list_returns_error(self) -> None:
        result = calculate_stdev([])

        assert "Error" in result

    def test_includes_cv(self) -> None:
        result = calculate_stdev([1.0, 2.0, 3.0])

        assert "CV" in result


class TestCalculateTrend:
    def test_increasing_trend(self) -> None:
        result = calculate_trend([1.0, 2.0, 3.0, 4.0, 5.0])

        assert "increasing" in result

    def test_decreasing_trend(self) -> None:
        result = calculate_trend([5.0, 4.0, 3.0, 2.0, 1.0])

        assert "decreasing" in result

    def test_flat_trend(self) -> None:
        result = calculate_trend([3.0, 3.0, 3.0, 3.0])

        assert "flat" in result

    def test_single_value_returns_error(self) -> None:
        result = calculate_trend([5.0])

        assert "Error" in result

    def test_empty_list_returns_error(self) -> None:
        result = calculate_trend([])

        assert "Error" in result

    def test_includes_slope(self) -> None:
        result = calculate_trend([0.0, 1.0, 2.0, 3.0])

        assert "slope" in result

    def test_includes_total_change(self) -> None:
        result = calculate_trend([10.0, 20.0, 30.0])

        assert "total change" in result

    def test_slope_of_perfect_linear_series(self) -> None:
        # y = 2x → slope should be 2
        result = calculate_trend([0.0, 2.0, 4.0, 6.0, 8.0])

        assert "increasing" in result
        assert "slope=2" in result


class TestDetectSeasonality:
    def test_clear_weekly_pattern(self) -> None:
        # One day of rest per week with otherwise constant activity
        week = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 10.0]
        result = detect_seasonality(week * 4, period=7)

        assert "autocorrelation" in result
        assert isinstance(result, str)

    def test_insufficient_data_returns_error(self) -> None:
        result = detect_seasonality([1.0, 2.0, 3.0], period=7)

        assert "Error" in result

    def test_exactly_2x_period_is_accepted(self) -> None:
        result = detect_seasonality([1.0] * 14, period=7)

        assert "Error" not in result

    def test_constant_series_returns_special_message(self) -> None:
        result = detect_seasonality([5.0] * 20, period=7)

        assert "constant" in result

    def test_returns_period_in_output(self) -> None:
        values = list(range(30))
        result = detect_seasonality(values, period=7)

        assert "period=7" in result

    def test_custom_period(self) -> None:
        result = detect_seasonality(list(range(60)), period=30)

        assert "period=30" in result
