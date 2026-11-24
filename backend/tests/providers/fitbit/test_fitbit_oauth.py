from unittest.mock import create_autospec

import pytest

from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.enums import ProviderName
from app.schemas.model_crud.credentials import OAuthTokenResponse
from app.services.providers.fitbit.oauth import FitbitOAuth
from app.services.providers.templates.base_oauth import AuthenticationMethod


@pytest.fixture
def fitbit_oauth() -> FitbitOAuth:
    user_repo = create_autospec(UserRepository, instance=True)
    connection_repo = create_autospec(UserConnectionRepository, instance=True)
    return FitbitOAuth(
        user_repo=user_repo,
        connection_repo=connection_repo,
        provider_name=ProviderName.FITBIT.value,
        api_base_url="https://api.fitbit.com",
    )


def test_endpoints(fitbit_oauth: FitbitOAuth) -> None:
    endpoints = fitbit_oauth.endpoints
    assert endpoints.authorize_url == "https://www.fitbit.com/oauth2/authorize"
    assert endpoints.token_url == "https://api.fitbit.com/oauth2/token"


def test_uses_pkce(fitbit_oauth: FitbitOAuth) -> None:
    assert fitbit_oauth.use_pkce is True


def test_uses_basic_auth(fitbit_oauth: FitbitOAuth) -> None:
    assert fitbit_oauth.auth_method == AuthenticationMethod.BASIC_AUTH


def test_get_provider_user_info_extracts_user_id(fitbit_oauth: FitbitOAuth) -> None:
    token_response = OAuthTokenResponse(access_token="at", token_type="Bearer", expires_in=3600, user_id="ABC123")
    result = fitbit_oauth._get_provider_user_info(token_response, "some-internal-user-id")
    assert result["user_id"] == "ABC123"
    assert result["username"] is None


def test_get_provider_user_info_handles_none_user_id(fitbit_oauth: FitbitOAuth) -> None:
    token_response = OAuthTokenResponse(access_token="at", token_type="Bearer", expires_in=3600)
    result = fitbit_oauth._get_provider_user_info(token_response, "some-internal-user-id")
    assert result["user_id"] is None
    assert result["username"] is None
