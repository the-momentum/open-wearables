"""Google refuses an aggregating granularity instead of quietly storing raw data.

Windowed rollUp is disabled (#1577), so `hourly`/`daily` cannot be honoured. The pull
fails the sync; the webhook only logs, because a 5xx there is retried by Google.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import DataGranularity
from app.services.providers.google_health.data_247 import (
    GoogleHealth247Data,
    UnsupportedGranularityError,
)
from app.services.providers.google_health.webhook_handler import GoogleWebhookHandler

USER_ID = uuid4()
END = datetime(2026, 9, 10, tzinfo=timezone.utc)
START = END - timedelta(days=1)


@pytest.fixture
def data_247() -> GoogleHealth247Data:
    return GoogleHealth247Data(
        oauth=MagicMock(),
        connection_repo=MagicMock(),
        api_base_url="https://health.googleapis.com",
    )


def _drive(data_247: GoogleHealth247Data, granularity: DataGranularity, calls: list[str]) -> None:
    """Run a full pull at *granularity*, recording every endpoint it hits."""

    def fake_request(*args: object, **kwargs: object) -> object:
        calls.append(str(kwargs.get("endpoint") or args[6]))
        return {}

    with (
        patch(
            "app.services.providers.google_health.data_247.make_authenticated_request",
            side_effect=fake_request,
        ),
        patch.object(data_247.sleep, "load_and_save", return_value=3),
        patch.object(data_247.settings_repo, "get_data_granularity", return_value=granularity),
        patch("app.services.providers.google_health.data_247.store_raw_payload"),
    ):
        data_247.load_and_save_all(MagicMock(), USER_ID, START, END)


class TestPullSync:
    @pytest.mark.parametrize("granularity", [DataGranularity.HOURLY, DataGranularity.DAILY])
    def test_an_aggregating_granularity_fails_the_sync(
        self, data_247: GoogleHealth247Data, granularity: DataGranularity
    ) -> None:
        calls: list[str] = []

        with pytest.raises(UnsupportedGranularityError, match=granularity.value):
            _drive(data_247, granularity, calls)

        # The types that lost their rollUp path were not fetched; the civil-day ones still were.
        assert calls
        assert all("dailyRollUp" in c for c in calls)

    def test_raw_syncs_every_metric(self, data_247: GoogleHealth247Data) -> None:
        calls: list[str] = []

        _drive(data_247, DataGranularity.RAW, calls)

        assert any("dailyRollUp" not in c for c in calls)


class TestWebhookSync:
    @pytest.mark.parametrize("granularity", [DataGranularity.HOURLY, DataGranularity.DAILY])
    def test_a_notification_fetches_nothing(self, data_247: GoogleHealth247Data, granularity: DataGranularity) -> None:
        with (
            patch("app.services.providers.google_health.data_247.make_authenticated_request") as request,
            patch.object(data_247.settings_repo, "get_data_granularity", return_value=granularity),
            pytest.raises(UnsupportedGranularityError, match=granularity.value),
        ):
            data_247.sync_data_type(MagicMock(), USER_ID, "steps", START, END)

        request.assert_not_called()

    def test_the_handler_reports_it_instead_of_returning_a_5xx(self, data_247: GoogleHealth247Data) -> None:
        handler = GoogleWebhookHandler(data_247=data_247, workouts=MagicMock())

        with (
            patch.object(data_247, "sync_data_type", side_effect=UnsupportedGranularityError(DataGranularity.HOURLY)),
            patch("app.services.providers.google_health.webhook_handler.log_and_capture_error") as capture,
        ):
            saved = handler._fetch_and_save(MagicMock(), USER_ID, "steps", START, END)

        assert saved == 0
        capture.assert_called_once()
