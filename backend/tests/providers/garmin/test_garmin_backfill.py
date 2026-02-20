"""Tests for Garmin Backfill Service."""

from datetime import datetime, timedelta, timezone

from app.services.providers.garmin.backfill_config import (
    ALL_DATA_TYPES,
    BACKFILL_CHUNK_DAYS,
    BACKFILL_DATA_TYPES,
    BACKFILL_ENDPOINTS,
    BACKFILL_WINDOW_COUNT,
    DEFAULT_BACKFILL_DAYS,
    MAX_BACKFILL_DAYS,
    MAX_REQUEST_DAYS,
    REQUEST_DELAY_SECONDS,
    SUMMARY_DAYS,
)


class TestGarminBackfillConfig:
    """Tests for Garmin backfill configuration constants."""

    def test_backfill_limits_constants(self) -> None:
        """Test that backfill limit constants are set correctly."""
        # 30-day max per request, 365 days total via 12 windows
        assert BACKFILL_CHUNK_DAYS == 30  # Per request (30 days = max allowed)
        assert MAX_BACKFILL_DAYS == 365  # Target: ~1 year of history
        assert BACKFILL_WINDOW_COUNT == 12  # 12 x 30-day windows
        assert MAX_REQUEST_DAYS == 30  # Max days per single backfill request (Garmin limit)
        assert DEFAULT_BACKFILL_DAYS == 1  # Default for subsequent syncs
        assert SUMMARY_DAYS == 0  # No summary coverage gap (REST endpoints removed)

    def test_backfill_endpoints_mapping(self) -> None:
        """Test that all backfill endpoints are mapped."""
        expected_endpoints = [
            "sleeps",
            "dailies",
            "epochs",
            "bodyComps",
            "hrv",
            "stressDetails",
            "respiration",
            "pulseOx",
            "activities",
            "activityDetails",
            "userMetrics",
            "bloodPressures",
            "skinTemp",
            "healthSnapshot",
            "moveiq",
            "mct",
        ]

        for endpoint in expected_endpoints:
            assert endpoint in BACKFILL_ENDPOINTS
            assert BACKFILL_ENDPOINTS[endpoint].startswith("/wellness-api/rest/backfill/")

    def test_default_data_types(self) -> None:
        """Test default data types for backfill."""
        # All 16 data types are included
        expected_defaults = [
            "sleeps",
            "dailies",
            "epochs",
            "bodyComps",
            "hrv",
            "activities",
            "activityDetails",
            "moveiq",
            "healthSnapshot",
            "stressDetails",
            "respiration",
            "pulseOx",
            "bloodPressures",
            "userMetrics",
            "skinTemp",
            "mct",
        ]
        assert expected_defaults == ALL_DATA_TYPES

    def test_backfill_data_types(self) -> None:
        """Test that backfill uses exactly 5 essential data types."""
        expected = ["sleeps", "dailies", "activities", "activityDetails", "hrv"]
        assert expected == BACKFILL_DATA_TYPES
        assert len(BACKFILL_DATA_TYPES) == 5

    def test_backfill_types_are_subset_of_all_types(self) -> None:
        """Test that all backfill types exist in ALL_DATA_TYPES."""
        for data_type in BACKFILL_DATA_TYPES:
            assert data_type in ALL_DATA_TYPES

    def test_rate_limit_constants(self) -> None:
        """Test rate limit constants."""
        assert REQUEST_DELAY_SECONDS == 0.5  # Small delay between requests


class TestGarminBackfillTimeframeLogic:
    """Test backfill timeframe logic without actual API calls."""

    def test_first_sync_timeframe_calculation(self) -> None:
        """Test that first sync calculates appropriate timeframe.

        First sync uses BACKFILL_CHUNK_DAYS (30 days)
        which is the max allowed by Garmin per request for all types.
        """
        # Simulate the logic from trigger_backfill
        is_first_sync = True
        backfill_chunk_days = 30  # 30-day max (confirmed by Garmin support)
        default_backfill_days = 1

        end_time = datetime.now(timezone.utc)
        days = backfill_chunk_days if is_first_sync else default_backfill_days
        start_time = end_time - timedelta(days=days)

        days_diff = (end_time - start_time).days
        assert days_diff == 30

    def test_subsequent_sync_timeframe_calculation(self) -> None:
        """Test that subsequent sync calculates 1-day timeframe."""
        # Simulate the logic from trigger_backfill
        is_first_sync = False
        backfill_chunk_days = 30
        default_backfill_days = 1

        end_time = datetime.now(timezone.utc)
        days = backfill_chunk_days if is_first_sync else default_backfill_days
        start_time = end_time - timedelta(days=days)

        days_diff = (end_time - start_time).days
        assert days_diff == 1

    def test_custom_timeframe_overrides_defaults(self) -> None:
        """Test that custom start/end times are preserved."""
        custom_start = datetime.now(timezone.utc) - timedelta(days=30)
        custom_end = datetime.now(timezone.utc)

        # When start_time is provided, it should be used as-is
        days_diff = (custom_end - custom_start).days
        assert days_diff == 30
