import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.types import Event, Hint

from app.config import settings

# railway noise that ends up in huge amounts on sentry
_CONNECTION_NOISE_FRAGMENTS = (
    "Timeout connecting to server",
    "Cannot connect to redis",
    "Connection error: Timeout",
)


def _is_connection_noise(text: str) -> bool:
    return any(fragment in text for fragment in _CONNECTION_NOISE_FRAGMENTS)


def _before_send(event: Event, hint: Hint) -> Event | None:
    exc_info = hint.get("exc_info")
    if exc_info and exc_info[1] is not None and _is_connection_noise(str(exc_info[1])):
        return None

    logentry = event.get("logentry") or {}
    message = str(logentry.get("formatted") or logentry.get("message") or event.get("message") or "")
    if _is_connection_noise(message):
        return None

    return event


def init_sentry() -> None:
    if settings.SENTRY_ENABLED:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENV,
            server_name=settings.SENTRY_SERVER_NAME,
            traces_sample_rate=settings.SENTRY_SAMPLES_RATE,
            before_send=_before_send,
            integrations=[
                CeleryIntegration(
                    monitor_beat_tasks=True,
                    propagate_traces=True,
                ),
            ],
        )
