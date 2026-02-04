"""Unified observability setup for FastAPI applications.

This module provides simplified APIs for setting up observability,
hiding the complexity of initialization order and provider configuration.
"""

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.config import settings
from app.integrations.observability.logging import configure_logging
from app.integrations.observability.tracing import init_providers, init_tracing


def ensure_providers_initialized() -> None:
    """Ensure OpenTelemetry providers are initialized.

    Safe to call multiple times - will only initialize once.
    Must be called BEFORE FastAPI app creation to ensure middleware
    can access the correct providers.

    Example:
        ensure_providers_initialized()
        api = FastAPI(...)
    """
    init_providers()


def add_observability_middleware(app: FastAPI) -> None:
    """Add OpenTelemetry ASGI middleware to trace HTTP requests.

    Must be called AFTER app creation but BEFORE the app starts.
    Typically called at module level right after FastAPI() instantiation.

    Args:
        app: FastAPI application instance
    """
    if not settings.otel_enabled:
        return

    from opentelemetry import metrics, trace
    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

    app.add_middleware(
        OpenTelemetryMiddleware,
        tracer_provider=trace.get_tracer_provider(),
        meter_provider=metrics.get_meter_provider(),
    )


def create_observed_lifespan(
    engine: object,
    additional_startup: Callable[[], None] | None = None,
    additional_shutdown: Callable[[], None] | None = None,
) -> Callable[[FastAPI], AsyncIterator[None]]:
    """Create a lifespan context manager with observability auto-instrumentation.

    Initializes SQLAlchemy, Redis, httpx, and Celery instrumentation on startup.

    Args:
        engine: SQLAlchemy engine for database instrumentation
        additional_startup: Optional callback to run after observability setup
        additional_shutdown: Optional callback to run before shutdown

    Returns:
        Async context manager suitable for FastAPI lifespan parameter

    Example:
        from app.integrations.observability import (
            ensure_providers_initialized,
            add_observability_middleware,
            create_observed_lifespan,
        )

        ensure_providers_initialized()
        api = FastAPI(lifespan=create_observed_lifespan(engine, init_sentry))
        add_observability_middleware(api)
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        init_tracing(app, engine)
        if additional_startup:
            additional_startup()
        yield
        if additional_shutdown:
            additional_shutdown()

    return lifespan
