"""
Tests for start_historical_sync on BaseProviderStrategy.

Tests cover:
- Default pull-based implementation (Oura, Whoop, etc.)
- Garmin override (webhook backfill)
- Providers that don't support historical sync (Apple, Google, Samsung)
- HistoricalSyncResult dataclass contract
"""

from datetime import datetime
from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from celery.result import AsyncResult
from pytest_mock import MockerFixture

from app.services.providers.apple.strategy import AppleStrategy
from app.services.providers.base_strategy import HistoricalSyncResult
from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.oura.strategy import OuraStrategy
from app.services.providers.polar.strategy import PolarStrategy
from app.services.providers.whoop.strategy import WhoopStrategy
from app.utils.exceptions import UnsupportedProviderError


class TestHistoricalSyncResult:
    """Tests for the HistoricalSyncResult dataclass."""

    def test_all_fields_present(self) -> None:
        result = HistoricalSyncResult(
            task_id="abc-123",
            method="pull_api",
            message="Synced",
            days=90,
            start_date="2026-01-01T00:00:00+00:00",
            end_date="2026-04-01T00:00:00+00:00",
        )
        assert result.task_id == "abc-123"
        assert result.method == "pull_api"
        assert result.message == "Synced"
        assert result.days == 90
        assert result.start_date is not None
        assert result.end_date is not None

    def test_optional_fields_default_to_none(self) -> None:
        result = HistoricalSyncResult(
            task_id="abc-123",
            method="webhook_backfill",
            message="Started",
            days=None,
        )
        assert result.start_date is None
        assert result.end_date is None


class TestPullBasedHistoricalSync:
    """Tests for the default start_historical_sync (pull-based providers)."""

    def test_oura_dispatches_pull_sync(self, mocker: MockerFixture) -> None:
        """Pull-based provider should dispatch sync_vendor_data with is_historical=True."""
        mock_celery = mocker.patch("app.services.providers.base_strategy.celery_app", autospec=True)
        mock_celery.send_task.return_value = create_autospec(AsyncResult, instance=True, id="task-oura-123")
        user_id = uuid4()

        result = OuraStrategy().start_historical_sync(user_id, days=90)

        assert isinstance(result, HistoricalSyncResult)
        assert result.task_id == "task-oura-123"
        assert result.method == "pull_api"
        assert result.days == 90
        assert result.start_date is not None
        assert result.end_date is not None
        mock_celery.send_task.assert_called_once()
        call_kwargs = mock_celery.send_task.call_args[1]["kwargs"]
        assert call_kwargs["user_id"] == str(user_id)
        assert call_kwargs["providers"] == ["oura"]
        assert call_kwargs["is_historical"] is True

    def test_whoop_dispatches_pull_sync(self, mocker: MockerFixture) -> None:
        """Another pull-based provider should also use the default implementation."""
        mock_celery = mocker.patch("app.services.providers.base_strategy.celery_app", autospec=True)
        mock_celery.send_task.return_value = create_autospec(AsyncResult, instance=True, id="task-whoop-456")
        user_id = uuid4()

        result = WhoopStrategy().start_historical_sync(user_id, days=30)

        assert result.task_id == "task-whoop-456"
        assert result.method == "pull_api"
        assert result.days == 30
        call_kwargs = mock_celery.send_task.call_args[1]["kwargs"]
        assert call_kwargs["providers"] == ["whoop"]

    def test_respects_days_parameter(self, mocker: MockerFixture) -> None:
        """The date range should span the requested number of days."""
        mock_celery = mocker.patch("app.services.providers.base_strategy.celery_app", autospec=True)
        mock_celery.send_task.return_value = create_autospec(AsyncResult, instance=True, id="task-123")
        user_id = uuid4()

        result = OuraStrategy().start_historical_sync(user_id, days=7)

        assert result.days == 7
        start = datetime.fromisoformat(result.start_date)
        end = datetime.fromisoformat(result.end_date)
        assert (end - start).days == 7

    def test_caps_days_at_max_historical_days(self, mocker: MockerFixture) -> None:
        mock_celery = mocker.patch("app.services.providers.base_strategy.celery_app", autospec=True)
        mock_celery.send_task.return_value = create_autospec(AsyncResult, instance=True, id="task-123")

        result = PolarStrategy().start_historical_sync(uuid4(), days=730)

        assert result.days == 365
        start = datetime.fromisoformat(result.start_date)
        end = datetime.fromisoformat(result.end_date)
        assert (end - start).days == 365


class TestGarminHistoricalSync:
    """Tests for Garmin's overridden start_historical_sync."""

    def test_dispatches_backfill_task(self, mocker: MockerFixture) -> None:
        """Garmin should dispatch start_garmin_full_backfill, not sync_vendor_data."""
        mock_backfill = mocker.patch("app.services.providers.garmin.strategy.start_garmin_full_backfill", autospec=True)
        mock_backfill.delay.return_value = create_autospec(AsyncResult, instance=True, id="task-garmin-789")
        user_id = uuid4()

        result = GarminStrategy().start_historical_sync(user_id, days=90)

        assert isinstance(result, HistoricalSyncResult)
        assert result.task_id == "task-garmin-789"
        assert result.method == "webhook_backfill"
        assert result.days == 30
        start = datetime.fromisoformat(result.start_date)
        end = datetime.fromisoformat(result.end_date)
        assert (end - start).days == 30
        mock_backfill.delay.assert_called_once_with(str(user_id))

    def test_ignores_days_parameter(self, mocker: MockerFixture) -> None:
        """Garmin always uses its own 30-day limit regardless of days param."""
        mock_backfill = mocker.patch("app.services.providers.garmin.strategy.start_garmin_full_backfill", autospec=True)
        mock_backfill.delay.return_value = create_autospec(AsyncResult, instance=True, id="task-123")
        user_id = uuid4()

        result = GarminStrategy().start_historical_sync(user_id, days=365)

        assert result.days == 30
        mock_backfill.delay.assert_called_once_with(str(user_id))


class TestUnsupportedHistoricalSync:
    """Tests for providers that don't support historical sync."""

    def test_apple_raises_unsupported(self) -> None:
        """SDK-only provider should raise UnsupportedProviderError."""
        user_id = uuid4()

        with pytest.raises(UnsupportedProviderError, match="apple"):
            AppleStrategy().start_historical_sync(user_id, days=90)
