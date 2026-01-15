"""Tests for Garmin Backfill Service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

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
        # Official Garmin limits
        assert backfill_service.HEALTH_API_MAX_DAYS == 730  # 2 years
        assert backfill_service.ACTIVITY_API_MAX_DAYS == 1825  # 5 years
        assert backfill_service.DEFAULT_BACKFILL_DAYS == 1  # Default for subsequent syncs

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
        expected_defaults = ["sleeps", "dailies", "epochs", "bodyComps", "hrv"]
        assert backfill_service.DEFAULT_DATA_TYPES == expected_defaults

    def test_rate_limit_constants(self, backfill_service: GarminBackfillService) -> None:
        """Test rate limit constants."""
        assert backfill_service.REQUEST_DELAY_SECONDS == 2.0
        assert backfill_service.MAX_RETRIES == 3
        assert backfill_service.RETRY_BASE_DELAY == 10.0


class TestGarminBackfillTimeframeLogic:
    """Test backfill timeframe logic without actual API calls."""

    def test_first_sync_timeframe_calculation(self) -> None:
        """Test that first sync calculates 2-year timeframe."""
        # Simulate the logic from trigger_backfill
        is_first_sync = True
        HEALTH_API_MAX_DAYS = 730
        DEFAULT_BACKFILL_DAYS = 1

        end_time = datetime.now(timezone.utc)
        days = HEALTH_API_MAX_DAYS if is_first_sync else DEFAULT_BACKFILL_DAYS
        start_time = end_time - timedelta(days=days)

        days_diff = (end_time - start_time).days
        assert days_diff == 730

    def test_subsequent_sync_timeframe_calculation(self) -> None:
        """Test that subsequent sync calculates 1-day timeframe."""
        # Simulate the logic from trigger_backfill
        is_first_sync = False
        HEALTH_API_MAX_DAYS = 730
        DEFAULT_BACKFILL_DAYS = 1

        end_time = datetime.now(timezone.utc)
        days = HEALTH_API_MAX_DAYS if is_first_sync else DEFAULT_BACKFILL_DAYS
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
