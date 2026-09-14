"""Withings strategy wiring and lifecycle hook."""

from app.services.providers.withings.strategy import WithingsStrategy


def test_capabilities_declare_pull_with_per_user_webhook_subscriptions() -> None:
    caps = WithingsStrategy().capabilities

    assert caps.rest_pull is True
    assert caps.webhook_ping is True
    assert caps.webhook_registration_api is True
    assert caps.webhook_subscription_per_user is True


def test_webhook_components_are_wired_and_the_mode_is_admin_configurable() -> None:
    strategy = WithingsStrategy()

    assert strategy.webhooks is not None
    assert strategy.webhook_service is not None
    assert strategy.live_sync_configurable is True
