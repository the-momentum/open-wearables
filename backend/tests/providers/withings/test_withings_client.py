from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.providers.withings import WithingsMeasure
from app.services.providers.withings import _client


def test_scale_measure_applies_power_of_ten() -> None:
    assert _client.scale_measure(WithingsMeasure(value=7500, type=1, unit=-2)) == Decimal("75.00")
    assert _client.scale_measure(WithingsMeasure(value=180, type=4, unit=-2)) == Decimal("1.80")
    assert _client.scale_measure(WithingsMeasure(value=65, type=11, unit=0)) == Decimal("65")


@patch("app.services.providers.withings._client.make_authenticated_request")
def test_withings_request_unwraps_body(mock_req: MagicMock) -> None:
    mock_req.return_value = {"status": 0, "body": {"measuregrps": [1, 2]}}
    body = _client.withings_request(
        db=MagicMock(),
        user_id=uuid4(),
        connection_repo=MagicMock(),
        oauth=MagicMock(),
        service_path="/measure",
        action="getmeas",
        params={"meastypes": "1"},
    )
    assert body == {"measuregrps": [1, 2]}
    kwargs = mock_req.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["params"]["action"] == "getmeas"
    assert kwargs["params"]["meastypes"] == "1"


@patch("app.services.providers.withings._client.make_authenticated_request")
def test_withings_request_status_100_returns_empty_body(mock_req: MagicMock) -> None:
    mock_req.return_value = {"status": 100, "body": {}}
    body = _client.withings_request(
        db=MagicMock(),
        user_id=uuid4(),
        connection_repo=MagicMock(),
        oauth=MagicMock(),
        service_path="/measure",
        action="getmeas",
        params={},
    )
    assert body == {}


@patch("app.services.providers.withings._client.make_authenticated_request")
def test_withings_request_raises_on_error_status(mock_req: MagicMock) -> None:
    mock_req.return_value = {"status": 601, "body": {}}
    with pytest.raises(HTTPException):
        _client.withings_request(
            db=MagicMock(),
            user_id=uuid4(),
            connection_repo=MagicMock(),
            oauth=MagicMock(),
            service_path="/measure",
            action="getmeas",
            params={},
        )


@patch("app.services.providers.withings._client.make_authenticated_request")
def test_paginate_follows_more_offset(mock_req: MagicMock) -> None:
    mock_req.side_effect = [
        {"status": 0, "body": {"rows": [1, 2], "more": 1, "offset": 2}},
        {"status": 0, "body": {"rows": [3], "more": 0, "offset": 0}},
    ]
    rows = _client.paginate(
        db=MagicMock(),
        user_id=uuid4(),
        connection_repo=MagicMock(),
        oauth=MagicMock(),
        service_path="/v2/measure",
        action="getactivity",
        params={},
        list_key="rows",
    )
    assert rows == [1, 2, 3]
    assert mock_req.call_count == 2


@patch("app.services.providers.withings._client.make_authenticated_request")
def test_paginate_stops_when_offset_does_not_advance(mock_req: MagicMock) -> None:
    """more=1 with a missing/zero/repeated offset must not refetch page 0 forever."""
    mock_req.return_value = {"status": 0, "body": {"rows": [1], "more": 1, "offset": 0}}
    rows = _client.paginate(
        db=MagicMock(),
        user_id=uuid4(),
        connection_repo=MagicMock(),
        oauth=MagicMock(),
        service_path="/v2/measure",
        action="getactivity",
        params={},
        list_key="rows",
    )
    assert rows == [1]
    assert mock_req.call_count == 1


@patch("app.services.providers.withings._client.make_authenticated_request")
def test_paginate_stops_at_page_cap(mock_req: MagicMock) -> None:
    """A pathological always-more response chain is cut off at the page cap."""

    def _page(**kwargs):  # noqa: ANN003, ANN202
        offset = kwargs["params"].get("offset", 0)
        return {"status": 0, "body": {"rows": [offset], "more": 1, "offset": offset + 1}}

    mock_req.side_effect = _page
    rows = _client.paginate(
        db=MagicMock(),
        user_id=uuid4(),
        connection_repo=MagicMock(),
        oauth=MagicMock(),
        service_path="/v2/measure",
        action="getactivity",
        params={},
        list_key="rows",
    )
    assert mock_req.call_count == _client._MAX_PAGES
    assert len(rows) == _client._MAX_PAGES
