"""Tests for the OAuth redirect_uri allowlist, authorize auth and callback redirects."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.model_crud.credentials import OAuthState
from app.services.sdk_token_service import create_sdk_user_token
from app.utils.exceptions import InvalidInputError
from tests.factories import ApiKeyFactory, DeveloperFactory, UserFactory
from tests.utils import api_key_headers, developer_auth_headers

APP_CALLBACK = "openwearables://oauth/callback"


def authorize(
    client: TestClient, redirect_uri: str | None, headers: dict | None = None, user_id: str | None = None
) -> Response:
    params = {"user_id": user_id or str(uuid4())}
    if redirect_uri is not None:
        params["redirect_uri"] = redirect_uri
    headers = headers if headers is not None else api_key_headers(ApiKeyFactory().plain_key)
    return client.get("/api/v1/oauth/garmin/authorize", params=params, headers=headers)


class TestRedirectAllowlist:
    def test_app_callback_is_allowed(self, client: TestClient, db: Session) -> None:
        assert authorize(client, APP_CALLBACK).status_code == 200

    def test_dashboard_origin_is_allowed_on_any_path(self, client: TestClient, db: Session) -> None:
        assert authorize(client, f"{settings.frontend_url}/users/x/pair/success?ok=1").status_code == 200

    def test_other_sites_are_refused(self, client: TestClient, db: Session) -> None:
        response = authorize(client, "https://evil.example.com/collect")

        assert response.status_code == 400
        assert "OAUTH_REDIRECT_ALLOWLIST" in response.json()["detail"]

    def test_lookalike_scheme_path_is_refused(self, client: TestClient, db: Session) -> None:
        assert authorize(client, "openwearables://oauth/other").status_code == 400
        assert authorize(client, "javascript:alert(1)").status_code == 400

    def test_malformed_uri_is_refused(self, client: TestClient, db: Session) -> None:
        assert authorize(client, "http://[::1").status_code == 400

    def test_allowlist_is_configurable(self, client: TestClient, db: Session) -> None:
        with patch.object(settings, "oauth_redirect_allowlist", "acme://cb,https://partner.example.com"):
            assert authorize(client, "acme://cb?x=1").status_code == 200
            assert authorize(client, "https://partner.example.com/done").status_code == 200
            assert authorize(client, APP_CALLBACK).status_code == 400

    def test_no_redirect_uri_still_works(self, client: TestClient, db: Session) -> None:
        assert authorize(client, None).status_code == 200


class TestAuthorizeAuth:
    def test_sdk_token_connects_its_own_user(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        headers = {"Authorization": f"Bearer {create_sdk_user_token('app', str(user.id))}"}

        assert authorize(client, APP_CALLBACK, headers, str(user.id)).status_code == 200

    def test_sdk_token_cannot_connect_another_user(self, client: TestClient, db: Session) -> None:
        headers = {"Authorization": f"Bearer {create_sdk_user_token('app', str(uuid4()))}"}

        assert authorize(client, APP_CALLBACK, headers).status_code == 403

    def test_a_bad_token_is_refused_rather_than_ignored(self, client: TestClient, db: Session) -> None:
        assert authorize(client, APP_CALLBACK, {"Authorization": "Bearer not-a-token"}).status_code == 401

    def test_disabled_provider_cannot_be_connected(self, client: TestClient, db: Session) -> None:
        headers = developer_auth_headers(DeveloperFactory().id)
        client.put("/api/v1/oauth/providers/garmin", json={"is_enabled": False}, headers=headers)

        response = authorize(client, APP_CALLBACK)

        assert response.status_code == 400
        assert "not enabled" in response.json()["detail"]


class TestCallbackRedirects:
    def _start(self, client: TestClient) -> str:
        return authorize(client, APP_CALLBACK).json()["state"]

    def test_provider_error_returns_to_the_app(self, client: TestClient, db: Session) -> None:
        state = self._start(client)

        response = client.get(
            "/api/v1/oauth/garmin/callback",
            params={"state": state, "error": "access_denied", "error_description": "User cancelled"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        target = urlsplit(response.headers["location"])
        assert f"{target.scheme}://{target.netloc}{target.path}" == APP_CALLBACK
        query = parse_qs(target.query)
        assert query["provider"] == ["garmin"]
        assert query["status"] == ["error"]
        assert "User cancelled" in query["message"][0]

    def test_failed_token_exchange_returns_to_the_app(self, client: TestClient, db: Session) -> None:
        state = self._start(client)

        with patch(
            "app.services.providers.templates.base_oauth.BaseOAuthTemplate._exchange_token",
            side_effect=InvalidInputError("Token exchange failed"),
        ):
            response = client.get(
                "/api/v1/oauth/garmin/callback", params={"state": state, "code": "c"}, follow_redirects=False
            )

        query = parse_qs(urlsplit(response.headers["location"]).query)
        assert response.headers["location"].startswith(APP_CALLBACK)
        assert query["status"] == ["error"]

    def test_success_returns_to_the_app(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        done = OAuthState(user_id=user.id, provider="garmin", redirect_uri=APP_CALLBACK)

        with (
            patch(
                "app.services.providers.templates.base_oauth.BaseOAuthTemplate.handle_callback",
                return_value=done,
            ),
            patch("app.api.routes.v1.oauth.start_garmin_full_backfill.delay"),
        ):
            response = client.get(
                "/api/v1/oauth/garmin/callback", params={"state": "s", "code": "c"}, follow_redirects=False
            )

        assert response.status_code == 303
        assert response.headers["location"] == f"{APP_CALLBACK}?provider=garmin&status=success"

    def test_unknown_state_without_redirect_ends_on_the_error_page(self, client: TestClient, db: Session) -> None:
        response = client.get(
            "/api/v1/oauth/garmin/callback", params={"state": "unknown", "code": "c"}, follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"].startswith("/api/v1/oauth/error?message=")
