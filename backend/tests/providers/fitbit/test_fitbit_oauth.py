from unittest.mock import MagicMock

import pytest

from app.schemas.oauth import ProviderName
from app.services.providers.fitbit.oauth import FitbitOAuth
from app.services.providers.templates.base_oauth import AuthenticationMethod


@pytest.fixture
def fitbit_oauth() -> FitbitOAuth:
    user_repo = MagicMock()
    connection_repo = MagicMock()
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
    token_response = MagicMock()
    token_response.model_extra = {"user_id": "ABC123"}
    result = fitbit_oauth._get_provider_user_info(token_response, "some-internal-user-id")
    assert result["user_id"] == "ABC123"
    assert result["username"] is None


def test_get_provider_user_info_handles_none_user_id(fitbit_oauth: FitbitOAuth) -> None:
    token_response = MagicMock()
    token_response.model_extra = {}
    result = fitbit_oauth._get_provider_user_info(token_response, "some-internal-user-id")
    assert result["user_id"] is None
    assert result["username"] is None
