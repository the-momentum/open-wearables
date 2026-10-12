"""Tests for the API-key connect flow (POST /users/{user_id}/connections/{provider})."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import UserConnection
from app.schemas.auth import ConnectionStatus
from tests.factories import ApiKeyFactory, UserFactory
from tests.utils import api_key_headers

HEVY_KEY = "11111111-2222-3333-4444-555555555555"


@pytest.fixture(autouse=True)
def backfill_task() -> Iterator[MagicMock]:
    """The connect endpoint queues the 90-day backfill on Celery; keep it off the broker."""
    with patch("app.integrations.celery.tasks.sync_vendor_data") as task:
        yield task


def _mock_user_info_response(status_code: int = 200) -> MagicMock:
    response = MagicMock(status_code=status_code)
    response.json.return_value = {"id": "hevy-user-1", "name": "John Doe", "url": "https://hevy.com/user/jd"}
    return response


class TestHevyApiKeyConnect:
    def test_connect_accepts_the_live_data_envelope(self, client: TestClient, db: Session) -> None:
        """The live API wraps the user in {"data": {...}} and adds a username (seen 2026-10-04)."""
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().plain_key)
        live = MagicMock(status_code=200)
        live.json.return_value = {
            "data": {
                "id": "hevy-user-9",
                "username": "jdoe",
                "name": "John Doe",
                "url": "https://hevy.com/user/jdoe",
                "weight_unit": "kg",
                "distance_unit": "kilometers",
            }
        }

        with patch("app.services.providers.hevy.strategy.httpx.get", return_value=live):
            response = client.post(
                f"/api/v1/users/{user.id}/connections/hevy",
                json={"api_key": HEVY_KEY},
                headers=headers,
            )

        assert response.status_code == 201, response.text
        assert response.json()["provider_user_id"] == "hevy-user-9"
        assert response.json()["provider_username"] == "jdoe"

    def test_connect_creates_connection(self, client: TestClient, db: Session, backfill_task: MagicMock) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().plain_key)

        with patch(
            "app.services.providers.hevy.strategy.httpx.get", return_value=_mock_user_info_response()
        ) as mock_get:
            response = client.post(
                f"/api/v1/users/{user.id}/connections/hevy",
                json={"api_key": HEVY_KEY},
                headers=headers,
            )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["provider"] == "hevy"
        assert body["provider_user_id"] == "hevy-user-1"
        assert body["rest_pull"] is True

        # key validated against /v1/user/info with the api-key header
        assert mock_get.call_args.kwargs["headers"]["api-key"] == HEVY_KEY

        connection = (
            db.query(UserConnection).filter(UserConnection.user_id == user.id, UserConnection.provider == "hevy").one()
        )
        assert connection.access_token == HEVY_KEY
        assert connection.refresh_token is None
        assert connection.token_expires_at is None
        assert connection.status == ConnectionStatus.ACTIVE
        # cursor stamped so the first periodic pull doesn't re-fetch everything
        assert connection.last_synced_at is not None
        # and the same 90-day backfill the OAuth callback queues
        backfill_task.delay.assert_called_once()
        assert backfill_task.delay.call_args.kwargs["providers"] == ["hevy"]
        assert backfill_task.delay.call_args.kwargs["is_historical"] is True

    def test_reconnect_rotates_key_without_duplicate_row(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().plain_key)
        new_key = "99999999-8888-7777-6666-555555555555"

        with patch("app.services.providers.hevy.strategy.httpx.get", return_value=_mock_user_info_response()):
            first = client.post(
                f"/api/v1/users/{user.id}/connections/hevy", json={"api_key": HEVY_KEY}, headers=headers
            )
            second = client.post(
                f"/api/v1/users/{user.id}/connections/hevy", json={"api_key": new_key}, headers=headers
            )

        assert first.status_code == 201
        assert second.status_code == 201
        connections = (
            db.query(UserConnection).filter(UserConnection.user_id == user.id, UserConnection.provider == "hevy").all()
        )
        assert len(connections) == 1
        assert connections[0].access_token == new_key

    def test_rejected_key_returns_400(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().plain_key)

        with patch("app.services.providers.hevy.strategy.httpx.get", return_value=MagicMock(status_code=401)):
            response = client.post(
                f"/api/v1/users/{user.id}/connections/hevy",
                json={"api_key": "bogus"},
                headers=headers,
            )

        assert response.status_code == 400
        assert (
            db.query(UserConnection)
            .filter(UserConnection.user_id == user.id, UserConnection.provider == "hevy")
            .count()
            == 0
        )

    @pytest.mark.parametrize(
        "failure",
        [
            httpx.ConnectTimeout("timed out"),
            httpx.ConnectError("connection refused"),
            httpx.Response(429, request=httpx.Request("GET", "https://api.hevyapp.com/v1/user/info")),
            httpx.Response(503, request=httpx.Request("GET", "https://api.hevyapp.com/v1/user/info")),
            httpx.Response(200, text="<html>maintenance</html>"),
        ],
        ids=["timeout", "connect-error", "429", "503", "unexpected-body"],
    )
    def test_hevy_outage_is_a_502_not_an_invalid_key(
        self, client: TestClient, db: Session, failure: Exception | httpx.Response
    ) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().plain_key)
        mock_kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}

        with patch("app.services.providers.hevy.strategy.httpx.get", **mock_kwargs):
            response = client.post(
                f"/api/v1/users/{user.id}/connections/hevy", json={"api_key": HEVY_KEY}, headers=headers
            )

        assert response.status_code == 502, response.text
        assert "Hevy" in response.json()["detail"]
        assert (
            db.query(UserConnection)
            .filter(UserConnection.user_id == user.id, UserConnection.provider == "hevy")
            .count()
            == 0
        )

    def test_reposting_another_accounts_key_switches_the_identity(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().plain_key)
        other_account = _mock_user_info_response()
        other_account.json.return_value = {"data": {"id": "hevy-user-2", "username": "jane"}}

        with patch("app.services.providers.hevy.strategy.httpx.get", return_value=_mock_user_info_response()):
            client.post(f"/api/v1/users/{user.id}/connections/hevy", json={"api_key": HEVY_KEY}, headers=headers)
        with patch("app.services.providers.hevy.strategy.httpx.get", return_value=other_account):
            response = client.post(
                f"/api/v1/users/{user.id}/connections/hevy", json={"api_key": "other-key"}, headers=headers
            )

        assert response.status_code == 201, response.text
        connection = (
            db.query(UserConnection).filter(UserConnection.user_id == user.id, UserConnection.provider == "hevy").one()
        )
        db.refresh(connection)
        assert connection.access_token == "other-key"
        assert connection.provider_user_id == "hevy-user-2"
        assert connection.provider_username == "jane"

    def test_oauth_provider_rejects_api_key_connect(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().plain_key)

        response = client.post(
            f"/api/v1/users/{user.id}/connections/garmin",
            json={"api_key": "whatever"},
            headers=headers,
        )

        assert response.status_code == 400
        assert "does not support API-key connect" in response.json()["detail"]

    def test_missing_api_key_header_rejected(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        response = client.post(f"/api/v1/users/{user.id}/connections/hevy", json={"api_key": HEVY_KEY})
        assert response.status_code in (401, 403)
