"""OpenTelemetry tracing configuration and instrumentation."""

from logging import getLogger

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings

logger = getLogger(__name__)

_tracer: trace.Tracer | None = None
_providers_initialized = False


def init_providers() -> None:
    """Initialize OpenTelemetry trace and metric providers.

    TIMING: Must be called BEFORE FastAPI app creation.

    The reason is that FastAPI's add_middleware() captures provider references
    at call time, not when middleware is instantiated. If providers aren't set
    up yet, the ASGI middleware receives None/proxy references and won't create
    traces or metrics for HTTP requests.

    Safe to call multiple times - will only initialize once.
    """
    global _providers_initialized

    if _providers_initialized:
        return

    if not settings.otel_enabled:
        logger.info("OpenTelemetry disabled")
        return

    logger.info(f"Initializing OpenTelemetry providers for {settings.otel_service_name}")

    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.otel_service_version,
            "deployment.environment": settings.environment.value,
        }
    )

    # Configure trace provider with OTLP exporter
    tracer_provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=settings.otel_exporter_endpoint,
            insecure=True,
        )
    )
    tracer_provider.add_span_processor(processor)
    trace.set_tracer_provider(tracer_provider)

    # Initialize metrics (this sets the global MeterProvider)
    from app.integrations.observability.metrics import init_metrics

    init_metrics()

    _providers_initialized = True
    logger.info("OpenTelemetry providers initialized")


def get_tracer(name: str | None = None) -> trace.Tracer:
    """Get a tracer instance for creating custom spans.

    Args:
        name: Optional tracer name, defaults to module name

    Returns:
        OpenTelemetry Tracer instance
    """
    return trace.get_tracer(name or __name__)


def init_tracing(fastapi_app: object, db_engine: object) -> None:
    """Initialize OpenTelemetry auto-instrumentations.

    Note: Providers should already be initialized via init_providers() before
    the FastAPI app is created. This function sets up the library instrumentations.

    Args:
        fastapi_app: FastAPI application instance
        db_engine: SQLAlchemy engine for database instrumentation
    """
    if not settings.otel_enabled:
        logger.info("OpenTelemetry tracing disabled")
        return

    logger.info("Initializing OpenTelemetry library instrumentations")

    # Auto-instrument SQLAlchemy
    SQLAlchemyInstrumentor().instrument(engine=db_engine)  # type: ignore[arg-type]
    logger.debug("SQLAlchemy instrumentation enabled")

    # Auto-instrument Redis
    RedisInstrumentor().instrument()
    logger.debug("Redis instrumentation enabled")

    # Auto-instrument httpx (used for provider API calls)
    HTTPXClientInstrumentor().instrument()
    logger.debug("HTTPX instrumentation enabled")

    # Celery instrumentation is handled separately in celery/core.py
    # to ensure it's initialized in worker processes

    logger.info("OpenTelemetry tracing initialized successfully")


def init_celery_tracing() -> None:
    """Initialize Celery-specific tracing and metrics for worker processes."""
    if not settings.otel_enabled:
        return

    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    import app.integrations.observability.metrics as metrics_module
    from app.integrations.observability.metrics import AppMetrics

    # Create resource with service information for workers
    resource = Resource.create(
        {
            "service.name": f"{settings.otel_service_name}-worker",
            "service.version": settings.otel_service_version,
            "deployment.environment": settings.environment.value,
        }
    )

    # Configure trace provider
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=settings.otel_exporter_endpoint,
            insecure=True,
        )
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Configure metrics provider for workers
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=settings.otel_exporter_endpoint,
            insecure=True,
        ),
        export_interval_millis=15000,
    )
    metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(metric_provider)

    # Initialize AppMetrics in the worker
    metrics_module._app_metrics = AppMetrics()

    # Instrument Celery
    CeleryInstrumentor().instrument()
    logger.info("Celery tracing and metrics instrumentation enabled")
