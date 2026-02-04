"""OpenTelemetry-compliant structured logging with trace correlation."""

import logging
import sys
import traceback
from typing import Any

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from pythonjsonlogger import jsonlogger

from app.config import settings

# Mapping Python log levels to OTel severity numbers (1-24 scale)
# See: https://opentelemetry.io/docs/specs/otel/logs/data-model/#severity-fields
SEVERITY_NUMBER_MAP = {
    logging.DEBUG: 5,  # DEBUG
    logging.INFO: 9,  # INFO
    logging.WARNING: 13,  # WARN
    logging.ERROR: 17,  # ERROR
    logging.CRITICAL: 21,  # FATAL
}


class OTelStructuredFormatter(jsonlogger.JsonFormatter):
    """JSON formatter following OpenTelemetry semantic conventions.

    Produces logs compatible with:
    - OpenTelemetry Log Data Model
    - Loki/Grafana ingestion
    - Trace correlation (trace_id, span_id)
    """

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        # Timestamp (ISO 8601 format)
        log_record["timestamp"] = self.formatTime(record, self.datefmt)

        # Severity per OTel spec (both number and text)
        log_record["severity_number"] = SEVERITY_NUMBER_MAP.get(record.levelno, 9)
        log_record["severity_text"] = record.levelname

        # Body (the actual log message)
        log_record["body"] = record.getMessage()

        # Resource attributes (service identification)
        log_record["resource"] = {
            "service.name": settings.otel_service_name,
            "service.version": settings.otel_service_version,
            "deployment.environment": settings.environment.value,
        }

        # Code location attributes (OTel semantic conventions)
        log_record["attributes"] = {
            "code.filepath": record.pathname,
            "code.function": record.funcName,
            "code.lineno": record.lineno,
            "code.namespace": record.name,
        }

        # Trace context correlation (if available)
        span = trace.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            if ctx.is_valid:
                log_record["trace_id"] = format(ctx.trace_id, "032x")
                log_record["span_id"] = format(ctx.span_id, "016x")
                log_record["trace_flags"] = ctx.trace_flags

        # Exception attributes (OTel semantic conventions)
        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, exc_tb = record.exc_info
            log_record["attributes"].update(
                {
                    "exception.type": exc_type.__name__ if exc_type else "Unknown",
                    "exception.message": str(exc_value) if exc_value else "",
                    "exception.stacktrace": "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
                    "exception.escaped": False,
                }
            )

        # Merge extra attributes from log call (e.g., logger.info("msg", extra={...}))
        reserved_keys = {
            "message",
            "asctime",
            "args",
            "msg",
            "exc_info",
            "exc_text",
            "levelname",
            "levelno",
            "name",
            "pathname",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "stack_info",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in reserved_keys and not key.startswith("_"):
                log_record["attributes"][key] = value

        # Clean up redundant fields from base formatter
        for key in ["levelname", "levelno", "name", "pathname", "lineno", "funcName", "message", "asctime"]:
            log_record.pop(key, None)


def configure_logging() -> None:
    """Configure structured logging with OpenTelemetry correlation.

    This sets up:
    - JSON-formatted logs to stdout (for container environments)
    - Trace ID/Span ID correlation in every log entry
    - OTel semantic conventions for log attributes
    - OTLP log export (when otel_enabled=True)
    """
    # Determine log level
    log_level = getattr(logging, settings.otel_log_level.upper(), logging.INFO)

    # Create JSON formatter
    formatter = OTelStructuredFormatter(
        fmt="%(timestamp)s %(severity_text)s %(name)s %(body)s",
        datefmt="%Y-%m-%dT%H:%M:%S.%fZ",
    )

    # Console handler (stdout for container log aggregation)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Reduce noise from verbose libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)

    # OTLP log export (when enabled)
    if settings.otel_enabled:
        resource = Resource.create(
            {
                "service.name": settings.otel_service_name,
                "service.version": settings.otel_service_version,
                "deployment.environment": settings.environment.value,
            }
        )

        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                OTLPLogExporter(
                    endpoint=settings.otel_exporter_endpoint,
                    insecure=True,
                )
            )
        )
        set_logger_provider(logger_provider)

        # Add OTLP handler
        otel_handler = LoggingHandler(logger_provider=logger_provider)
        otel_handler.setLevel(log_level)
        root_logger.addHandler(otel_handler)

    logging.getLogger(__name__).info(
        "Structured logging configured",
        extra={"otel_enabled": settings.otel_enabled},
    )
