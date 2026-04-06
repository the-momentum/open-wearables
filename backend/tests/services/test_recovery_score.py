"""
Unit tests for the recovery score calculation module.

Tests cover:
- Log transformation of HRV metrics
- Z-score to 0-100 mapping (HRV and RHR directions)
- Per-component score calculation (baseline requirements, z-score math)
- Master recovery score: full data, missing components, gatekeeper
"""

import math

import pytest

from app.services.recovery_score import (
    RECOVERY_PHYSIO_CONFIG,
    _transform_metric,
    _z_score_to_0_100,
    calculate_master_recovery_score,
    calculate_physio_score,
)


class TestTransformMetric:
    def test_hrv_rmssd_applies_log(self) -> None:
        assert _transform_metric(45.0, "rmssd") == pytest.approx(math.log(45.0))

    def test_hrv_sdnn_applies_log(self) -> None:
        assert _transform_metric(45.0, "sdnn") == pytest.approx(math.log(45.0))

    def test_rhr_no_transform(self) -> None:
        assert _transform_metric(60.0, "rhr") == 60.0

    def test_zero_value_returns_zero(self) -> None:
        assert _transform_metric(0.0, "rmssd") == 0.0

    def test_negative_value_returns_zero(self) -> None:
        assert _transform_metric(-1.0, "sdnn") == 0.0


class TestZScoreTo0100:
    """Test the empirical-rule scaling: Z=0→70, Z=+2→100, Z=-2→0."""

    cfg = RECOVERY_PHYSIO_CONFIG

    def test_zero_z_score_returns_neutral(self) -> None:
        assert _z_score_to_0_100(0.0, is_hrv=True, config=self.cfg) == 70

    def test_max_z_score_hrv_returns_100(self) -> None:
        assert _z_score_to_0_100(2.0, is_hrv=True, config=self.cfg) == 100

    def test_min_z_score_hrv_returns_0(self) -> None:
        assert _z_score_to_0_100(-2.0, is_hrv=True, config=self.cfg) == 0

    def test_rhr_inverts_sign(self) -> None:
        # Higher RHR (positive Z) → worse recovery → score below neutral
        assert _z_score_to_0_100(2.0, is_hrv=False, config=self.cfg) == 0
        assert _z_score_to_0_100(-2.0, is_hrv=False, config=self.cfg) == 100

    def test_clamped_above_100(self) -> None:
        assert _z_score_to_0_100(10.0, is_hrv=True, config=self.cfg) == 100

    def test_clamped_below_0(self) -> None:
        assert _z_score_to_0_100(-10.0, is_hrv=True, config=self.cfg) == 0


class TestCalculatePhysioScore:
    HISTORY = [45.0, 42.0, 48.0, 46.0, 44.0]

    def test_returns_neutral_when_insufficient_baseline(self) -> None:
        result = calculate_physio_score(45.0, [44.0, 45.0], "sdnn")
        assert result["score"] == 70
        assert result["status"] == "calculating_baseline"
        assert result["z_score"] == 0.0

    def test_active_status_when_enough_history(self) -> None:
        result = calculate_physio_score(45.0, self.HISTORY, "sdnn")
        assert result["status"] == "active"

    def test_median_value_scores_near_neutral(self) -> None:
        import statistics

        median_val = statistics.median(self.HISTORY)
        result = calculate_physio_score(median_val, self.HISTORY, "sdnn")
        assert 60 <= result["score"] <= 80

    def test_high_hrv_scores_above_neutral(self) -> None:
        result = calculate_physio_score(55.0, self.HISTORY, "sdnn")
        assert result["score"] > 70

    def test_low_hrv_scores_below_neutral(self) -> None:
        result = calculate_physio_score(35.0, self.HISTORY, "sdnn")
        assert result["score"] < 70

    def test_high_rhr_scores_below_neutral(self) -> None:
        # Higher RHR = worse recovery
        rhr_history = [60.0, 59.0, 61.0, 60.0, 58.0]
        result = calculate_physio_score(70.0, rhr_history, "rhr")
        assert result["score"] < 70

    def test_low_rhr_scores_above_neutral(self) -> None:
        rhr_history = [60.0, 59.0, 61.0, 60.0, 58.0]
        result = calculate_physio_score(50.0, rhr_history, "rhr")
        assert result["score"] > 70

    def test_flat_baseline_returns_neutral(self) -> None:
        # std_dev == 0 → z_score == 0 → neutral
        result = calculate_physio_score(50.0, [50.0, 50.0, 50.0, 50.0, 50.0], "rhr")
        assert result["score"] == 70

    def test_z_score_is_rounded_to_2_dp(self) -> None:
        result = calculate_physio_score(45.0, self.HISTORY, "sdnn")
        assert result["z_score"] == round(result["z_score"], 2)


class TestCalculateMasterRecoveryScore:
    HRV_HISTORY = [45.0, 42.0, 48.0, 46.0, 44.0, 41.0, 47.0, 45.0, 43.0, 46.0]
    RHR_HISTORY = [60.0, 59.0, 61.0, 60.0, 58.0, 62.0, 59.0, 60.0, 61.0, 59.0]

    def test_full_data_returns_success(self) -> None:
        result = calculate_master_recovery_score(
            user_id="u1",
            daily_sleep_score=70,
            daily_hrv=44.5,
            historical_hrv=self.HRV_HISTORY,
            daily_rhr=59.5,
            historical_rhr=self.RHR_HISTORY,
        )
        assert result["status"] == "success"
        assert result["recovery_score"] is not None
        assert 0 <= result["recovery_score"] <= 100

    def test_average_day_scores_near_70(self) -> None:
        result = calculate_master_recovery_score(
            user_id="u1",
            daily_sleep_score=70,
            daily_hrv=44.5,
            historical_hrv=self.HRV_HISTORY,
            daily_rhr=59.5,
            historical_rhr=self.RHR_HISTORY,
        )
        assert 60 <= result["recovery_score"] <= 80

    def test_full_weights_sum_to_1(self) -> None:
        result = calculate_master_recovery_score(
            user_id="u1",
            daily_sleep_score=70,
            daily_hrv=44.5,
            historical_hrv=self.HRV_HISTORY,
            daily_rhr=59.5,
            historical_rhr=self.RHR_HISTORY,
        )
        total = sum(result["applied_weights"].values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_missing_hrv_redistributes_weights(self) -> None:
        result = calculate_master_recovery_score(
            user_id="u1",
            daily_sleep_score=85,
            daily_hrv=None,
            daily_rhr=55.0,
            historical_rhr=self.RHR_HISTORY,
        )
        assert result["status"] == "success"
        assert "hrv_score" not in result["component_scores"]
        # Sleep and RHR should each get 50% (0.30 / 0.60, 0.30 / 0.60)
        assert result["applied_weights"]["sleep_score"] == pytest.approx(0.5, abs=0.01)
        assert result["applied_weights"]["rhr_score"] == pytest.approx(0.5, abs=0.01)

    def test_missing_rhr_redistributes_weights(self) -> None:
        result = calculate_master_recovery_score(
            user_id="u1",
            daily_sleep_score=70,
            daily_hrv=44.5,
            historical_hrv=self.HRV_HISTORY,
            daily_rhr=None,
        )
        assert result["status"] == "success"
        assert "rhr_score" not in result["component_scores"]
        # HRV gets 40/70 ≈ 0.57, sleep gets 30/70 ≈ 0.43
        assert result["applied_weights"]["hrv_score"] == pytest.approx(0.57, abs=0.01)
        assert result["applied_weights"]["sleep_score"] == pytest.approx(0.43, abs=0.01)

    def test_missing_sleep_uses_physio_only(self) -> None:
        result = calculate_master_recovery_score(
            user_id="u1",
            daily_sleep_score=None,
            daily_hrv=44.5,
            historical_hrv=self.HRV_HISTORY,
            daily_rhr=59.5,
            historical_rhr=self.RHR_HISTORY,
        )
        assert result["status"] == "success"
        assert "sleep_score" not in result["component_scores"]
        # HRV gets 40/70 ≈ 0.57, RHR gets 30/70 ≈ 0.43
        assert result["applied_weights"]["hrv_score"] == pytest.approx(0.57, abs=0.01)

    def test_no_physio_data_returns_insufficient(self) -> None:
        result = calculate_master_recovery_score(
            user_id="u1",
            daily_sleep_score=95,
            daily_hrv=None,
            daily_rhr=None,
        )
        assert result["status"] == "insufficient_data"
        assert result["recovery_score"] is None

    def test_no_data_at_all_returns_insufficient(self) -> None:
        result = calculate_master_recovery_score(user_id="u1")
        assert result["status"] == "insufficient_data"
        assert result["recovery_score"] is None

    def test_component_scores_present_in_result(self) -> None:
        result = calculate_master_recovery_score(
            user_id="u1",
            daily_sleep_score=70,
            daily_hrv=44.5,
            historical_hrv=self.HRV_HISTORY,
            daily_rhr=59.5,
            historical_rhr=self.RHR_HISTORY,
        )
        assert "hrv_score" in result["component_scores"]
        assert "rhr_score" in result["component_scores"]
        assert "sleep_score" in result["component_scores"]

    def test_score_is_integer(self) -> None:
        result = calculate_master_recovery_score(
            user_id="u1",
            daily_hrv=44.5,
            historical_hrv=self.HRV_HISTORY,
            daily_rhr=59.5,
            historical_rhr=self.RHR_HISTORY,
        )
        assert isinstance(result["recovery_score"], int)
