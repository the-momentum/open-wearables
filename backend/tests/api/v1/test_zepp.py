"""Tests for Zepp API endpoints."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.auth import ConnectionStatus
from app.services.providers.zepp.client import ZeppAuthExpiredError
from tests.factories import UserFactory


class TestZeppEndpoints:
    def test_verify_zepp_success(self, client: TestClient) -> None:
        with patch("app.api.routes.v1.zepp.ZeppClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.get_user_info.return_value = {"userid": "12345", "name": "Athlete"}
            mock_client_cls.return_value = mock_client

            response = client.post(
                "/api/v1/providers/zepp/verify",
                json={
                    "app_token": "valid_token_123",
                    "user_id": "12345",
                    "host": "api-mifit-us3.zepp.com",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert data["user_id"] == "12345"

    def test_verify_zepp_invalid_token(self, client: TestClient) -> None:
        with patch("app.api.routes.v1.zepp.ZeppClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.get_user_info.side_effect = ZeppAuthExpiredError("Token expired")
            mock_client_cls.return_value = mock_client

            response = client.post(
                "/api/v1/providers/zepp/verify",
                json={
                    "app_token": "expired_token_123",
                    "user_id": "12345",
                    "host": "api-mifit-us3.zepp.com",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False
            assert "Authentication failed" in data["message"]

    def test_connect_zepp_success(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        with patch("app.api.routes.v1.zepp.ZeppClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.get_user_info.return_value = {"userid": "999888"}
            mock_client_cls.return_value = mock_client

            with patch("app.services.providers.zepp.strategy.ZeppStrategy.start_historical_sync") as mock_sync:
                response = client.post(
                    f"/api/v1/providers/zepp/users/{user.id}/connect",
                    json={
                        "app_token": "tok_xyz_123",
                        "provider_user_id": "999888",
                        "host": "api-mifit-us3.zepp.com",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["provider"] == "zepp"
                assert data["provider_user_id"] == "999888"
                assert data["status"] == ConnectionStatus.ACTIVE
                assert data["icon_url"] == "/static/provider-icons/zepp.svg"
                assert data["rest_pull"] is True
                mock_sync.assert_called_once_with(user_id=user.id, days=30)

    def test_connect_zepp_invalid_credentials_fails(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        with patch("app.api.routes.v1.zepp.ZeppClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.get_user_info.side_effect = ZeppAuthExpiredError("Bad token")
            mock_client_cls.return_value = mock_client

            response = client.post(
                f"/api/v1/providers/zepp/users/{user.id}/connect",
                json={
                    "app_token": "invalid_tok",
                    "provider_user_id": "999888",
                    "host": "api-mifit-us3.zepp.com",
                },
            )

            assert response.status_code == 400
            assert "Invalid Zepp credentials" in response.json()["detail"]

    def test_connect_zepp_user_not_found(self, client: TestClient, db: Session) -> None:
        non_existent_id = uuid4()
        response = client.post(
            f"/api/v1/providers/zepp/users/{non_existent_id}/connect",
            json={
                "app_token": "tok_xyz_123",
                "provider_user_id": "999888",
                "host": "api-mifit-us3.zepp.com",
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
