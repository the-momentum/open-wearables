"""Helper functions for recording metrics.

All functions are no-ops when OTEL_ENABLED=false.
"""

from app.config import settings
from app.integrations.observability.metrics import get_app_metrics


def record_task_started(task_name: str) -> None:
    """Record that a Celery task has started. No-op when OTEL disabled."""
    if not settings.otel_enabled:
        return
    metrics = get_app_metrics()
    if metrics:
        metrics.celery_tasks_started.add(1, {"task": task_name})


def record_task_completed(task_name: str, state: str, duration: float) -> None:
    """Record Celery task completion with duration. No-op when OTEL disabled."""
    if not settings.otel_enabled:
        return
    metrics = get_app_metrics()
    if metrics:
        metrics.celery_task_duration.record(duration, {"task": task_name})
        metrics.celery_tasks_completed.add(1, {"task": task_name, "state": state})


def record_task_failed(task_name: str, error_type: str) -> None:
    """Record a Celery task failure. No-op when OTEL disabled."""
    if not settings.otel_enabled:
        return
    metrics = get_app_metrics()
    if metrics:
        metrics.celery_tasks_failed.add(1, {"task": task_name, "error_type": error_type})


def record_metric(
    metric_name: str,
    value: int | float = 1,
    labels: dict[str, str] | None = None,
) -> None:
    """Record a counter metric. No-op when OTEL disabled.

    Args:
        metric_name: Attribute name on AppMetrics (e.g., "oauth_attempts")
        value: Value to add (default 1)
        labels: Labels/attributes dict

    Example:
        record_metric("oauth_attempts", labels={"provider": "garmin"})
        record_metric("workouts_synced", 5, {"provider": "polar"})
    """
    if not settings.otel_enabled:
        return

    metrics = get_app_metrics()
    if not metrics:
        return

    metric = getattr(metrics, metric_name, None)
    if metric is None:
        return

    if labels:
        metric.add(value, labels)
    else:
        metric.add(value)


def record_histogram(
    metric_name: str,
    value: float,
    labels: dict[str, str] | None = None,
) -> None:
    """Record a histogram metric (e.g., duration). No-op when OTEL disabled.

    Args:
        metric_name: Attribute name on AppMetrics (e.g., "provider_sync_duration")
        value: Value to record
        labels: Labels/attributes dict

    Example:
        record_histogram("provider_sync_duration", 2.5, {"provider": "garmin"})
    """
    if not settings.otel_enabled:
        return

    metrics = get_app_metrics()
    if not metrics:
        return

    metric = getattr(metrics, metric_name, None)
    if metric is None:
        return

    if labels:
        metric.record(value, labels)
    else:
        metric.record(value)
