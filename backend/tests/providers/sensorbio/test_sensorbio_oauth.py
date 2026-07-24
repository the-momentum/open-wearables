from unittest.mock import MagicMock

import pytest

from app.schemas.enums import ProviderName
from app.services.providers.sensorbio.oauth import SensorBioOAuth
from app.services.providers.templates.base_oauth import AuthenticationMethod, BaseOAuthTemplate


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


def test_sensorbio_enables_http2_for_oauth_client(
    sensorbio_oauth: SensorBioOAuth,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed_clients: list[dict[str, object]] = []

    def capture_client(**kwargs: object) -> MagicMock:
        constructed_clients.append(kwargs)
        return MagicMock()

    monkeypatch.setattr("app.services.providers.templates.base_oauth.httpx.Client", capture_client)

    assert BaseOAuthTemplate.use_http2 is False
    sensorbio_oauth._http_client()

    assert constructed_clients == [{"http2": True, "timeout": 30.0}]
