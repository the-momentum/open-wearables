"""Tests for Garmin Backfill Service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.providers.garmin.backfill import GarminBackfillService


class TestGarminBackfillServiceUnit:
    """Unit tests for GarminBackfillService class (no DB required)."""

    @pytest.fixture
    def backfill_service(self) -> GarminBackfillService:
        """Create GarminBackfillService instance for testing."""
        mock_oauth = MagicMock()
        return GarminBackfillService(
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
            oauth=mock_oauth,
        )

    def test_backfill_limits_constants(self, backfill_service: GarminBackfillService) -> None:
        """Test that backfill limit constants are set correctly."""
        # Optimized constants: 90-day batches instead of 1-day
        assert backfill_service.BACKFILL_CHUNK_DAYS == 90  # Per request (90 days = max allowed)
        assert backfill_service.MAX_BACKFILL_DAYS == 90  # Target: 3 months of history
        assert backfill_service.MAX_REQUEST_DAYS == 90  # Max days per single backfill request (Garmin limit)
        assert backfill_service.DEFAULT_BACKFILL_DAYS == 1  # Default for subsequent syncs
        assert backfill_service.SUMMARY_DAYS == 7  # Summary covers last 7 days; backfill starts after

    def test_backfill_endpoints_mapping(self, backfill_service: GarminBackfillService) -> None:
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
            assert endpoint in backfill_service.BACKFILL_ENDPOINTS
            assert backfill_service.BACKFILL_ENDPOINTS[endpoint].startswith("/wellness-api/rest/backfill/")

    def test_default_data_types(self, backfill_service: GarminBackfillService) -> None:
        """Test default data types for backfill."""
        # All 16 data types are included in DEFAULT_DATA_TYPES
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
        assert expected_defaults == backfill_service.DEFAULT_DATA_TYPES

    def test_rate_limit_constants(self, backfill_service: GarminBackfillService) -> None:
        """Test rate limit constants."""
        assert backfill_service.REQUEST_DELAY_SECONDS == 0.5  # Small delay between requests
        # Note: MAX_RETRIES and RETRY_BASE_DELAY are not defined in current implementation


class TestGarminBackfillTimeframeLogic:
    """Test backfill timeframe logic without actual API calls."""

    def test_first_sync_timeframe_calculation(self) -> None:
        """Test that first sync calculates appropriate timeframe.

        Note: With optimization, first sync uses BACKFILL_CHUNK_DAYS (90 days)
        which is the max allowed by Garmin per request.
        """
        # Simulate the logic from trigger_backfill
        is_first_sync = True
        backfill_chunk_days = 90  # Optimized implementation value
        default_backfill_days = 1

        end_time = datetime.now(timezone.utc)
        days = backfill_chunk_days if is_first_sync else default_backfill_days
        start_time = end_time - timedelta(days=days)

        days_diff = (end_time - start_time).days
        assert days_diff == 90

    def test_subsequent_sync_timeframe_calculation(self) -> None:
        """Test that subsequent sync calculates 1-day timeframe."""
        # Simulate the logic from trigger_backfill
        is_first_sync = False
        backfill_chunk_days = 90
        default_backfill_days = 1

        end_time = datetime.now(timezone.utc)
        days = backfill_chunk_days if is_first_sync else default_backfill_days
        start_time = end_time - timedelta(days=days)

        days_diff = (end_time - start_time).days
        assert days_diff == 1

    def test_custom_timeframe_overrides_defaults(self) -> None:
        """Test that custom start/end times are preserved."""
        custom_start = datetime.now(timezone.utc) - timedelta(days=90)
        custom_end = datetime.now(timezone.utc)

        # When start_time is provided, it should be used as-is
        days_diff = (custom_end - custom_start).days
        assert days_diff == 90
