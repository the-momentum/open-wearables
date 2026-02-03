"""OpenTelemetry observability integration for traces, logs, and metrics."""

from app.integrations.observability.logging import configure_logging
from app.integrations.observability.metrics import get_app_metrics, init_metrics
from app.integrations.observability.tracing import get_tracer, init_tracing, init_providers

__all__ = [
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
    Note: Providers should already be initialized at module level via init_providers().

    Args:
        fastapi_app: FastAPI application instance
        db_engine: SQLAlchemy engine for database instrumentation
    """
    configure_logging()
    init_tracing(fastapi_app, db_engine)
