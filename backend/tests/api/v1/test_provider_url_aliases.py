"""The cloud path keeps its pre-split URL so registered redirect URIs stay valid."""

import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.constants.provider_urls import from_url_slug
from app.schemas.enums import ProviderName
from tests.factories import ApiKeyFactory


class TestUrlSlugMapping:
    def test_both_slugs_resolve_to_the_cloud_provider(self) -> None:
        assert from_url_slug("google") == ProviderName.GOOGLE_HEALTH.value
        assert from_url_slug("google_health") == ProviderName.GOOGLE_HEALTH.value

    @pytest.mark.parametrize(
        "provider",
        [ProviderName.GARMIN, ProviderName.OURA, ProviderName.APPLE, ProviderName.HEALTH_CONNECT],
    )
    def test_every_other_provider_is_untouched(self, provider: ProviderName) -> None:
        assert from_url_slug(provider.value) == provider.value

    def test_redirect_uri_uses_the_current_slug(self) -> None:
        """What we emit is canonical; the legacy path is only still accepted inbound."""
        uri = settings.oauth_redirect_uri(ProviderName.GOOGLE_HEALTH)
        assert uri.endswith("/api/v1/oauth/google_health/callback")


class TestAuthorizeRoute:
    @pytest.mark.parametrize("slug", ["google", "google_health"])
    def test_both_slugs_reach_the_same_provider(self, client: TestClient, api_v1_prefix: str, slug: str) -> None:
        """Either spelling resolves; without credentials configured both fail identically."""
        response = client.get(
            f"{api_v1_prefix}/oauth/{slug}/authorize",
            params={"user_id": "123e4567-e89b-12d3-a456-426614174000"},
        )
        assert response.status_code != 404

    def test_unknown_provider_is_rejected(self, client: TestClient, api_v1_prefix: str) -> None:
        """400, as the enum-typed parameter returned before the alias landed."""
        response = client.get(
            f"{api_v1_prefix}/oauth/nonsense/authorize",
            params={"user_id": "123e4567-e89b-12d3-a456-426614174000"},
        )
        assert response.status_code == 400

    def test_sdk_provider_cannot_be_authorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """health_connect resolves but has no OAuth, so it is a 400 rather than a 404."""
        response = client.get(
            f"{api_v1_prefix}/oauth/health_connect/authorize",
            params={"user_id": "123e4567-e89b-12d3-a456-426614174000"},
        )
        assert response.status_code == 400


class TestWebhookRoute:
    @pytest.mark.parametrize("slug", ["google", "google_health"])
    def test_both_slugs_reach_the_webhook_handler(self, client: TestClient, api_v1_prefix: str, slug: str) -> None:
        response = client.post(f"{api_v1_prefix}/providers/{slug}/webhooks", json={})
        assert response.status_code not in (404, 501)

    def test_unknown_provider_is_404(self, client: TestClient, api_v1_prefix: str) -> None:
        response = client.post(f"{api_v1_prefix}/providers/nonsense/webhooks", json={})
        assert response.status_code == 404


class TestDataIdentityStaysStrict:
    """URL compatibility must not leak into data filters — a stale ?provider=google
    should surface the split rather than silently return only the cloud half."""

    def test_timeseries_rejects_the_legacy_provider(self, client: TestClient, api_v1_prefix: str) -> None:
        api_key = ApiKeyFactory()
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        response = client.get(
            f"{api_v1_prefix}/users/{user_id}/timeseries",
            headers={"X-Open-Wearables-API-Key": api_key.plain_key},
            params={
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-02T00:00:00Z",
                "provider": "google",
            },
        )
        assert response.status_code == 400
        assert "google_health" in response.text


class TestSyncRoutesTakeTheCurrentSlugOnly:
    """The alias covers what Google holds a copy of — a redirect URI and a subscriber
    endpoint. Our own sync API is not aliased, so it takes the current slug only."""

    def test_sync_rejects_the_legacy_slug(self, client: TestClient, api_v1_prefix: str) -> None:
        api_key = ApiKeyFactory()
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        response = client.post(
            f"{api_v1_prefix}/providers/google/users/{user_id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.plain_key},
        )
        assert response.status_code == 400
        assert "google_health" in response.text

    def test_current_slug_is_the_only_one_the_enum_knows(self) -> None:
        assert ProviderName("google_health") is ProviderName.GOOGLE_HEALTH
        with pytest.raises(ValueError, match="is not a valid ProviderName"):
            ProviderName("google")
