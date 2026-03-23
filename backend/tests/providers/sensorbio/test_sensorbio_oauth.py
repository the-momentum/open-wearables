from unittest.mock import MagicMock

import pytest

from app.schemas.oauth import ProviderName
from app.services.providers.sensorbio.oauth import SensorBioOAuth
from app.services.providers.templates.base_oauth import AuthenticationMethod


@pytest.fixture
def sensorbio_oauth() -> SensorBioOAuth:
    return SensorBioOAuth(
        user_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name=ProviderName.SENSORBIO.value,
        api_base_url="https://api.sensorbio.com",
    )


def test_endpoints(sensorbio_oauth: SensorBioOAuth) -> None:
    endpoints = sensorbio_oauth.endpoints
    assert endpoints.authorize_url == "https://auth.sensorbio.com/authorize"
    assert endpoints.token_url == "https://auth.sensorbio.com/token"


def test_uses_body_auth(sensorbio_oauth: SensorBioOAuth) -> None:
    assert sensorbio_oauth.auth_method == AuthenticationMethod.BODY


def test_uses_no_pkce(sensorbio_oauth: SensorBioOAuth) -> None:
    assert sensorbio_oauth.use_pkce is False
