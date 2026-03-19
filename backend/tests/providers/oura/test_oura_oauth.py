"""Tests for OuraOAuth."""

import pytest

from app.schemas import AuthenticationMethod
from app.services.providers.oura.oauth import OuraOAuth
from app.services.providers.oura.strategy import OuraStrategy


class TestOuraOAuth:
    """Test suite for OuraOAuth."""

    @pytest.fixture
    def oauth(self) -> OuraOAuth:
        strategy = OuraStrategy()
        return strategy.oauth

    def test_authorize_url(self, oauth: OuraOAuth) -> None:
        assert oauth.endpoints.authorize_url == "https://cloud.ouraring.com/oauth/authorize"

    def test_token_url(self, oauth: OuraOAuth) -> None:
        assert oauth.endpoints.token_url == "https://api.ouraring.com/oauth/token"

    def test_no_pkce(self, oauth: OuraOAuth) -> None:
        assert oauth.use_pkce is False

    def test_auth_method_body(self, oauth: OuraOAuth) -> None:
        assert oauth.auth_method == AuthenticationMethod.BODY

    def test_credentials_have_redirect_uri(self, oauth: OuraOAuth) -> None:
        creds = oauth.credentials
        assert "oura" in creds.redirect_uri

    def test_credentials_have_scope(self, oauth: OuraOAuth) -> None:
        creds = oauth.credentials
        assert "personal" in creds.default_scope
        assert "heartrate" in creds.default_scope

    def test_provider_name(self, oauth: OuraOAuth) -> None:
        assert oauth.provider_name == "oura"

    def test_api_base_url(self, oauth: OuraOAuth) -> None:
        assert oauth.api_base_url == "https://api.ouraring.com"
