from unittest.mock import patch

import pytest
from pydantic import SecretStr

from app.config import settings
from app.services.providers.withings.applis import (
    APPLI_DOMAIN,
    PROFILE_CHANGE_APPLI,
    SUBSCRIBED_APPLIS,
    withings_callback_url,
)


def test_subscribed_applis_are_derived_from_routing() -> None:
    # Subscription set == routing keys, so they can never drift.
    assert sorted(APPLI_DOMAIN) == SUBSCRIBED_APPLIS
    assert SUBSCRIBED_APPLIS == [1, 2, 4, 16, 44, 58]


def test_appli_domains() -> None:
    assert APPLI_DOMAIN[2] == "measures"  # temperature
    assert APPLI_DOMAIN[58] == "measures"  # glucose
    assert APPLI_DOMAIN[16] == "activity_workouts"
    assert APPLI_DOMAIN[44] == "sleep"
    assert PROFILE_CHANGE_APPLI == 46
    assert 62 not in APPLI_DOMAIN
    # ECG is deliberately NOT routed (deferred — no core-model home).
    assert 54 not in APPLI_DOMAIN


def test_callback_url_is_https_webhooks_path() -> None:
    with patch.object(settings, "withings_webhook_token", SecretStr("a token/+")):
        url = withings_callback_url()
    assert url.endswith("/api/v1/providers/withings/webhooks?token=a+token%2F%2B")


def test_callback_url_requires_webhook_token() -> None:
    with (
        patch.object(settings, "withings_webhook_token", None),
        pytest.raises(ValueError, match="WITHINGS_WEBHOOK_TOKEN"),
    ):
        withings_callback_url()
