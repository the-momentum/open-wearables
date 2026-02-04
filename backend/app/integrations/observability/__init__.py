"""OpenTelemetry observability integration for traces, logs, and metrics.

QUICK START:
    from app.integrations.observability import (
        ensure_providers_initialized,
        add_observability_middleware,
        create_observed_lifespan,
    )

    ensure_providers_initialized()
    api = FastAPI(lifespan=create_observed_lifespan(engine))
    add_observability_middleware(api)

CUSTOM INSTRUMENTATION:
    from app.integrations.observability import traced, metered, record_metric

    @traced()
    def my_function(): ...

    @metered(counter_name="app.calls")
    async def my_async_function(): ...

    record_metric("oauth_attempts", labels={"provider": "garmin"})

INITIALIZATION ORDER (if not using simplified API):
    1. Call init_providers() BEFORE creating FastAPI app
    2. Call init_observability() during FastAPI lifespan startup
"""

from app.integrations.observability.decorators import (
    metered,
    record_histogram,
    record_metric,
    record_task_completed,
    record_task_failed,
    record_task_started,
    traced,
)
from app.integrations.observability.logging import configure_logging
from app.integrations.observability.metrics import get_app_metrics, init_metrics
from app.integrations.observability.setup import (
    add_observability_middleware,
    create_observed_lifespan,
    ensure_providers_initialized,
)
from app.integrations.observability.tracing import get_tracer, init_providers, init_tracing

__all__ = [
    # Simplified API (recommended)
    "ensure_providers_initialized",
    "add_observability_middleware",
    "create_observed_lifespan",
    # Decorators and helpers
    "traced",
    "metered",
    "record_metric",
    "record_histogram",
    "record_task_started",
    "record_task_completed",
    "record_task_failed",
    # Lower-level API
    "configure_logging",
    "init_tracing",
    "init_metrics",
    "init_providers",
    "get_tracer",
    "get_app_metrics",
]


def init_observability(fastapi_app: object, db_engine: object) -> None:
    """Initialize observability instrumentations during app startup.

    This should be called during the FastAPI lifespan startup.
    Note: Providers should already be initialized via init_providers() or
    ensure_providers_initialized() before the FastAPI app was created.

    Args:
        fastapi_app: FastAPI application instance
        db_engine: SQLAlchemy engine for database instrumentation
    """
    configure_logging()
    init_tracing(fastapi_app, db_engine)
