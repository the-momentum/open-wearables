"""Tests for PolarData247Template Nightly Recharge normalization."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.services.providers.polar.data_247 import PolarData247Template
from app.services.providers.polar.strategy import PolarStrategy


@pytest.fixture
def data_247() -> PolarData247Template:
    return PolarStrategy().data_247


@pytest.fixture
def sample_polar_recharge_night() -> dict[str, Any]:
    """Single night from /v3/users/nightly-recharge — docs example + midnight-crossing samples.

    HH:MM transitions span 23:45 → 00:15 → 00:45 so the "bump +1 day on regress"
    helper logic is exercised by the default fixture.
    """
    return {
        "polar_user": "https://www.polaraccesslink/v3/users/1",
        "date": "2020-01-01",
        "heart_rate_avg": 70,
        "beat_to_beat_avg": 816,
        "heart_rate_variability_avg": 28,
        "breathing_rate_avg": 14.1,
        "nightly_recharge_status": 3,
        "ans_charge": -2,
        "ans_charge_status": 2,
        "hrv_samples": {"23:45": 14, "00:15": 15, "00:45": 16},
        "breathing_samples": {"23:50": 13.4, "00:10": 13.8},
    }


class TestNormalizeRecovery:
    def test_emits_all_five_sample_types_for_valid_night(
        self, data_247: PolarData247Template, sample_polar_recharge_night: dict
    ) -> None:
        """Fully-populated night → 3 hrv + 2 breathing + 3 single-point scores = 8 samples."""
        user_id = uuid4()
        samples = data_247.normalize_recovery(sample_polar_recharge_night, user_id)

        by_type: dict[SeriesType, list] = {}
        for s in samples:
            by_type.setdefault(s.series_type, []).append(s)

        assert len(by_type[SeriesType.heart_rate_variability_rmssd]) == 3
        assert len(by_type[SeriesType.respiratory_rate]) == 2
        assert len(by_type[SeriesType.polar_nightly_recharge_status]) == 1
        assert len(by_type[SeriesType.polar_ans_charge]) == 1
        assert len(by_type[SeriesType.polar_ans_charge_status]) == 1

        for s in samples:
            assert s.source == "polar"
            assert s.user_id == user_id

    def test_skips_night_with_missing_date(
        self, data_247: PolarData247Template, sample_polar_recharge_night: dict
    ) -> None:
        sample_polar_recharge_night.pop("date")
        user_id = uuid4()
        samples = data_247.normalize_recovery(sample_polar_recharge_night, user_id)
        assert samples == []

    def test_skips_invalid_hhmm_keys_but_keeps_valid_samples(
        self, data_247: PolarData247Template, sample_polar_recharge_night: dict
    ) -> None:
        sample_polar_recharge_night["hrv_samples"] = {
            "00:15": 14,
            "not-a-time": 999,
            "25:99": 888,
            "01:00": 15,
        }
        user_id = uuid4()
        samples = data_247.normalize_recovery(sample_polar_recharge_night, user_id)
        hrv = [s for s in samples if s.series_type == SeriesType.heart_rate_variability_rmssd]
        assert len(hrv) == 2
        assert {float(s.value) for s in hrv} == {14.0, 15.0}

    def test_handles_absent_samples_dicts(
        self, data_247: PolarData247Template, sample_polar_recharge_night: dict
    ) -> None:
        """Night with only scores (no hrv/breathing samples) emits just the 3 single-points."""
        sample_polar_recharge_night.pop("hrv_samples")
        sample_polar_recharge_night.pop("breathing_samples")
        user_id = uuid4()
        samples = data_247.normalize_recovery(sample_polar_recharge_night, user_id)
        assert len(samples) == 3
        assert {s.series_type for s in samples} == {
            SeriesType.polar_nightly_recharge_status,
            SeriesType.polar_ans_charge,
            SeriesType.polar_ans_charge_status,
        }

    def test_ans_charge_signed_values_preserved(
        self, data_247: PolarData247Template, sample_polar_recharge_night: dict
    ) -> None:
        user_id = uuid4()
        sample_polar_recharge_night["ans_charge"] = -7
        samples = data_247.normalize_recovery(sample_polar_recharge_night, user_id)
        ans = next(s for s in samples if s.series_type == SeriesType.polar_ans_charge)
        assert ans.value == Decimal("-7")

        sample_polar_recharge_night["ans_charge"] = 7
        samples = data_247.normalize_recovery(sample_polar_recharge_night, user_id)
        ans = next(s for s in samples if s.series_type == SeriesType.polar_ans_charge)
        assert ans.value == Decimal("7")

    def test_score_timestamps_anchor_to_date_midnight_utc(
        self, data_247: PolarData247Template, sample_polar_recharge_night: dict
    ) -> None:
        user_id = uuid4()
        samples = data_247.normalize_recovery(sample_polar_recharge_night, user_id)
        expected = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
        scores = [
            s for s in samples
            if s.series_type in (
                SeriesType.polar_nightly_recharge_status,
                SeriesType.polar_ans_charge,
                SeriesType.polar_ans_charge_status,
            )
        ]
        assert len(scores) == 3
        for s in scores:
            assert s.recorded_at == expected

    def test_hrv_sample_timestamps_bump_across_midnight(
        self, data_247: PolarData247Template, sample_polar_recharge_night: dict
    ) -> None:
        """hrv_samples go 23:45 (same day) → 00:15, 00:45 (next day) via bump-on-regress."""
        user_id = uuid4()
        samples = data_247.normalize_recovery(sample_polar_recharge_night, user_id)
        hrv = sorted(
            (s for s in samples if s.series_type == SeriesType.heart_rate_variability_rmssd),
            key=lambda s: s.recorded_at,
        )
        assert len(hrv) == 3
        assert hrv[0].recorded_at == datetime(2020, 1, 1, 23, 45, tzinfo=timezone.utc)
        assert hrv[1].recorded_at == datetime(2020, 1, 2, 0, 15, tzinfo=timezone.utc)
        assert hrv[2].recorded_at == datetime(2020, 1, 2, 0, 45, tzinfo=timezone.utc)

    def test_breathing_sample_float_values_preserved(
        self, data_247: PolarData247Template, sample_polar_recharge_night: dict
    ) -> None:
        user_id = uuid4()
        samples = data_247.normalize_recovery(sample_polar_recharge_night, user_id)
        breathing = sorted(
            (s for s in samples if s.series_type == SeriesType.respiratory_rate),
            key=lambda s: s.recorded_at,
        )
        assert len(breathing) == 2
        assert {float(b.value) for b in breathing} == {13.4, 13.8}
