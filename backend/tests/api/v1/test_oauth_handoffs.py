from collections.abc import Generator
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.redis_client import get_redis_client
from app.models import UserConnection
from app.schemas.auth import ConnectionStatus
from app.schemas.model_crud.credentials import OAuthTokenResponse
from tests.factories import ApiKeyFactory, UserConnectionFactory, UserFactory
from tests.utils import api_key_headers

RETURN_URI = "https://science.team42.run/auth/strava/callback"
CLIENT_STATE = "client-state-with-enough-entropy"


@pytest.fixture
def enabled_handoffs() -> Generator[None, None, None]:
    key = Fernet.generate_key().decode()
    with (
        patch.object(settings, "team42_oauth_handoff_enabled", True),
        patch.object(settings, "team42_oauth_handoff_key", SecretStr(key)),
        patch.object(settings, "team42_oauth_handoff_return_uris", RETURN_URI),
        patch.object(settings, "team42_oauth_handoff_allowed_scopes", "read,activity:read_all"),
        patch.object(settings, "team42_oauth_handoff_state_ttl_seconds", 600),
        patch.object(settings, "team42_oauth_handoff_code_ttl_seconds", 600),
    ):
        yield


def _bootstrap(
    client: TestClient,
    *,
    purpose: str,
    scopes: list[str],
    return_uri: str = RETURN_URI,
) -> tuple[str, str]:
    api_key = ApiKeyFactory()
    response = client.post(
        "/api/v1/oauth/bootstrap/strava",
        headers=api_key_headers(api_key.id),
        json={
            "state": CLIENT_STATE,
            "return_uri": return_uri,
            "purpose": purpose,
            "scopes": scopes,
        },
    )
    assert response.status_code == 200
    authorization_url = response.json()["authorization_url"]
    internal_state = parse_qs(urlparse(authorization_url).query)["state"][0]
    return api_key.id, internal_state


def _complete_callback(
    client: TestClient,
    internal_state: str,
    *,
    scope: str = "read,activity:read_all",
    callback_scope: str | None = None,
    subject: str = "424242",
) -> str:
    token = OAuthTokenResponse(
        access_token="secret-access-token",
        refresh_token="secret-refresh-token",
        token_type="Bearer",
        expires_in=21600,
        scope=scope,
    )
    profile = {
        "user_id": subject,
        "username": "runner",
        "first_name": "Ada",
        "last_name": "Lovelace",
    }
    with (
        patch(
            "app.services.providers.strava.oauth.StravaOAuth._exchange_token",
            return_value=token,
        ),
        patch(
            "app.services.providers.strava.oauth.StravaOAuth._get_provider_user_info",
            return_value=profile,
        ),
    ):
        params = {"code": "provider-code", "state": internal_state}
        if callback_scope is not None:
            params["scope"] = callback_scope
        response = client.get("/api/v1/oauth/strava/callback", params=params, follow_redirects=False)

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(f"{RETURN_URI}#")
    fragment = parse_qs(urlparse(location).fragment)
    assert fragment["state"] == [CLIENT_STATE]
    return fragment["handoff"][0]


def _inspect(client: TestClient, api_key: str, handoff_code: str) -> dict:
    response = client.post(
        "/api/v1/oauth/handoffs/inspect",
        headers=api_key_headers(api_key),
        json={"handoff_code": handoff_code},
    )
    assert response.status_code == 200
    return response.json()


class TestOAuthHandoffBootstrap:
    def test_disabled_by_default(self, client: TestClient) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            "/api/v1/oauth/bootstrap/strava",
            headers=api_key_headers(api_key.id),
            json={
                "state": CLIENT_STATE,
                "return_uri": RETURN_URI,
                "purpose": "login",
                "scopes": ["read"],
            },
        )
        assert response.status_code == 404

    def test_requires_api_key(self, client: TestClient, enabled_handoffs: None) -> None:
        response = client.post(
            "/api/v1/oauth/bootstrap/strava",
            json={
                "state": CLIENT_STATE,
                "return_uri": RETURN_URI,
                "purpose": "login",
                "scopes": ["read"],
            },
        )
        assert response.status_code == 401

    def test_rejects_unregistered_return_uri(self, client: TestClient, enabled_handoffs: None) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            "/api/v1/oauth/bootstrap/strava",
            headers=api_key_headers(api_key.id),
            json={
                "state": CLIENT_STATE,
                "return_uri": "https://evil.example/callback",
                "purpose": "login",
                "scopes": ["read"],
            },
        )
        assert response.status_code == 400

    def test_login_cannot_request_activity_scopes(self, client: TestClient, enabled_handoffs: None) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            "/api/v1/oauth/bootstrap/strava",
            headers=api_key_headers(api_key.id),
            json={
                "state": CLIENT_STATE,
                "return_uri": RETURN_URI,
                "purpose": "login",
                "scopes": ["read", "activity:read_all"],
            },
        )
        assert response.status_code == 400

    def test_state_payload_is_encrypted(self, client: TestClient, enabled_handoffs: None) -> None:
        _, internal_state = _bootstrap(client, purpose="login", scopes=["read"])
        raw = get_redis_client().get(f"team42_oauth_handoff_state:{internal_state}")
        assert raw
        assert CLIENT_STATE not in str(raw)
        assert RETURN_URI not in str(raw)


class TestOAuthHandoffCallbackAndInspect:
    def test_denial_redirect_consumes_state(self, client: TestClient, enabled_handoffs: None) -> None:
        _, internal_state = _bootstrap(client, purpose="login", scopes=["read"])
        response = client.get(
            "/api/v1/oauth/strava/callback",
            params={"state": internal_state, "error": "access_denied"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        fragment = parse_qs(urlparse(response.headers["location"]).fragment)
        assert fragment["state"] == [CLIENT_STATE]
        assert fragment["error"] == ["access_denied"]

        replay = client.get(
            "/api/v1/oauth/strava/callback",
            params={"state": internal_state, "error": "access_denied"},
            follow_redirects=False,
        )
        assert replay.status_code == 303
        assert replay.headers["location"].startswith("/api/v1/oauth/error")

    def test_login_inspection_is_identity_only_and_single_use(
        self,
        client: TestClient,
        enabled_handoffs: None,
    ) -> None:
        api_key, internal_state = _bootstrap(client, purpose="login", scopes=["read"])
        handoff_code = _complete_callback(client, internal_state, scope="read")
        inspected = _inspect(client, api_key, handoff_code)

        assert inspected == {
            "provider_subject": "424242",
            "scope": "read",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "provider_username": "runner",
            "purpose": "login",
            "activity_sync_authorized": False,
            "claim_code": None,
        }
        assert "secret-access-token" not in str(inspected)
        assert not get_redis_client().keys("team42_oauth_handoff_claim:*")

        replay = client.post(
            "/api/v1/oauth/handoffs/inspect",
            headers=api_key_headers(api_key),
            json={"handoff_code": handoff_code},
        )
        assert replay.status_code == 410

    def test_registration_inspection_rotates_to_claim_code(
        self,
        client: TestClient,
        enabled_handoffs: None,
    ) -> None:
        api_key, internal_state = _bootstrap(
            client,
            purpose="register",
            scopes=["read", "activity:read_all"],
        )
        handoff_code = _complete_callback(client, internal_state)
        inspected = _inspect(client, api_key, handoff_code)

        assert inspected["purpose"] == "register"
        assert inspected["activity_sync_authorized"] is True
        assert inspected["claim_code"]
        assert "secret-access-token" not in str(inspected)

    def test_callback_scope_is_used_when_token_response_omits_scope(
        self,
        client: TestClient,
        enabled_handoffs: None,
    ) -> None:
        api_key, internal_state = _bootstrap(
            client,
            purpose="register",
            scopes=["read", "activity:read_all"],
        )
        handoff_code = _complete_callback(
            client,
            internal_state,
            scope="",
            callback_scope="read,activity:read_all",
        )
        inspected = _inspect(client, api_key, handoff_code)

        assert inspected["scope"] == "activity:read_all,read"
        assert inspected["activity_sync_authorized"] is True
        assert inspected["claim_code"]


class TestOAuthHandoffClaim:
    def test_claim_connects_target_without_starting_historical_sync(
        self,
        client: TestClient,
        db: Session,
        enabled_handoffs: None,
    ) -> None:
        api_key, internal_state = _bootstrap(
            client,
            purpose="register",
            scopes=["read", "activity:read_all"],
        )
        inspected = _inspect(client, api_key, _complete_callback(client, internal_state))
        user = UserFactory()

        response = client.post(
            "/api/v1/oauth/handoffs/claim",
            headers=api_key_headers(api_key),
            json={"handoff_code": inspected["claim_code"], "user_id": str(user.id)},
        )
        assert response.status_code == 200
        assert response.json()["claimed"] is True

        connection = (
            db.query(UserConnection)
            .filter(UserConnection.user_id == user.id, UserConnection.provider == "strava")
            .one()
        )
        assert connection.provider_user_id == "424242"
        assert connection.access_token == "secret-access-token"
        assert connection.refresh_token == "secret-refresh-token"
        assert connection.status == ConnectionStatus.ACTIVE
        assert connection.last_synced_at is not None

        replay = client.post(
            "/api/v1/oauth/handoffs/claim",
            headers=api_key_headers(api_key),
            json={"handoff_code": inspected["claim_code"], "user_id": str(user.id)},
        )
        assert replay.status_code == 410

    def test_claim_rejects_subject_owned_by_revoked_other_user(
        self,
        client: TestClient,
        enabled_handoffs: None,
    ) -> None:
        other_user = UserFactory()
        UserConnectionFactory(
            user=other_user,
            provider="strava",
            provider_user_id="424242",
            status=ConnectionStatus.REVOKED,
            access_token=None,
            refresh_token=None,
        )
        target_user = UserFactory()
        api_key, internal_state = _bootstrap(
            client,
            purpose="register",
            scopes=["read", "activity:read_all"],
        )
        inspected = _inspect(client, api_key, _complete_callback(client, internal_state))

        response = client.post(
            "/api/v1/oauth/handoffs/claim",
            headers=api_key_headers(api_key),
            json={"handoff_code": inspected["claim_code"], "user_id": str(target_user.id)},
        )
        assert response.status_code == 409

    def test_claim_reactivates_same_subject_for_same_user(
        self,
        client: TestClient,
        db: Session,
        enabled_handoffs: None,
    ) -> None:
        target_user = UserFactory()
        existing = UserConnectionFactory(
            user=target_user,
            provider="strava",
            provider_user_id="424242",
            status=ConnectionStatus.REVOKED,
            access_token=None,
            refresh_token=None,
        )
        api_key, internal_state = _bootstrap(
            client,
            purpose="register",
            scopes=["read", "activity:read_all"],
        )
        inspected = _inspect(client, api_key, _complete_callback(client, internal_state))

        response = client.post(
            "/api/v1/oauth/handoffs/claim",
            headers=api_key_headers(api_key),
            json={"handoff_code": inspected["claim_code"], "user_id": str(target_user.id)},
        )

        assert response.status_code == 200
        db.refresh(existing)
        assert existing.status == ConnectionStatus.ACTIVE
        assert existing.provider_user_id == "424242"
        assert existing.access_token == "secret-access-token"
        assert existing.refresh_token == "secret-refresh-token"
        assert (
            db.query(UserConnection)
            .filter(UserConnection.user_id == target_user.id, UserConnection.provider == "strava")
            .count()
            == 1
        )

    def test_claim_rejects_replacing_targets_existing_subject(
        self,
        client: TestClient,
        enabled_handoffs: None,
    ) -> None:
        target_user = UserFactory()
        UserConnectionFactory(
            user=target_user,
            provider="strava",
            provider_user_id="different-subject",
            status=ConnectionStatus.REVOKED,
            access_token=None,
            refresh_token=None,
        )
        api_key, internal_state = _bootstrap(
            client,
            purpose="register",
            scopes=["read", "activity:read_all"],
        )
        inspected = _inspect(client, api_key, _complete_callback(client, internal_state))

        response = client.post(
            "/api/v1/oauth/handoffs/claim",
            headers=api_key_headers(api_key),
            json={"handoff_code": inspected["claim_code"], "user_id": str(target_user.id)},
        )
        assert response.status_code == 409

    def test_claim_serializes_connections_for_the_target_user(
        self,
        client: TestClient,
        enabled_handoffs: None,
    ) -> None:
        target_user = UserFactory()
        api_key, internal_state = _bootstrap(
            client,
            purpose="register",
            scopes=["read", "activity:read_all"],
        )
        inspected = _inspect(client, api_key, _complete_callback(client, internal_state))
        lock_key = f"team42_oauth_handoff_user_lock:{target_user.id}"
        get_redis_client().set(lock_key, "1", ex=60)

        response = client.post(
            "/api/v1/oauth/handoffs/claim",
            headers=api_key_headers(api_key),
            json={"handoff_code": inspected["claim_code"], "user_id": str(target_user.id)},
        )

        assert response.status_code == 409
        assert not get_redis_client().keys("team42_oauth_handoff_subject_lock:*")
