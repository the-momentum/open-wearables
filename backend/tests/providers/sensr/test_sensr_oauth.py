from unittest.mock import MagicMock

import pytest

from app.schemas.oauth import ProviderName
from app.services.providers.sensr.oauth import SensrOAuth
from app.services.providers.templates.base_oauth import AuthenticationMethod


@pytest.fixture
def sensr_oauth() -> SensrOAuth:
    return SensrOAuth(
        user_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name=ProviderName.SENSR.value,
        api_base_url="https://api.getsensr.io",
    )


def test_endpoints(sensr_oauth: SensrOAuth) -> None:
    endpoints = sensr_oauth.endpoints
    assert endpoints.authorize_url == "https://auth.getsensr.io/authorize"
    assert endpoints.token_url == "https://auth.getsensr.io/token"


def test_uses_body_auth(sensr_oauth: SensrOAuth) -> None:
    assert sensr_oauth.auth_method == AuthenticationMethod.BODY


def test_uses_no_pkce(sensr_oauth: SensrOAuth) -> None:
    assert sensr_oauth.use_pkce is False
