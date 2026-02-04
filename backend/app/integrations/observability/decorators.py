"""Convenience decorators for custom instrumentation.

These decorators simplify adding custom spans and metrics to your code.
All decorators are no-ops when OTEL_ENABLED=false.
"""

import asyncio
import functools
import time
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from opentelemetry import trace

from app.config import settings
from app.integrations.observability.metrics import get_app_metrics

P = ParamSpec("P")
R = TypeVar("R")


def traced(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Wrap a function in an OpenTelemetry span.

    Creates a span with the function name (or custom name), automatically
    captures exceptions, and sets success/error attributes.

    No-op when OTEL_ENABLED=false.

    Args:
        name: Custom span name. Defaults to "module.function_name"
        attributes: Static attributes to add to the span

    Example:
        @traced()
        def fetch_user_data(user_id: str) -> dict:
            ...

        @traced(name="sync.provider", attributes={"component": "sync"})
        async def sync_provider(provider: str) -> None:
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if not settings.otel_enabled:
            return func

        span_name = name or f"{func.__module__}.{func.__qualname__}"
        tracer = trace.get_tracer(func.__module__)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                try:
                    result = await func(*args, **kwargs)  # type: ignore[misc]
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.record_exception(e)
                    raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator


def metered(
    counter_name: str | None = None,
    histogram_name: str | None = None,
    labels: dict[str, str] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Record metrics for a function.

    Records execution count (counter) and/or duration (histogram).
    No-op when OTEL_ENABLED=false.

    Args:
        counter_name: Name for the call counter. If None, no counter is recorded.
        histogram_name: Name for the duration histogram. If None, no duration is recorded.
        labels: Static labels to add to metrics

    Example:
        @metered(counter_name="app.sync.calls", histogram_name="app.sync.duration")
        def sync_data(provider: str) -> None:
            ...

        @metered(counter_name="app.oauth.attempts", labels={"flow": "authorization"})
        async def start_oauth() -> str:
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if not settings.otel_enabled:
            return func

        # Lazily create meters to avoid import-time issues
        _counter = None
        _histogram = None
        _initialized = False

        def _ensure_initialized() -> None:
            nonlocal _counter, _histogram, _initialized
            if _initialized:
                return
            _initialized = True

            from opentelemetry import metrics

            meter = metrics.get_meter(func.__module__)

            if counter_name:
                _counter = meter.create_counter(
                    name=counter_name,
                    description=f"Call count for {func.__qualname__}",
                    unit="1",
                )
            if histogram_name:
                _histogram = meter.create_histogram(
                    name=histogram_name,
                    description=f"Duration for {func.__qualname__}",
                    unit="s",
                )

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            _ensure_initialized()
            metric_labels = labels or {}

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                if _counter:
                    _counter.add(1, {**metric_labels, "status": "success"})
                return result
            except Exception:
                if _counter:
                    _counter.add(1, {**metric_labels, "status": "error"})
                raise
            finally:
                if _histogram:
                    duration = time.time() - start_time
                    _histogram.record(duration, metric_labels)

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            _ensure_initialized()
            metric_labels = labels or {}

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)  # type: ignore[misc]
                if _counter:
                    _counter.add(1, {**metric_labels, "status": "success"})
                return result
            except Exception:
                if _counter:
                    _counter.add(1, {**metric_labels, "status": "error"})
                raise
            finally:
                if _histogram:
                    duration = time.time() - start_time
                    _histogram.record(duration, metric_labels)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator


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
