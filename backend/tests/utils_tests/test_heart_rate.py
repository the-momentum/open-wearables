"""Tests for app.utils.heart_rate.

Covers the shared max-HR estimate (the single source of truth used by both the
daily summaries and the workout.created Edwards-zone webhook path) and the
Edwards HR-zone lower bounds.
"""

from datetime import date, datetime

from app.utils.heart_rate import (
    DEFAULT_MAX_HR,
    MIN_ESTIMATED_MAX_HR,
    edwards_zone_lower_bounds,
    estimate_max_hr,
)


class TestEstimateMaxHr:
    """Test suite for estimate_max_hr (220 - age, with fallback and floor)."""

    def test_normal_age(self) -> None:
        # Born 1990-01-01, referenced 2026-06-03 -> age 36 -> 220 - 36 = 184.
        ref = datetime(2026, 6, 3, 9, 0, 0)
        assert estimate_max_hr(date(1990, 1, 1), ref) == 184

    def test_age_hits_floor(self) -> None:
        # Age >= 120 (born 1900, referenced 2026 -> age 126) -> 220 - 126 = 94,
        # floored to MIN_ESTIMATED_MAX_HR.
        ref = datetime(2026, 6, 3, 9, 0, 0)
        assert estimate_max_hr(date(1900, 1, 1), ref) == MIN_ESTIMATED_MAX_HR
        assert MIN_ESTIMATED_MAX_HR == 100

    def test_null_birth_date_fallback(self) -> None:
        ref = datetime(2026, 6, 3, 9, 0, 0)
        assert estimate_max_hr(None, ref) == DEFAULT_MAX_HR
        assert DEFAULT_MAX_HR == 190

    def test_reference_date_birthday_boundary(self) -> None:
        # Birthday boundary: the day before the birthday is still the younger age,
        # the birthday itself counts as the older age.
        birth = date(1990, 6, 15)
        day_before = datetime(2026, 6, 14, 23, 59, 59)
        on_birthday = datetime(2026, 6, 15, 0, 0, 0)
        # Day before 36th birthday -> age 35 -> 185; on birthday -> age 36 -> 184.
        assert estimate_max_hr(birth, day_before) == 185
        assert estimate_max_hr(birth, on_birthday) == 184


class TestEdwardsZoneLowerBounds:
    """Test suite for edwards_zone_lower_bounds (five half-open zone lower bounds)."""

    def test_representative_max_hr_all_five_bounds(self) -> None:
        max_hr = 200
        bounds = edwards_zone_lower_bounds(max_hr)
        # 50/60/70/80/90% of 200.
        assert bounds == (100, 120, 140, 160, 180)
        assert len(bounds) == 5

    def test_zone_1_lower_bound_is_50_percent(self) -> None:
        max_hr = 200
        bounds = edwards_zone_lower_bounds(max_hr)
        assert bounds[0] == round(0.50 * max_hr)

    def test_zone_5_lower_bound_is_90_percent(self) -> None:
        max_hr = 200
        bounds = edwards_zone_lower_bounds(max_hr)
        assert bounds[4] == round(0.90 * max_hr)
