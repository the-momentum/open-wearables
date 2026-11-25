"""Domain errors raised by the shared provider API client.

A missing or dead connection is the user's state at the provider, never a 401 (which reads
as a bad API key), and a failed call keeps the provider's status and body out of ``detail``.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, create_autospec
from uuid import uuid4

import httpx
import pytest
import respx
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.models import UserConnection
from app.repositories import UserConnectionRepository
from app.services.providers import api_client
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.exceptions import (
    ProviderAuthRejectedError,
    ProviderError,
    ProviderNotConnectedError,
    ProviderRateLimitError,
    ProviderTokenUnavailableError,
    ReauthRequiredError,
)

URL = "https://api.provider.test/v1/data"


def _token_args(connection: Any) -> dict[str, Any]:
    connection_repo = create_autospec(UserConnectionRepository, instance=True)
    connection_repo.get_by_user_and_provider.return_value = connection
    return {
        "db": MagicMock(spec=Session, info={}),
        "user_id": uuid4(),
        "provider_name": "garmin",
        "connection_repo": connection_repo,
        "oauth": create_autospec(BaseOAuthTemplate, instance=True),
    }


def _request_args() -> dict[str, Any]:
    return {
        "db": MagicMock(spec=Session, info={}),
        "user_id": uuid4(),
        "connection_repo": create_autospec(UserConnectionRepository, instance=True),
        "oauth": create_autospec(BaseOAuthTemplate, instance=True),
        "api_base_url": "https://api.provider.test",
        "provider_name": "garmin",
        "endpoint": "/v1/data",
    }


@pytest.fixture
def valid_token(mocker: MockerFixture) -> None:
    mocker.patch("app.services.providers.api_client.get_valid_token", autospec=True, return_value="token")


class TestGetValidToken:
    def test_no_connection(self) -> None:
        with pytest.raises(ProviderNotConnectedError) as exc_info:
            api_client.get_valid_token(**_token_args(None))

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "User is not connected to Garmin."

    def test_connection_without_a_token(self) -> None:
        with pytest.raises(ProviderTokenUnavailableError) as exc_info:
            api_client.get_valid_token(**_token_args(UserConnection(access_token=None)))

        assert exc_info.value.status_code == 400

    def test_expired_token_without_a_refresh_token(self) -> None:
        connection = UserConnection(
            access_token="at",
            refresh_token=None,
            token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        with pytest.raises(ReauthRequiredError) as exc_info:
            api_client.get_valid_token(**_token_args(connection))

        assert exc_info.value.status_code == 409


@pytest.mark.usefixtures("valid_token")
class TestMakeAuthenticatedRequest:
    def test_a_rejected_token_is_an_upstream_error_not_a_reconnect(
        self, mocker: MockerFixture, respx_mock: respx.MockRouter
    ) -> None:
        """Not proof the grant is dead: only a day of rejections revokes it (ReauthRequiredError, 409)."""
        mocker.patch("app.services.providers.api_client._reload_token_after_401", autospec=True, return_value=None)
        respx_mock.get(URL).respond(401, text="invalid_token")

        with pytest.raises(ProviderAuthRejectedError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.status_code == 502

    def test_error_response_keeps_the_body_out_of_the_detail(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(URL).respond(404, text='{"message": "user 42 not found"}')

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        error = exc_info.value
        assert (error.status_code, error.upstream_status) == (502, 404)
        assert error.detail == "Garmin API error (status 404)"
        assert error.upstream_body == '{"message": "user 42 not found"}'

    def test_throttle_that_persists_is_a_503(self, mocker: MockerFixture, respx_mock: respx.MockRouter) -> None:
        mocker.patch("app.services.providers.api_client.time.sleep", autospec=True)
        route = respx_mock.get(URL).respond(429, text="slow down")

        with pytest.raises(ProviderRateLimitError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert (exc_info.value.status_code, exc_info.value.upstream_status) == (503, 429)
        assert route.call_count == 4

    def test_no_response(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status is None
        assert exc_info.value.detail == "Garmin API request failed"

    def test_empty_body_where_json_is_expected(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(URL).respond(204)

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status == 204

    def test_error_in_a_200_body(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(URL).respond(200, text='{"error": "not found", "code": 404, "request_id": "r1"}')

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status == 404
        assert exc_info.value.upstream_body == '{"error": "not found", "code": 404, "request_id": "r1"}'

    def test_error_in_a_200_body_without_a_code(self, respx_mock: respx.MockRouter) -> None:
        """The provider still rejected the request: dropped by a task like an upstream 400, not retried."""
        respx_mock.get(URL).respond(200, json={"error": "Workout not found"})

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status == 400
        assert exc_info.value.detail == "Garmin API error (status 400)"

    def test_error_in_a_200_body_with_a_string_code(self, respx_mock: respx.MockRouter) -> None:
        """A provider outage reported as "503" is still retried by a task, not dropped as a 400."""
        respx_mock.get(URL).respond(200, json={"error": "maintenance", "code": "503"})

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status == 503


@pytest.mark.usefixtures("valid_token")
class TestDownloadBinaryContent:
    def _download(self) -> bytes:
        args = _request_args()
        return api_client.download_binary_content(
            db=args["db"],
            user_id=args["user_id"],
            connection_repo=args["connection_repo"],
            oauth=args["oauth"],
            provider_name="garmin",
            url=URL,
        )

    def test_error_response(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(URL).respond(403, text="forbidden")

        with pytest.raises(ProviderError) as exc_info:
            self._download()

        assert exc_info.value.upstream_status == 403

    def test_no_response(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(URL).mock(side_effect=httpx.ReadTimeout("timed out"))

        with pytest.raises(ProviderError) as exc_info:
            self._download()

        assert exc_info.value.upstream_status is None
