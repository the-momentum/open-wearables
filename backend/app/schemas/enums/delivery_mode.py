from enum import Enum


class DeliveryMode(str, Enum):
    """High-level data delivery mode label for a provider.

    Intended for UI display and human-readable summaries only (e.g. provider
    badges in the dashboard). For runtime capability checks use
    ``ProviderCapabilities`` from ``app.services.providers.base_strategy``.
    """

    POLL = "poll"
    """We periodically poll the provider's REST API (Whoop, Ultrahuman)."""

    PUSH_FULL = "push_full"
    """Provider pushes the full data payload to our webhook (Garmin)."""

    PUSH_NOTIFY = "push_notify"
    """Provider sends a lightweight notification; we fetch the data via REST
    (Oura, Strava, Fitbit, Polar, Suunto)."""

    SDK_PUSH = "sdk_push"
    """Mobile client pushes data through our SDK endpoint (Apple, Samsung,
    Google). No cloud server involved on the provider side."""
