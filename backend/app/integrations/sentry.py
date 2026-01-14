import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

from app.config import settings


def init_sentry() -> None:
    if settings.SENTRY_ENABLED:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENV,
            traces_sample_rate=settings.SENTRY_SAMPLES_RATE,
            integrations=[
                CeleryIntegration(
                    monitor_beat_tasks=True,
                    propagate_traces=True,
                ),
            ],
        )
