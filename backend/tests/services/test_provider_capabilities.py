"""ProviderCapabilities invariants enforced in __post_init__."""

import pytest

from app.services.providers.base_strategy import ProviderCapabilities


def test_per_user_subscriptions_requires_webhook_ping() -> None:
    with pytest.raises(ValueError, match="webhook_per_user_subscriptions requires webhook_ping"):
        ProviderCapabilities(rest_pull=True, webhook_per_user_subscriptions=True)


def test_per_user_subscriptions_excludes_registration_api() -> None:
    # webhook_registration_api itself is fine; combining the two delivery models is not.
    with pytest.raises(ValueError, match="mutually exclusive"):
        ProviderCapabilities(
            rest_pull=True,
            webhook_ping=True,
            webhook_per_user_subscriptions=True,
            webhook_registration_api=True,
        )


def test_withings_shaped_capabilities_are_valid() -> None:
    caps = ProviderCapabilities(rest_pull=True, webhook_ping=True, webhook_per_user_subscriptions=True)
    assert caps.webhook_per_user_subscriptions is True
