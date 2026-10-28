"""Domain errors raised by the shared provider API client.

A missing or dead connection is the user's state at the provider, never a 401 (which reads
as a bad API key), and a failed call keeps the provider's status and body out of ``detail``.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.services.providers import api_client
from app.utils.exceptions import (
    ProviderError,
    ProviderNotConnectedError,
    ProviderRateLimitError,
    ProviderReauthorizationRequiredError,
    ProviderTokenUnavailableError,
)

URL = "https://api.provider.test/v1/data"


def _token_args(connection: Any) -> dict[str, Any]:
    connection_repo = MagicMock()
    connection_repo.get_by_user_and_provider.return_value = connection
    return {
        "db": MagicMock(),
        "user_id": uuid4(),
        "provider_name": "garmin",
        "connection_repo": connection_repo,
        "oauth": MagicMock(),
    }


def _request_args() -> dict[str, Any]:
    return {
        "db": MagicMock(),
        "user_id": uuid4(),
        "connection_repo": MagicMock(),
        "oauth": MagicMock(),
        "api_base_url": "https://api.provider.test",
        "provider_name": "garmin",
        "endpoint": "/v1/data",
    }


def _response(status_code: int, **kwargs: Any) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", URL), **kwargs)


class TestGetValidToken:
    def test_no_connection(self) -> None:
        with pytest.raises(ProviderNotConnectedError) as exc_info:
            api_client.get_valid_token(**_token_args(None))

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "User is not connected to Garmin."

    def test_connection_without_a_token(self) -> None:
        with pytest.raises(ProviderTokenUnavailableError) as exc_info:
            api_client.get_valid_token(**_token_args(MagicMock(access_token=None)))

        assert exc_info.value.status_code == 400

    def test_expired_token_without_a_refresh_token(self) -> None:
        connection = MagicMock(
            access_token="at",
            refresh_token=None,
            token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        with pytest.raises(ProviderReauthorizationRequiredError) as exc_info:
            api_client.get_valid_token(**_token_args(connection))

        assert exc_info.value.status_code == 409


@patch("app.services.providers.api_client.get_valid_token", return_value="token")
@patch("app.services.providers.api_client.httpx.Client")
class TestMakeAuthenticatedRequest:
    @staticmethod
    def _answer(mock_client: MagicMock, *responses: httpx.Response | Exception) -> MagicMock:
        request = mock_client.return_value.__enter__.return_value.request
        request.side_effect = list(responses)
        return request

    def test_rejected_token_means_the_user_must_reconnect(self, mock_client: MagicMock, mock_token: MagicMock) -> None:
        self._answer(mock_client, _response(401, text="invalid_token"))

        with pytest.raises(ProviderReauthorizationRequiredError):
            api_client.make_authenticated_request(**_request_args())

    def test_error_response_keeps_the_body_out_of_the_detail(
        self, mock_client: MagicMock, mock_token: MagicMock
    ) -> None:
        self._answer(mock_client, _response(404, text='{"message": "user 42 not found"}'))

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        error = exc_info.value
        assert (error.status_code, error.upstream_status) == (502, 404)
        assert error.detail == "Garmin API error (status 404)"
        assert error.upstream_body == '{"message": "user 42 not found"}'

    @patch("app.services.providers.api_client.time.sleep")
    def test_throttle_that_persists_is_a_503(
        self, mock_sleep: MagicMock, mock_client: MagicMock, mock_token: MagicMock
    ) -> None:
        request = self._answer(mock_client, *[_response(429, text="slow down") for _ in range(4)])

        with pytest.raises(ProviderRateLimitError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert (exc_info.value.status_code, exc_info.value.upstream_status) == (503, 429)
        assert request.call_count == 4

    def test_no_response(self, mock_client: MagicMock, mock_token: MagicMock) -> None:
        self._answer(mock_client, httpx.ConnectTimeout("timed out"))

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status is None
        assert exc_info.value.detail == "Garmin API request failed"

    def test_empty_body_where_json_is_expected(self, mock_client: MagicMock, mock_token: MagicMock) -> None:
        self._answer(mock_client, _response(204))

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status == 204

    def test_error_in_a_200_body(self, mock_client: MagicMock, mock_token: MagicMock) -> None:
        self._answer(mock_client, _response(200, text='{"error": "not found", "code": 404, "request_id": "r1"}'))

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status == 404
        assert exc_info.value.upstream_body == '{"error": "not found", "code": 404, "request_id": "r1"}'

    def test_error_in_a_200_body_without_a_code(self, mock_client: MagicMock, mock_token: MagicMock) -> None:
        """The provider still rejected the request: dropped by a task like an upstream 400, not retried."""
        self._answer(mock_client, _response(200, json={"error": "Workout not found"}))

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status == 400
        assert exc_info.value.detail == "Garmin API error (status 400)"

    def test_error_in_a_200_body_with_a_string_code(self, mock_client: MagicMock, mock_token: MagicMock) -> None:
        """A provider outage reported as "503" is still retried by a task, not dropped as a 400."""
        self._answer(mock_client, _response(200, json={"error": "maintenance", "code": "503"}))

        with pytest.raises(ProviderError) as exc_info:
            api_client.make_authenticated_request(**_request_args())

        assert exc_info.value.upstream_status == 503


@patch("app.services.providers.api_client.get_valid_token", return_value="token")
@patch("app.services.providers.api_client.httpx.get")
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

    def test_error_response(self, mock_get: MagicMock, mock_token: MagicMock) -> None:
        mock_get.return_value = _response(403, text="forbidden")

        with pytest.raises(ProviderError) as exc_info:
            self._download()

        assert exc_info.value.upstream_status == 403

    def test_no_response(self, mock_get: MagicMock, mock_token: MagicMock) -> None:
        mock_get.side_effect = httpx.ReadTimeout("timed out")

        with pytest.raises(ProviderError) as exc_info:
            self._download()

        assert exc_info.value.upstream_status is None
