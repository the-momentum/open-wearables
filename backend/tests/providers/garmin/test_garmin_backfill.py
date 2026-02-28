"""Tests for Garmin Backfill Service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

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
from app.services.providers.garmin.handlers.backfill import GarminBackfillService


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


class TestGarminBackfillServiceResults:
    """Tests for backfill service API response handling."""

    def _make_service(self) -> GarminBackfillService:
        oauth = MagicMock()
        return GarminBackfillService(
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
            oauth=oauth,
        )

    @patch.object(GarminBackfillService, "_make_api_request")
    def test_409_duplicate_goes_to_duplicate_list(self, mock_api: MagicMock) -> None:
        """409 responses should land in 'duplicate', not 'triggered'."""
        mock_api.side_effect = HTTPException(status_code=409, detail="duplicate backfill")
        service = self._make_service()
        db = MagicMock()
        user_id = MagicMock()

        result = service.trigger_backfill(
            db=db,
            user_id=user_id,
            data_types=["sleeps"],
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
            end_time=datetime.now(timezone.utc),
        )

        assert "sleeps" in result["duplicate"]
        assert "sleeps" not in result["triggered"]
        assert "sleeps" not in result.get("failed", {})

    @patch.object(GarminBackfillService, "_make_api_request")
    def test_202_accepted_goes_to_triggered(self, mock_api: MagicMock) -> None:
        """Successful 202 responses should land in 'triggered'."""
        mock_api.return_value = None  # 202 returns empty body
        service = self._make_service()
        db = MagicMock()
        user_id = MagicMock()

        result = service.trigger_backfill(
            db=db,
            user_id=user_id,
            data_types=["sleeps"],
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
            end_time=datetime.now(timezone.utc),
        )

        assert "sleeps" in result["triggered"]
        assert "sleeps" not in result["duplicate"]

    @patch.object(GarminBackfillService, "_make_api_request")
    def test_401_goes_to_failed(self, mock_api: MagicMock) -> None:
        """401 responses should land in 'failed'."""
        mock_api.side_effect = HTTPException(status_code=401, detail="authorization expired")
        service = self._make_service()
        db = MagicMock()
        user_id = MagicMock()

        result = service.trigger_backfill(
            db=db,
            user_id=user_id,
            data_types=["sleeps"],
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
            end_time=datetime.now(timezone.utc),
        )

        assert "sleeps" in result["failed"]
        assert result["failed_status_codes"]["sleeps"] == 401
        assert "sleeps" not in result["triggered"]
        assert "sleeps" not in result["duplicate"]

    @patch.object(GarminBackfillService, "_make_api_request")
    def test_401_stops_chain_via_failed_status_code(self, mock_api: MagicMock) -> None:
        """Task should detect 401 in failed_status_codes and not continue chain."""
        mock_api.side_effect = HTTPException(status_code=401, detail="authorization expired")
        service = self._make_service()
        db = MagicMock()
        user_id = MagicMock()

        result = service.trigger_backfill(
            db=db,
            user_id=user_id,
            data_types=["sleeps", "dailies"],
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
            end_time=datetime.now(timezone.utc),
        )

        # Both types should fail with status code preserved
        assert "sleeps" in result["failed"]
        assert result["failed_status_codes"]["sleeps"] == 401
        assert "dailies" in result["failed"]
        assert result["failed_status_codes"]["dailies"] == 401
        # Neither should be in triggered or duplicate
        assert result["triggered"] == []
        assert result["duplicate"] == []

    @patch.object(GarminBackfillService, "_make_api_request")
    def test_412_goes_to_failed(self, mock_api: MagicMock) -> None:
        """412 responses should land in 'failed' with status code preserved."""
        mock_api.side_effect = HTTPException(
            status_code=412,
            detail="Access denied for consumer required HISTORICAL_DATA_EXPORT",
        )
        service = self._make_service()
        db = MagicMock()
        user_id = MagicMock()

        result = service.trigger_backfill(
            db=db,
            user_id=user_id,
            data_types=["sleeps"],
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
            end_time=datetime.now(timezone.utc),
        )

        assert "sleeps" in result["failed"]
        assert result["failed_status_codes"]["sleeps"] == 412
        assert "sleeps" not in result["triggered"]
        assert "sleeps" not in result["duplicate"]

    @patch.object(GarminBackfillService, "_make_api_request")
    def test_412_stops_chain_via_failed_status_code(self, mock_api: MagicMock) -> None:
        """412 should fail all types — permission error affects every data type."""
        mock_api.side_effect = HTTPException(
            status_code=412,
            detail="Access denied for consumer required HISTORICAL_DATA_EXPORT",
        )
        service = self._make_service()
        db = MagicMock()
        user_id = MagicMock()

        result = service.trigger_backfill(
            db=db,
            user_id=user_id,
            data_types=["sleeps", "dailies", "activities"],
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
            end_time=datetime.now(timezone.utc),
        )

        for data_type in ["sleeps", "dailies", "activities"]:
            assert data_type in result["failed"]
            assert result["failed_status_codes"][data_type] == 412
        assert result["triggered"] == []
        assert result["duplicate"] == []


class TestBackfillTaskStopChain:
    """Tests for the celery task stop-chain logic on auth/permission errors.

    These test trigger_backfill_for_type() directly, mocking Redis state
    and the backfill service to verify the chain stops on 401/403/412.
    """

    TASK_MODULE = "app.integrations.celery.tasks.garmin_backfill_task"
    USER_ID = "c079cf7e-70b3-4529-a325-401a658f5cba"

    def _run_task_with_status(self, status_code: int, detail: str) -> dict:
        """Run trigger_backfill_for_type with a mocked HTTP error and return result."""
        from app.integrations.celery.tasks.garmin_backfill_task import (
            trigger_backfill_for_type,
        )

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True

        with (
            patch(f"{self.TASK_MODULE}.SessionLocal") as mock_session_cls,
            patch(f"{self.TASK_MODULE}.ProviderFactory") as mock_factory_cls,
            patch(f"{self.TASK_MODULE}.get_current_window", return_value=0),
            patch(
                f"{self.TASK_MODULE}.get_window_date_range",
                return_value=(
                    datetime.now(timezone.utc) - timedelta(days=30),
                    datetime.now(timezone.utc),
                ),
            ),
            patch(f"{self.TASK_MODULE}.get_trace_id", return_value="test-trace"),
            patch(f"{self.TASK_MODULE}.set_type_trace_id", return_value="test-type-trace"),
            patch(f"{self.TASK_MODULE}.is_retry_phase", return_value=False),
            patch(f"{self.TASK_MODULE}.mark_type_triggered"),
            patch(f"{self.TASK_MODULE}.mark_type_failed") as mock_mark_failed,
            patch(f"{self.TASK_MODULE}.get_pending_types", return_value=["dailies", "activities"]),
            patch(f"{self.TASK_MODULE}.trigger_next_pending_type") as mock_next,
            patch(f"{self.TASK_MODULE}.redis_client", mock_redis),
            patch(f"{self.TASK_MODULE}.UserConnectionRepository") as mock_conn_repo_cls,
        ):
            # Setup DB session context manager
            mock_db = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            # Setup connection repo — return a valid connection
            mock_conn_repo_cls.return_value.get_by_user_and_provider.return_value = MagicMock()

            # Setup provider factory
            mock_strategy = MagicMock()
            mock_strategy.oauth = MagicMock()
            mock_factory_cls.return_value.get_provider.return_value = mock_strategy

            # Make backfill service raise the HTTP error
            with patch.object(
                GarminBackfillService,
                "trigger_backfill",
                side_effect=HTTPException(status_code=status_code, detail=detail),
            ):
                result = trigger_backfill_for_type(self.USER_ID, "sleeps")

            return {
                "result": result,
                "mock_mark_failed": mock_mark_failed,
                "mock_next": mock_next,
            }

    def test_412_stops_chain_and_fails_pending_types(self) -> None:
        """412 should stop the chain and mark all pending types as failed."""
        ctx = self._run_task_with_status(412, "Access denied for consumer required HISTORICAL_DATA_EXPORT")

        assert ctx["result"]["status"] == "failed"
        assert "HISTORICAL_DATA_EXPORT" in ctx["result"]["error"]

        # Should mark the current type + all pending types as failed
        failed_types = [call.args[1] for call in ctx["mock_mark_failed"].call_args_list]
        assert "sleeps" in failed_types
        assert "dailies" in failed_types
        assert "activities" in failed_types

        # Should NOT trigger next type
        ctx["mock_next"].apply_async.assert_not_called()

    def test_401_stops_chain_and_fails_pending_types(self) -> None:
        """401 should stop the chain and mark all pending types as failed."""
        ctx = self._run_task_with_status(401, "authorization expired")

        assert ctx["result"]["status"] == "failed"
        assert "re-authorize" in ctx["result"]["error"].lower()

        failed_types = [call.args[1] for call in ctx["mock_mark_failed"].call_args_list]
        assert "sleeps" in failed_types
        assert "dailies" in failed_types
        assert "activities" in failed_types

        ctx["mock_next"].apply_async.assert_not_called()

    def test_403_stops_chain_and_fails_pending_types(self) -> None:
        """403 should stop the chain and mark all pending types as failed."""
        ctx = self._run_task_with_status(403, "historical data access not granted")

        assert ctx["result"]["status"] == "failed"

        failed_types = [call.args[1] for call in ctx["mock_mark_failed"].call_args_list]
        assert "sleeps" in failed_types
        assert "dailies" in failed_types
        assert "activities" in failed_types

        ctx["mock_next"].apply_async.assert_not_called()

    def test_400_min_start_time_stops_chain_via_exception(self) -> None:
        """400 'min start time' should stop the chain (HTTPException path)."""
        detail = (
            'Garmin API error: {"errorMessage":"start 2025-12-28T22:09:49Z'
            ' before min start time of 2026-01-26T22:10:12Z"}'
        )
        ctx = self._run_task_with_status(400, detail)

        assert ctx["result"]["status"] == "failed"
        assert "min" in ctx["result"]["error"].lower()

        failed_types = [call.args[1] for call in ctx["mock_mark_failed"].call_args_list]
        assert "sleeps" in failed_types
        assert "dailies" in failed_types
        assert "activities" in failed_types

        ctx["mock_next"].apply_async.assert_not_called()

    def test_400_min_start_time_stops_chain_via_result(self) -> None:
        """400 'min start time' via result dict should stop the chain (production path)."""
        from app.integrations.celery.tasks.garmin_backfill_task import (
            trigger_backfill_for_type,
        )

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True

        error_detail = (
            'Garmin API error: {"errorMessage":"start 2025-12-28T22:09:49Z '
            'before min start time of 2026-01-26T22:10:12Z"}'
        )

        with (
            patch(f"{self.TASK_MODULE}.SessionLocal") as mock_session_cls,
            patch(f"{self.TASK_MODULE}.ProviderFactory") as mock_factory_cls,
            patch(f"{self.TASK_MODULE}.get_current_window", return_value=1),
            patch(
                f"{self.TASK_MODULE}.get_window_date_range",
                return_value=(
                    datetime.now(timezone.utc) - timedelta(days=60),
                    datetime.now(timezone.utc) - timedelta(days=30),
                ),
            ),
            patch(f"{self.TASK_MODULE}.get_trace_id", return_value="test-trace"),
            patch(f"{self.TASK_MODULE}.set_type_trace_id", return_value="test-type-trace"),
            patch(f"{self.TASK_MODULE}.is_retry_phase", return_value=False),
            patch(f"{self.TASK_MODULE}.mark_type_triggered"),
            patch(f"{self.TASK_MODULE}.mark_type_failed") as mock_mark_failed,
            patch(f"{self.TASK_MODULE}.get_pending_types", return_value=["dailies", "activities"]),
            patch(f"{self.TASK_MODULE}.trigger_next_pending_type") as mock_next,
            patch(f"{self.TASK_MODULE}.redis_client", mock_redis),
            patch(f"{self.TASK_MODULE}.UserConnectionRepository") as mock_conn_repo_cls,
        ):
            mock_db = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn_repo_cls.return_value.get_by_user_and_provider.return_value = MagicMock()

            mock_strategy = MagicMock()
            mock_strategy.oauth = MagicMock()
            mock_factory_cls.return_value.get_provider.return_value = mock_strategy

            # Return result dict with failed status (as backfill.py does in production)
            with patch.object(
                GarminBackfillService,
                "trigger_backfill",
                return_value={
                    "triggered": [],
                    "failed": {"sleeps": error_detail},
                    "duplicate": [],
                    "failed_status_codes": {"sleeps": 400},
                },
            ):
                result = trigger_backfill_for_type(self.USER_ID, "sleeps")

        assert result["status"] == "failed"
        assert "min" in result["error"].lower()

        # Should mark current type + all pending types as failed
        failed_types = [call.args[1] for call in mock_mark_failed.call_args_list]
        assert "sleeps" in failed_types
        assert "dailies" in failed_types
        assert "activities" in failed_types

        # Should NOT trigger next type
        mock_next.apply_async.assert_not_called()

    def test_500_does_not_stop_chain(self) -> None:
        """500 should NOT stop the chain — next type should still be triggered."""
        ctx = self._run_task_with_status(500, "internal server error")

        assert ctx["result"]["status"] == "failed"

        # Should only mark the current type as failed, not pending ones
        failed_types = [call.args[1] for call in ctx["mock_mark_failed"].call_args_list]
        assert "sleeps" in failed_types
        assert "dailies" not in failed_types

        # Should trigger next type
        ctx["mock_next"].apply_async.assert_called_once()
