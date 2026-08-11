"""Tests for deployment-level provider API base URL overrides."""

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.fitbit.strategy import FitbitStrategy
from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.google.health_api.webhook_service import _subscribers_url
from app.services.providers.google.strategy import GoogleStrategy
from app.services.providers.oura.strategy import OuraStrategy
from app.services.providers.oura.webhook_service import _oura_webhook_api_url
from app.services.providers.polar.strategy import PolarStrategy
from app.services.providers.polar.webhook_service import _polar_api_url
from app.services.providers.sensorbio.strategy import SensorBioStrategy
from app.services.providers.strava.strategy import StravaStrategy
from app.services.providers.strava.webhook_service import strava_webhook_service
from app.services.providers.suunto.strategy import SuuntoStrategy
from app.services.providers.ultrahuman.strategy import UltrahumanStrategy
from app.services.providers.whoop.strategy import WhoopStrategy

StrategyFactory = Callable[[], BaseProviderStrategy]

PROVIDERS: tuple[tuple[StrategyFactory, str, str], ...] = (
    (FitbitStrategy, "fitbit_api_base_url", "https://api.fitbit.com"),
    (GarminStrategy, "garmin_api_base_url", "https://apis.garmin.com"),
    (GoogleStrategy, "google_api_base_url", "https://health.googleapis.com"),
    (OuraStrategy, "oura_api_base_url", "https://api.ouraring.com"),
    (PolarStrategy, "polar_api_base_url", "https://www.polaraccesslink.com"),
    (SensorBioStrategy, "sensorbio_api_base_url", "https://api.sensorbio.com"),
    (StravaStrategy, "strava_api_base_url", "https://www.strava.com"),
    (SuuntoStrategy, "suunto_api_base_url", "https://cloudapi.suunto.com"),
    (UltrahumanStrategy, "ultrahuman_api_base_url", "https://partner.ultrahuman.com/api/partners/v1"),
    (WhoopStrategy, "whoop_api_base_url", "https://api.prod.whoop.com/developer"),
)


@pytest.mark.parametrize(("strategy_factory", "setting_name", "default_url"), PROVIDERS)
def test_provider_uses_default_api_base_url(
    strategy_factory: StrategyFactory,
    setting_name: str,
    default_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, setting_name, None)

    assert strategy_factory().api_base_url == default_url


@pytest.mark.parametrize(("strategy_factory", "setting_name", "_default_url"), PROVIDERS)
def test_provider_propagates_api_base_url_override(
    strategy_factory: StrategyFactory,
    setting_name: str,
    _default_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override = "http://provider-gateway.local/custom/prefix/"
    monkeypatch.setattr(settings, setting_name, override)

    strategy = strategy_factory()

    assert strategy.api_base_url == override.rstrip("/")
    for component_name in ("oauth", "workouts", "data_247"):
        component = getattr(strategy, component_name)
        if component is not None and hasattr(component, "api_base_url"):
            assert component.api_base_url == override.rstrip("/")


def test_provider_api_base_url_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OURA_API_BASE_URL", "https://gateway.example.com/oura/")

    configured = Settings(_env_file=None, secret_key="test-secret")

    assert configured.resolve_provider_api_base_url("oura", "https://api.ouraring.com") == (
        "https://gateway.example.com/oura"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@gateway.example.com/oura",
        "https://gateway.example.com/oura?tenant=example",
        "https://gateway.example.com/oura#api",
    ],
)
def test_provider_api_base_url_rejects_ambiguous_urls(url: str) -> None:
    with pytest.raises(ValidationError, match="provider API base URLs must not contain"):
        Settings(_env_file=None, secret_key="test-secret", oura_api_base_url=url)


def test_webhook_services_use_provider_api_base_url_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_api_base_url", "https://gateway.example.com/google")
    monkeypatch.setattr(settings, "google_project_id", "123456")
    monkeypatch.setattr(settings, "oura_api_base_url", "https://gateway.example.com/oura")
    monkeypatch.setattr(settings, "polar_api_base_url", "https://gateway.example.com/polar")
    monkeypatch.setattr(settings, "strava_api_base_url", "https://gateway.example.com/strava")

    assert _subscribers_url().startswith("https://gateway.example.com/google/")
    assert _oura_webhook_api_url() == "https://gateway.example.com/oura/v2/webhook/subscription"
    assert _polar_api_url() == "https://gateway.example.com/polar"
    assert strava_webhook_service.api_current_url == "https://gateway.example.com/strava/api/v3"


def test_oura_token_endpoint_uses_api_base_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oura_api_base_url", "https://gateway.example.com/oura")

    strategy = OuraStrategy()

    assert strategy.oauth is not None
    assert strategy.oauth.endpoints.token_url == "https://gateway.example.com/oura/oauth/token"
