"""Tests for the Open Wearables Connect app registration and seat requests."""

import base64
import json
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.integrations.license_server import LicenseServerError, LicenseServerUnavailableError
from app.models import AppRegistration
from app.services.app_registration_service import app_registration_service
from app.services.sdk_token_service import create_sdk_user_token
from app.utils.license_tokens import pseudo_user_id
from tests.factories import DeveloperFactory, UserFactory
from tests.utils import developer_auth_headers


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verified_claims(token: str, public_key: str) -> dict[str, Any]:
    """Decode a compact JWS after checking its Ed25519 signature, like the license server does."""
    header, payload, signature = token.split(".")
    Ed25519PublicKey.from_public_bytes(_b64decode(public_key)).verify(
        _b64decode(signature), f"{header}.{payload}".encode()
    )
    assert json.loads(_b64decode(header)) == {
        "alg": "EdDSA",
        "typ": "JWT",
        "kid": json.loads(_b64decode(payload))["iss"],
    }
    return json.loads(_b64decode(payload))


class FakeLicenseServer:
    """Stands in for licenses.openwearables.io and checks every token it receives."""

    def __init__(self) -> None:
        self.public_key: str | None = None
        self.status = "pending_verification"
        self.calls: list[tuple[str, Any]] = []
        self.fail_with: Exception | None = None

    def _auth(self, name: str, private_key: str, instance_id: UUID, payload: Any = None) -> None:
        if self.fail_with:
            raise self.fail_with
        from app.utils.license_tokens import instance_token, public_key_of

        claims = _verified_claims(instance_token(private_key, instance_id), public_key_of(private_key))
        assert claims["token_use"] == "instance"
        assert claims["iss"] == str(instance_id)
        self.calls.append((name, payload))

    def register(self, private_key: str, instance_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        self._auth("register", private_key, instance_id, body)
        self.public_key = body["public_key"]
        return {"instance_id": str(instance_id), "status": self.status, "email_verified_at": None}

    def get_instance(self, private_key: str, instance_id: UUID) -> dict[str, Any]:
        self._auth("get_instance", private_key, instance_id)
        verified = datetime.now(timezone.utc).isoformat() if self.status == "active" else None
        return {"instance_id": str(instance_id), "status": self.status, "email_verified_at": verified}

    def delete_instance(self, private_key: str, instance_id: UUID) -> None:
        self._auth("delete_instance", private_key, instance_id)

    def get_entitlement(self, private_key: str, instance_id: UUID) -> dict[str, Any]:
        self._auth("get_entitlement", private_key, instance_id)
        return {"status": self.status, "plan": "free", "seat_limit": 5, "seats_used": 3, "rejected_claims_7d": 1}

    def release_seat(self, private_key: str, instance_id: UUID, pseudonym: str) -> None:
        self._auth("release_seat", private_key, instance_id, pseudonym)


@pytest.fixture
def license_server() -> Generator[FakeLicenseServer, None, None]:
    fake = FakeLicenseServer()
    with patch.object(app_registration_service, "client", fake):
        yield fake


@pytest.fixture
def headers() -> dict[str, str]:
    return developer_auth_headers(DeveloperFactory().id)


def _register(client: TestClient, prefix: str, headers: dict[str, str], **overrides: Any) -> Any:
    body = {"admin_email": "admin@acmehealth.com", "accept_terms": True, "marketing_consent": False, **overrides}
    return client.post(f"{prefix}/app-registration", json=body, headers=headers)


def _activate(client: TestClient, db: Session, prefix: str, headers: dict[str, str], fake: FakeLicenseServer) -> None:
    assert _register(client, prefix, headers).status_code == 201
    fake.status = "active"
    assert client.get(f"{prefix}/app-registration", headers=headers).json()["status"] == "active"


class TestRegistration:
    def test_not_registered_by_default(
        self, client: TestClient, db: Session, api_v1_prefix: str, headers: dict[str, str]
    ) -> None:
        response = client.get(f"{api_v1_prefix}/app-registration", headers=headers)

        assert response.status_code == 200
        assert response.json()["registered"] is False

    def test_requires_developer(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        assert client.get(f"{api_v1_prefix}/app-registration").status_code == 401

    def test_terms_must_be_accepted(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        response = _register(client, api_v1_prefix, headers, accept_terms=False)

        assert response.status_code == 422
        assert license_server.calls == []

    def test_register_sends_only_id_key_email_and_consents(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        response = _register(client, api_v1_prefix, headers, marketing_consent=True)

        assert response.status_code == 201
        body = response.json()
        assert body["registered"] is True
        assert body["status"] == "pending_verification"
        name, sent = license_server.calls[0]
        assert name == "register"
        assert set(sent) == {"instance_id", "public_key", "admin_email", "terms_version", "marketing_consent"}
        assert sent["instance_id"] == body["instance_id"]
        assert sent["marketing_consent"] is True
        stored = db.get(AppRegistration, 1)
        assert stored is not None
        assert stored.private_key not in json.dumps(sent)

    def test_license_server_down_leaves_nothing_behind(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        license_server.fail_with = LicenseServerUnavailableError("down")

        response = _register(client, api_v1_prefix, headers)

        assert response.status_code == 502
        assert db.get(AppRegistration, 1) is None

    def test_failed_verification_email_keeps_the_pending_registration(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        license_server.fail_with = LicenseServerUnavailableError("503", code="EMAIL_UNAVAILABLE")

        response = _register(client, api_v1_prefix, headers)

        assert response.status_code == 503
        assert response.json()["license_code"] == "EMAIL_UNAVAILABLE"
        assert "confirmation email" in response.json()["detail"]
        pending = client.get(f"{api_v1_prefix}/app-registration", headers=headers).json()
        assert pending["status"] == "pending_verification"

        license_server.fail_with = None
        retry = _register(client, api_v1_prefix, headers)

        assert retry.status_code == 201
        assert retry.json()["instance_id"] == pending["instance_id"]

    def test_license_server_refusal_is_passed_through(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        license_server.fail_with = LicenseServerError(429, "REGISTRATION_LIMIT_REACHED", "Too many")

        response = _register(client, api_v1_prefix, headers)

        assert response.status_code == 429
        assert response.json()["license_code"] == "REGISTRATION_LIMIT_REACHED"

    def test_register_again_while_pending_keeps_the_keys(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        first = _register(client, api_v1_prefix, headers).json()
        key = license_server.public_key

        second = _register(client, api_v1_prefix, headers, admin_email="it@acmehealth.com")

        assert second.status_code == 201
        assert second.json()["instance_id"] == first["instance_id"]
        assert second.json()["admin_email"] == "it@acmehealth.com"
        assert license_server.public_key == key

    def test_status_follows_email_verification(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _activate(client, db, api_v1_prefix, headers, license_server)

        again = _register(client, api_v1_prefix, headers)

        assert again.status_code == 409

    def test_unregister_removes_the_registration(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _activate(client, db, api_v1_prefix, headers, license_server)

        response = client.delete(f"{api_v1_prefix}/app-registration", headers=headers)

        assert response.status_code == 204
        assert license_server.calls[-1][0] == "delete_instance"
        assert client.get(f"{api_v1_prefix}/app-registration", headers=headers).json()["registered"] is False

    def test_unregister_when_license_server_forgot_the_instance(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _register(client, api_v1_prefix, headers)
        license_server.fail_with = LicenseServerError(404, "INSTANCE_NOT_REGISTERED", "gone")

        response = client.delete(f"{api_v1_prefix}/app-registration", headers=headers)

        assert response.status_code == 204
        assert db.get(AppRegistration, 1) is None

    def test_entitlement_is_proxied(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _activate(client, db, api_v1_prefix, headers, license_server)

        response = client.get(f"{api_v1_prefix}/app-registration/entitlement", headers=headers)

        assert response.status_code == 200
        assert response.json()["seats_used"] == 3
        assert response.json()["seat_limit"] == 5

    def test_entitlement_when_not_registered(
        self, client: TestClient, db: Session, api_v1_prefix: str, headers: dict[str, str]
    ) -> None:
        assert client.get(f"{api_v1_prefix}/app-registration/entitlement", headers=headers).status_code == 404


class TestInstanceInfo:
    def test_app_disabled_until_verified(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        registered = _register(client, api_v1_prefix, headers).json()

        info = client.get(f"{api_v1_prefix}/instance/info").json()

        assert info["app_enabled"] is False
        assert info["instance_id"] == registered["instance_id"]

    def test_info_picks_up_verification_without_the_portal(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _register(client, api_v1_prefix, headers)
        license_server.status = "active"
        registration = db.get(AppRegistration, 1)
        assert registration is not None
        registration.status_checked_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

        info = client.get(f"{api_v1_prefix}/instance/info").json()

        assert info["app_enabled"] is True

    def test_info_does_not_ask_the_license_server_on_every_call(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _register(client, api_v1_prefix, headers)
        calls = len(license_server.calls)

        for _ in range(3):
            client.get(f"{api_v1_prefix}/instance/info")

        assert len(license_server.calls) == calls


class TestSeatRequest:
    def test_validate_carries_seat_request_for_the_user(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _activate(client, db, api_v1_prefix, headers, license_server)
        user = UserFactory()
        code = client.post(f"{api_v1_prefix}/users/{user.id}/invitation-code", headers=headers).json()["code"]

        response = client.post(f"{api_v1_prefix}/invitation-code/validate", json={"code": code})

        registration = db.get(AppRegistration, 1)
        assert registration is not None
        assert license_server.public_key is not None
        claims = _verified_claims(response.json()["seat_request"], license_server.public_key)
        assert claims["token_use"] == "seat_request"
        assert claims["aud"] == "ow-license-server"
        assert claims["iss"] == str(registration.instance_id)
        assert claims["sub"] == pseudo_user_id(registration.hmac_secret, user.id)
        assert claims["sub"] != str(user.id)
        assert claims["exp"] - claims["iat"] == 300
        assert claims["jti"]

    def test_validate_without_registration_has_no_seat_request(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _register(client, api_v1_prefix, headers)
        code = client.post(f"{api_v1_prefix}/users/{UserFactory().id}/invitation-code", headers=headers).json()["code"]

        response = client.post(f"{api_v1_prefix}/invitation-code/validate", json={"code": code})

        assert response.json()["seat_request"] is None

    def test_sdk_user_gets_a_fresh_seat_request(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _activate(client, db, api_v1_prefix, headers, license_server)
        user = UserFactory()
        token = create_sdk_user_token("app", str(user.id))

        response = client.post(
            f"{api_v1_prefix}/sdk/users/{user.id}/seat-request", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert license_server.public_key is not None
        assert (
            _verified_claims(response.json()["seat_request"], license_server.public_key)["token_use"] == "seat_request"
        )

    def test_sdk_user_cannot_ask_for_another_user(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _activate(client, db, api_v1_prefix, headers, license_server)
        token = create_sdk_user_token("app", str(UserFactory().id))

        response = client.post(
            f"{api_v1_prefix}/sdk/users/{UserFactory().id}/seat-request", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    def test_sdk_seat_request_while_app_not_enabled(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        token = create_sdk_user_token("app", str(user.id))

        response = client.post(
            f"{api_v1_prefix}/sdk/users/{user.id}/seat-request", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 409


class TestSeatRelease:
    def test_deleting_a_user_schedules_release(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _activate(client, db, api_v1_prefix, headers, license_server)
        user = UserFactory()

        with patch("app.services.user_service.release_app_seat.apply_async") as schedule:
            client.delete(f"{api_v1_prefix}/users/{user.id}", headers=headers)

        schedule.assert_called_once_with(args=[str(user.id)])

    def test_no_release_when_not_registered(
        self, client: TestClient, db: Session, api_v1_prefix: str, headers: dict[str, str]
    ) -> None:
        user = UserFactory()

        with patch("app.services.user_service.release_app_seat.apply_async") as schedule:
            client.delete(f"{api_v1_prefix}/users/{user.id}", headers=headers)

        schedule.assert_not_called()

    def test_release_sends_the_pseudonym(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        headers: dict[str, str],
        license_server: FakeLicenseServer,
    ) -> None:
        _activate(client, db, api_v1_prefix, headers, license_server)
        user = UserFactory()

        app_registration_service.release_seat(db, user.id)

        registration = db.get(AppRegistration, 1)
        assert registration is not None
        assert license_server.calls[-1] == ("release_seat", pseudo_user_id(registration.hmac_secret, user.id))
