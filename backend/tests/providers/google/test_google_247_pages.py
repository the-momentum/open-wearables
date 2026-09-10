"""Page-envelope parsing for the Google 24/7 fetchers.

A malformed page must fail its own metric loudly instead of reading as an exhausted
window, which is what let a failed fetch pass as "no data" (#1545).
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.providers.google import DataPointsPage
from app.services.providers.google.health_api.data_247 import GoogleHealth247Data

USER_ID = uuid4()


@pytest.fixture
def data_247() -> GoogleHealth247Data:
    return GoogleHealth247Data(
        oauth=MagicMock(),
        connection_repo=MagicMock(),
        api_base_url="https://health.googleapis.com",
    )


class TestDataPointsPage:
    """Every shape Google actually returns, taken from stored payloads."""

    @pytest.mark.parametrize(
        ("payload", "expected_points", "expected_rollup", "expected_token"),
        [
            ({"dataPoints": [{"a": 1}], "nextPageToken": "t"}, 1, 0, "t"),
            ({}, 0, 0, None),
            ({"dataPoints": [{"a": 1}]}, 1, 0, None),
            ({"rollupDataPoints": [{"b": 2}]}, 0, 1, None),
            ({"nextPageToken": "t"}, 0, 0, "t"),
            ({"dataPoints": [], "someFutureField": "x"}, 0, 0, None),
        ],
    )
    def test_parses_every_observed_shape(
        self, payload: dict, expected_points: int, expected_rollup: int, expected_token: str | None
    ) -> None:
        page = DataPointsPage.model_validate(payload)

        assert len(page.data_points) == expected_points
        assert len(page.rollup_data_points) == expected_rollup
        assert page.next_page_token == expected_token

    @pytest.mark.parametrize("payload", [None, [], "oops", 42])
    def test_rejects_a_non_object_body(self, payload: object) -> None:
        with pytest.raises(Exception, match="validation error|Input should be"):
            DataPointsPage.model_validate(payload)


class TestParsePage:
    def test_raises_on_a_non_dict_instead_of_ending_the_window(self, data_247: GoogleHealth247Data) -> None:
        with pytest.raises(RuntimeError, match="Malformed .* response: list"):
            data_247._parse_page([], "/v4/users/me/dataTypes/heart-rate/dataPoints")

    def test_passes_a_valid_page_through(self, data_247: GoogleHealth247Data) -> None:
        page = data_247._parse_page({"dataPoints": [{"a": 1}]}, "/endpoint")

        assert len(page.data_points) == 1


class TestFailureIsolation:
    """One bad response fails its metric; the rest of the chain still syncs."""

    def test_a_malformed_page_does_not_stop_other_metrics(self, data_247: GoogleHealth247Data) -> None:
        db = MagicMock()
        calls: list[str] = []

        def fake_request(*args: object, **kwargs: object) -> object:
            endpoint = kwargs.get("endpoint") or args[6]
            calls.append(endpoint)
            # Only heart-rate comes back malformed.
            return [] if "heart-rate/" in endpoint else {"dataPoints": []}

        with (
            patch(
                "app.services.providers.google.health_api.data_247.make_authenticated_request",
                side_effect=fake_request,
            ),
            patch.object(data_247.sleep, "load_and_save", return_value=0),
            patch.object(data_247.settings_repo, "get_data_granularity", return_value=None),
            patch("app.services.providers.google.health_api.data_247.store_raw_payload"),
        ):
            results = data_247.load_and_save_all(db, USER_ID, MagicMock(), MagicMock())

        assert results == {}  # nothing had samples, but the run completed
        assert any("heart-rate/" in c for c in calls)
        # The chain kept going past the malformed metric.
        assert len({c for c in calls}) > 1


class TestPerMetricTransactions:
    """Each data type commits on its own, so one failure cannot corrupt or abort the rest."""

    def _run(self, data_247: GoogleHealth247Data, db: MagicMock, failing: str) -> dict:
        def fake_request(*args: object, **kwargs: object) -> object:
            endpoint = kwargs.get("endpoint") or args[6]
            if f"{failing}/" in str(endpoint):
                raise RuntimeError("boom")
            return {"dataPoints": []}

        with (
            patch(
                "app.services.providers.google.health_api.data_247.make_authenticated_request",
                side_effect=fake_request,
            ),
            patch.object(data_247.sleep, "load_and_save", return_value=0),
            patch.object(data_247.settings_repo, "get_data_granularity", return_value=None),
            patch("app.services.providers.google.health_api.data_247.store_raw_payload"),
        ):
            return data_247.load_and_save_all(db, USER_ID, MagicMock(), MagicMock())

    def test_a_failing_type_rolls_back_and_the_rest_continue(self, data_247: GoogleHealth247Data) -> None:
        db = MagicMock()

        self._run(data_247, db, failing="heart-rate")

        db.rollback.assert_called()
        assert db.commit.call_count >= 1  # other types still committed

    def test_a_failing_commit_does_not_cascade(self, data_247: GoogleHealth247Data) -> None:
        db = MagicMock()
        db.commit.side_effect = [RuntimeError("commit blew up")] + [None] * 50

        self._run(data_247, db, failing="nothing-fails")

        db.rollback.assert_called()
        # The loop kept going and committed the remaining types rather than aborting.
        assert db.commit.call_count > 1
