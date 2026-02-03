"""OpenTelemetry metrics for application monitoring."""

from logging import getLogger

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from app.config import settings

logger = getLogger(__name__)


def init_metrics() -> None:
    """Initialize OpenTelemetry metrics with OTLP export."""
    global _app_metrics

    if not settings.otel_enabled:
        logger.info("OpenTelemetry metrics disabled")
        return

    logger.info(f"Initializing OpenTelemetry metrics for {settings.otel_service_name}")

    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.version": settings.otel_service_version,
        "deployment.environment": settings.environment.value,
    })

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=settings.otel_exporter_endpoint,
            insecure=True,
        ),
        export_interval_millis=15000,  # Export every 15 seconds
    )

    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)

    # Initialize AppMetrics after provider is set
    _app_metrics = AppMetrics()

    logger.info("OpenTelemetry metrics initialized")


class AppMetrics:
    """Application-specific metrics for Open Wearables.

    Usage:
        from app.integrations.observability import app_metrics

        # Count user creation
        app_metrics.users_created.add(1)

        # Record sync duration
        with app_metrics.record_sync_duration("garmin"):
            perform_sync()

        # Track provider errors
        app_metrics.provider_sync_errors.add(1, {"provider": "garmin", "error_type": "api_error"})
    """

    def __init__(self) -> None:
        meter = metrics.get_meter(__name__)

        # User metrics
        self.users_created = meter.create_counter(
            name="app.users.created",
            description="Total number of users created",
            unit="1",
        )

        # Provider sync metrics
        self.provider_syncs = meter.create_counter(
            name="app.provider.syncs",
            description="Total provider sync operations",
            unit="1",
        )

        self.provider_sync_errors = meter.create_counter(
            name="app.provider.sync_errors",
            description="Provider sync failures",
            unit="1",
        )

        self.provider_sync_duration = meter.create_histogram(
            name="app.provider.sync_duration",
            description="Time to sync provider data",
            unit="s",
        )

        # Data metrics
        self.workouts_synced = meter.create_counter(
            name="app.workouts.synced",
            description="Total workouts synced from providers",
            unit="1",
        )

        self.activities_synced = meter.create_counter(
            name="app.activities.synced",
            description="Total activities synced from providers",
            unit="1",
        )

        # Connection metrics
        self.provider_connections = meter.create_up_down_counter(
            name="app.provider.connections",
            description="Active provider connections",
            unit="1",
        )

        # OAuth metrics
        self.oauth_attempts = meter.create_counter(
            name="app.oauth.attempts",
            description="OAuth flow attempts",
            unit="1",
        )

        self.oauth_successes = meter.create_counter(
            name="app.oauth.successes",
            description="Successful OAuth completions",
            unit="1",
        )

        self.oauth_failures = meter.create_counter(
            name="app.oauth.failures",
            description="Failed OAuth attempts",
            unit="1",
        )

        # API metrics
        self.api_requests = meter.create_counter(
            name="app.api.requests",
            description="Total API requests",
            unit="1",
        )

        # Celery task metrics
        self.celery_tasks_started = meter.create_counter(
            name="app.celery.tasks_started",
            description="Celery tasks started",
            unit="1",
        )

        self.celery_tasks_completed = meter.create_counter(
            name="app.celery.tasks_completed",
            description="Celery tasks completed successfully",
            unit="1",
        )

        self.celery_tasks_failed = meter.create_counter(
            name="app.celery.tasks_failed",
            description="Celery tasks that failed",
            unit="1",
        )

        self.celery_task_duration = meter.create_histogram(
            name="app.celery.task_duration",
            description="Celery task execution duration",
            unit="s",
        )


# Global metrics instance (initialized by init_metrics)
_app_metrics: AppMetrics | None = None


def get_app_metrics() -> AppMetrics | None:
    """Get the global AppMetrics instance.

    Returns None if metrics are not enabled or not yet initialized.
    Always check for None before using.
    """
    return _app_metrics
