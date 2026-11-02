"""Tests for GET /api/v1/config."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import settings
from tests.factories import DeveloperFactory
from tests.utils import developer_auth_headers


class TestGetConfig:
    def test_email_enabled_false_without_transport(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        headers = developer_auth_headers(DeveloperFactory().id)
        with (
            patch.object(settings, "smtp_host", None),
            patch.object(settings, "resend_api_key", None),
        ):
            response = client.get(f"{api_v1_prefix}/config", headers=headers)

        assert response.status_code == 200
        assert response.json()["email_enabled"] is False

    def test_email_enabled_true_with_resend(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        headers = developer_auth_headers(DeveloperFactory().id)
        with (
            patch.object(settings, "smtp_host", None),
            patch.object(settings, "resend_api_key", SecretStr("re_test")),
            patch.object(settings, "email_from_address", "invites@example.com"),
        ):
            response = client.get(f"{api_v1_prefix}/config", headers=headers)

        assert response.status_code == 200
        assert response.json()["email_enabled"] is True

    def test_requires_auth(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        response = client.get(f"{api_v1_prefix}/config")

        assert response.status_code == 401
