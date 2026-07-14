"""Withings notification routing — single source of truth.

Maps each Withings ``appli`` category we care about to the internal domain the
webhook worker fetches, and derives the per-user subscription set from it.

NOTE: ``appli`` (notification category) and ``meastype`` (measure code) are
distinct numeric namespaces. appli 2 = Temperature; appli 54 = ECG (deferred),
which is unrelated to meastype 54 = SpO2.
"""

from typing import Literal
from urllib.parse import urlencode

from app.config import settings

# The internal fetch domain a notification routes to (closed set).
Domain = Literal["measures", "sleep", "activity_workouts"]

# appli category -> internal domain. Data categories only.
#   1  Body & Weight        -> getmeas
#   2  Temperature          -> getmeas (meastypes 12/71/73, already mapped)
#   4  Blood Pressure & HR  -> getmeas
#   16 Activity (+workouts) -> getactivity + getworkouts
#   44 Sleep                -> getsummary
#   58 Glucose              -> getmeas (119 Glucose mg/dL)
APPLI_DOMAIN: dict[int, Domain] = {
    1: "measures",
    2: "measures",
    4: "measures",
    16: "activity_workouts",
    44: "sleep",
    58: "measures",
}

# Profile change (delete / unlink / update) — handled inline, never subscribed.
PROFILE_CHANGE_APPLI = 46

# Per-user subscription set: routing keys == subscriptions, by construction.
SUBSCRIBED_APPLIS: list[int] = sorted(APPLI_DOMAIN)


def withings_callback_url() -> str:
    """Authenticated callback URL Withings POSTs to and HEAD-probes."""
    # Withings recommends an unguessable token on the exact callback URL:
    # https://developer.withings.com/developer-guide/v3/data-api/notifications/notification-overview/#verify-a-shared-secret
    token = settings.withings_webhook_token
    if token is None or not token.get_secret_value():
        raise ValueError("WITHINGS_WEBHOOK_TOKEN must be configured for Withings notifications")
    query = urlencode({"token": token.get_secret_value()})
    return f"{settings.api_base_url}{settings.api_v1}/providers/withings/webhooks?{query}"
