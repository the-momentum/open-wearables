"""Withings RPC envelope, pagination and measure scaling."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.providers.withings import WithingsMeasure
from app.services.providers.withings import rpc_client


def _request(**overrides: Any) -> Any:
    kwargs: dict[str, Any] = {
        "db": MagicMock(),
        "user_id": uuid4(),
        "connection_repo": MagicMock(),
        "oauth": MagicMock(),
        "service_path": "/measure",
        "action": "getmeas",
        "params": {},
    }
    kwargs.update(overrides)
    return kwargs


def test_scale_measure_applies_power_of_ten() -> None:
    assert rpc_client.scale_measure(WithingsMeasure(value=7500, type=1, unit=-2)) == Decimal("75.00")
    assert rpc_client.scale_measure(WithingsMeasure(value=65, type=11, unit=0)) == Decimal("65")


@patch("app.services.providers.withings.rpc_client.make_authenticated_request")
def test_request_posts_form_data_and_unwraps_body(mock_req: MagicMock) -> None:
    mock_req.return_value = {"status": 0, "body": {"measuregrps": [1, 2]}}

    body = rpc_client.withings_request(**_request(params={"meastypes": "1"}))

    assert body == {"measuregrps": [1, 2]}
    kwargs = mock_req.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["form_data"] == {"action": "getmeas", "meastypes": "1"}


@pytest.mark.parametrize(
    ("withings_status", "http_status"),
    [(100, 401), (601, 429), (503, 502)],
)
@patch("app.services.providers.withings.rpc_client.make_authenticated_request")
def test_nonzero_status_is_an_error_even_on_http_200(
    mock_req: MagicMock, withings_status: int, http_status: int
) -> None:
    mock_req.return_value = {"status": withings_status, "body": {}}

    with pytest.raises(rpc_client.WithingsAPIError) as exc_info:
        rpc_client.withings_request(**_request())

    assert exc_info.value.withings_status == withings_status
    assert exc_info.value.status_code == http_status


@patch("app.services.providers.withings.rpc_client.make_authenticated_request")
def test_paginate_follows_more_and_keeps_first_page_envelope(mock_req: MagicMock) -> None:
    mock_req.side_effect = [
        {"status": 0, "body": {"timezone": "Europe/Paris", "measuregrps": [1], "more": 1, "offset": 1}},
        {"status": 0, "body": {"measuregrps": [2]}},
    ]

    result = rpc_client.paginate(**_request(list_key="measuregrps"))

    assert result.rows == [1, 2]
    assert result.envelope["timezone"] == "Europe/Paris"
    assert mock_req.call_args_list[1].kwargs["form_data"]["offset"] == 1


@patch("app.services.providers.withings.rpc_client.make_authenticated_request")
def test_paginate_rejects_non_advancing_offset(mock_req: MagicMock) -> None:
    mock_req.return_value = {"status": 0, "body": {"measuregrps": [1], "more": 1, "offset": 0}}

    with pytest.raises(rpc_client.WithingsPaginationError):
        rpc_client.paginate(**_request(list_key="measuregrps"))
