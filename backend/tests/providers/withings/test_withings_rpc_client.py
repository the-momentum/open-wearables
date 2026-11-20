"""Withings RPC envelope, pagination and measure scaling."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, create_autospec
from uuid import uuid4

import httpx
import pytest
import respx
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.providers.withings import WithingsMeasure
from app.services.providers.withings.handlers import rpc_client
from app.services.providers.withings.oauth import WithingsOAuth
from app.utils.exceptions import ProviderAuthRejectedError, ProviderRateLimitError


def _request(**overrides: Any) -> Any:
    kwargs: dict[str, Any] = {
        "db": MagicMock(spec=Session),
        "user_id": uuid4(),
        "connection_repo": create_autospec(UserConnectionRepository, instance=True),
        "oauth": create_autospec(WithingsOAuth, instance=True),
        "service_path": "/measure",
        "action": "getmeas",
        "params": {},
    }
    kwargs.update(overrides)
    return kwargs


def test_scale_measure_applies_power_of_ten() -> None:
    assert rpc_client.scale_measure(WithingsMeasure(value=7500, type=1, unit=-2)) == Decimal("75.00")
    assert rpc_client.scale_measure(WithingsMeasure(value=65, type=11, unit=0)) == Decimal("65")


def test_request_posts_form_data_and_unwraps_body(mocker: MockerFixture) -> None:
    mock_req = mocker.patch(
        "app.services.providers.withings.handlers.rpc_client.make_authenticated_request", autospec=True
    )
    mock_req.return_value = {"status": 0, "body": {"measuregrps": [1, 2]}}

    body = rpc_client.withings_request(**_request(params={"meastypes": "1"}))

    assert body == {"measuregrps": [1, 2]}
    kwargs = mock_req.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["form_data"] == {"action": "getmeas", "meastypes": "1"}


def test_nonzero_status_is_an_error_even_on_http_200(mocker: MockerFixture) -> None:
    mock_req = mocker.patch(
        "app.services.providers.withings.handlers.rpc_client.make_authenticated_request", autospec=True
    )
    mock_req.return_value = {"status": 503, "body": {}}

    with pytest.raises(rpc_client.WithingsAPIError) as exc_info:
        rpc_client.withings_request(**_request())

    assert exc_info.value.withings_status == 503
    assert exc_info.value.status_code == 502


def test_authentication_status_is_a_rejected_token(mocker: MockerFixture) -> None:
    mock_req = mocker.patch(
        "app.services.providers.withings.handlers.rpc_client.make_authenticated_request", autospec=True
    )
    mock_req.return_value = {"status": 100, "body": {}}

    with pytest.raises(ProviderAuthRejectedError) as exc_info:
        rpc_client.withings_request(**_request())

    assert exc_info.value.status_code == 502


THROTTLED = {"status": 601, "body": {}, "error": "Too Many Requests (#/min)"}
MEASURE_URL = f"{rpc_client.WITHINGS_API_BASE_URL}/measure"


def test_throttle_is_retried_through_the_shared_client(mocker: MockerFixture, respx_mock: respx.MockRouter) -> None:
    # Withings answers a throttle with HTTP 200 and an ``error`` next to the status. The
    # shared client used to raise on that message before the envelope was ever read.
    mocker.patch("app.services.providers.api_client.get_valid_token", autospec=True, return_value="token")
    mock_sleep = mocker.patch.object(rpc_client, "time", autospec=True).sleep
    respx_mock.post(MEASURE_URL).mock(
        side_effect=[
            httpx.Response(200, json=THROTTLED),
            httpx.Response(200, json={"status": 0, "body": {"series": []}}),
        ]
    )

    body = rpc_client.withings_request(**_request())

    assert body == {"series": []}
    assert [call.args[0] for call in mock_sleep.call_args_list] == [15.0]


def test_throttle_that_persists_is_a_rate_limit_error(mocker: MockerFixture, respx_mock: respx.MockRouter) -> None:
    mocker.patch("app.services.providers.api_client.get_valid_token", autospec=True, return_value="token")
    mock_sleep = mocker.patch.object(rpc_client, "time", autospec=True).sleep
    route = respx_mock.post(MEASURE_URL).respond(200, json=THROTTLED)

    with pytest.raises(ProviderRateLimitError) as exc_info:
        rpc_client.withings_request(**_request())

    assert exc_info.value.status_code == 503
    assert route.call_count == 4
    assert [call.args[0] for call in mock_sleep.call_args_list] == [15.0, 30.0, 60.0]


def test_paginate_follows_more_and_keeps_first_page_envelope(mocker: MockerFixture) -> None:
    mock_req = mocker.patch(
        "app.services.providers.withings.handlers.rpc_client.make_authenticated_request", autospec=True
    )
    mock_req.side_effect = [
        {"status": 0, "body": {"timezone": "Europe/Paris", "measuregrps": [1], "more": 1, "offset": 1}},
        {"status": 0, "body": {"measuregrps": [2]}},
    ]

    result = rpc_client.paginate(**_request(list_key="measuregrps"))

    assert result.rows == [1, 2]
    assert result.envelope["timezone"] == "Europe/Paris"
    assert mock_req.call_args_list[1].kwargs["form_data"]["offset"] == 1


def test_paginate_rejects_non_advancing_offset(mocker: MockerFixture) -> None:
    mock_req = mocker.patch(
        "app.services.providers.withings.handlers.rpc_client.make_authenticated_request", autospec=True
    )
    mock_req.return_value = {"status": 0, "body": {"measuregrps": [1], "more": 1, "offset": 0}}

    with pytest.raises(rpc_client.WithingsPaginationError):
        rpc_client.paginate(**_request(list_key="measuregrps"))
