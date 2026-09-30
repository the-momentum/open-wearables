"""A provider saying "there is nothing here" should not be logged as our failure.

make_authenticated_request logs at error level before it raises, so a caller that
already handles a status as "no data" cannot keep that line out of the logs. The
case that prompted this is a manual Strava activity: /streams answers 404, the
workouts code treats it as "no samples", and the error line is printed anyway.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.services.providers.api_client import make_authenticated_request

_ENDPOINT = "/api/v3/activities/123/streams"


def _response(status_code: int, content: bytes) -> httpx.Response:
    request = httpx.Request("GET", f"https://www.strava.com{_ENDPOINT}")
    return httpx.Response(status_code, content=content, request=request)


def _call(response: httpx.Response, **kwargs: object) -> tuple[object, MagicMock]:
    client = MagicMock()
    client.__enter__.return_value.request.return_value = response
    with (
        patch("app.services.providers.api_client._get_valid_token", return_value="tok"),
        patch("app.services.providers.api_client.httpx.Client", return_value=client),
        patch("app.services.providers.api_client.log_structured") as mock_log,
    ):
        try:
            result = make_authenticated_request(
                db=MagicMock(),
                user_id=uuid4(),
                connection_repo=MagicMock(),
                oauth=MagicMock(),
                api_base_url="https://www.strava.com",
                provider_name="strava",
                endpoint=_ENDPOINT,
                **kwargs,  # ty: ignore[invalid-argument-type]
            )
        except HTTPException as exc:
            result = exc
    return result, mock_log


def _error_calls(mock_log: MagicMock) -> list:
    return [c for c in mock_log.call_args_list if len(c.args) > 1 and c.args[1] == "error"]


class TestQuietStatuses:
    def test_expected_status_still_raises_but_is_not_logged(self) -> None:
        # Act
        result, mock_log = _call(_response(404, b"not found"), quiet_statuses=(404,))

        # Assert: the caller's flow is unchanged, only the log line is gone
        assert isinstance(result, HTTPException)
        assert result.status_code == 404
        assert _error_calls(mock_log) == []

    def test_unexpected_status_stays_loud(self) -> None:
        # Act
        result, mock_log = _call(_response(500, b"boom"), quiet_statuses=(404,))

        # Assert
        assert isinstance(result, HTTPException)
        assert _error_calls(mock_log)

    def test_it_is_opt_in(self) -> None:
        """Other providers see no change unless they pass quiet_statuses."""
        # Act
        _, mock_log = _call(_response(404, b"not found"))

        # Assert
        assert _error_calls(mock_log)

    def test_error_log_names_the_endpoint(self) -> None:
        # Act
        _, mock_log = _call(_response(500, b"boom"))

        # Assert
        assert _error_calls(mock_log)[0].kwargs.get("endpoint") == _ENDPOINT


class TestEmptyBodyIsNoContent:
    @pytest.mark.parametrize(
        ("status_code", "content"),
        [(204, b""), (200, b""), (200, b"   \n")],
        ids=["204", "200-empty", "200-whitespace"],
    )
    def test_returns_none_instead_of_raising(self, status_code: int, content: bytes) -> None:
        # Act
        result, mock_log = _call(_response(status_code, content))

        # Assert
        assert result is None
        assert _error_calls(mock_log) == []

    def test_a_real_body_still_parses(self) -> None:
        # Act
        result, _ = _call(_response(200, b'{"ok": true}'))

        # Assert
        assert result == {"ok": True}
