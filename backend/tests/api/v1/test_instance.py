"""Tests for GET /api/v1/instance/info and GET/PATCH /api/v1/instance/settings."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import __version__ as core_version
from app.models import InstanceSettings
from app.services.sdk_token_service import create_sdk_user_token
from tests.factories import UserFactory


class TestGetInstanceInfo:
    def test_is_public_and_empty_before_setup(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        response = client.get(f"{api_v1_prefix}/instance/info")

        assert response.status_code == 200
        assert response.json() == {
            "name": None,
            "logo_url": None,
            "support_email": None,
            "api_version": core_version,
            "app_enabled": False,
            "instance_id": None,
            "privacy_policy_url": None,
            "terms_url": None,
            "require_acceptance": False,
            "legal_documents_version": 1,
        }

    def test_reflects_saved_settings(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        client.patch(
            f"{api_v1_prefix}/instance/settings",
            headers=auth_headers,
            json={
                "organization_name": "Acme Health",
                "logo_url": "https://acmehealth.com/logo.png",
                "support_email": "help@acmehealth.com",
            },
        )

        response = client.get(f"{api_v1_prefix}/instance/info")

        assert response.status_code == 200
        assert response.json() == {
            "name": "Acme Health",
            "logo_url": "https://acmehealth.com/logo.png",
            "support_email": "help@acmehealth.com",
            "api_version": core_version,
            "app_enabled": False,
            "instance_id": None,
            "privacy_policy_url": None,
            "terms_url": None,
            "require_acceptance": False,
            "legal_documents_version": 1,
        }


class TestInstanceSettings:
    def test_get_returns_empty_settings_before_setup(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        response = client.get(f"{api_v1_prefix}/instance/settings", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["organization_name"] is None
        assert db.get(InstanceSettings, 1) is None

    def test_patch_creates_the_row_once_and_updates_only_sent_fields(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        url = f"{api_v1_prefix}/instance/settings"
        client.patch(url, headers=auth_headers, json={"organization_name": "Acme", "support_email": "a@acme.com"})

        response = client.patch(url, headers=auth_headers, json={"organization_name": "Acme Health"})

        assert response.status_code == 200
        body = response.json()
        assert body["organization_name"] == "Acme Health"
        assert body["support_email"] == "a@acme.com"
        assert body["updated_at"] is not None
        assert db.query(InstanceSettings).count() == 1

    def test_null_or_blank_clears_a_field(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        url = f"{api_v1_prefix}/instance/settings"
        client.patch(url, headers=auth_headers, json={"organization_name": "Acme", "support_email": "a@acme.com"})

        response = client.patch(url, headers=auth_headers, json={"organization_name": "  ", "support_email": None})

        assert response.status_code == 200
        assert response.json()["organization_name"] is None
        assert response.json()["support_email"] is None

    def test_rejects_plain_http_logo(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            f"{api_v1_prefix}/instance/settings",
            headers=auth_headers,
            json={"logo_url": "http://acmehealth.com/logo.png"},
        )

        assert response.status_code == 400

    def test_rejects_invalid_email_and_long_name(
        self, client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
    ) -> None:
        url = f"{api_v1_prefix}/instance/settings"

        assert client.patch(url, headers=auth_headers, json={"support_email": "not-an-email"}).status_code == 400
        assert client.patch(url, headers=auth_headers, json={"organization_name": "x" * 101}).status_code == 400

    def test_requires_developer_auth(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        url = f"{api_v1_prefix}/instance/settings"

        assert client.get(url).status_code == 401
        assert client.patch(url, json={"organization_name": "Acme"}).status_code == 401

    def test_rejects_sdk_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        headers = {"Authorization": f"Bearer {create_sdk_user_token('app_123', str(UserFactory().id))}"}

        response = client.patch(
            f"{api_v1_prefix}/instance/settings", headers=headers, json={"organization_name": "Acme"}
        )

        assert response.status_code == 401
