"""Optional OpenTelemetry log export (OTEL_ENABLED=true, `otel` extra).

Nothing here imports the OpenTelemetry SDK unless export is enabled. When it is, each
process builds its own LoggerProvider (it is never registered as the global provider)
and one handler that receives:

- stdlib records, through the root logger and, in LOG_FORMAT=legacy, the ``celery`` and
  ``uvicorn`` loggers, which do not propagate to the root there;
- ``log_structured`` calls, handed over directly by ``export_structured`` because they
  never pass through the logging module.

Stdout output is the same with and without export. Exporter endpoint, headers, timeouts
and batching are read by the SDK from the standard OTEL_EXPORTER_OTLP_* / OTEL_BLRP_*
variables.
"""

import atexit
import contextlib
import copy
import dataclasses
import importlib.util
import json
import logging
import os
import re
import threading
import weakref
from collections.abc import Callable, Mapping
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import PurePath
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from app import __version__
from app.config import settings
from app.utils.config_utils import LogFormat

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider, LogRecordProcessor

_log = logging.getLogger(__name__)

_REQUIRED_MODULES = (
    "opentelemetry.sdk",
    "opentelemetry.exporter.otlp.proto.http",
    "opentelemetry.instrumentation.logging",
)
_SUPPORTED_PROTOCOL = "http/protobuf"
REDACTED = "REDACTED"
SHUTDOWN_DEADLINE_SECONDS = 3.0

# An attribute is sensitive when its name, normalized to snake_case ("X-Api-Key" ->
# "x_api_key", "privateKey" -> "private_key"), contains one of these fragments or one of
# the names in OTEL_EXPORT_REDACT_KEYS, or is one of the exact names.
SENSITIVE_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "signature",
    "credential",
    "private_key",
    "bearer",
    "session",
)
SENSITIVE_NAMES = frozenset({"response_body", "body_preview"})

# Attribute names every LogRecord has. Anything else on a record came from `extra=`.
_STANDARD_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1
_UNEXPORTABLE = "<unexportable>"
# Celery formats task results and arguments into its own messages (`succeeded in 0.1s:
# {result}`); these mapping keys are masked before the message is built for export.
_CELERY_PAYLOAD_ARGS = frozenset({"return_value", "args", "kwargs", "argsrepr", "kwargsrepr", "body"})
_CELERY_OMITTED = "<omitted>"

_provider: "LoggerProvider | None" = None
_handler: logging.Handler | None = None


def export_enabled() -> bool:
    return settings.otel_enabled and os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() != "true"


def check_dependencies() -> None:
    """Fail at startup when export is enabled but the `otel` extra is not installed."""
    if not export_enabled():
        return
    missing = []
    for module in _REQUIRED_MODULES:
        try:
            found = importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            found = False
        if not found:
            missing.append(module)
    if missing:
        raise RuntimeError(
            "OTEL_ENABLED=true needs the 'otel' extra (uv sync --extra otel); missing: " + ", ".join(missing)
        )


def _normalized(key: str) -> str:
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key.strip())
    return snake.lower().replace("-", "_").replace(" ", "_")


def _configured_names() -> frozenset[str]:
    return frozenset(_normalized(key) for key in settings.otel_export_redact_keys.split(",") if key.strip())


def _is_sensitive(key: str, configured: frozenset[str]) -> bool:
    name = _normalized(key)
    if name in SENSITIVE_NAMES:
        return True
    return any(fragment in name for fragment in SENSITIVE_FRAGMENTS) or any(part in name for part in configured)


def _fields(value: Any) -> dict[str, Any] | None:
    """Field values of a pydantic model or dataclass, without serializers or deep copies."""
    if isinstance(value, BaseModel):
        return {name: getattr(value, name) for name in type(value).model_fields}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in dataclasses.fields(value)}
    return None


def _export_value(value: Any, configured: frozenset[str]) -> Any:
    """Redact and convert a value to what OpenTelemetry log attributes accept; None drops it."""
    if value is None or isinstance(value, (bool, float, str)):
        return value
    if isinstance(value, int):
        return value if _INT64_MIN <= value <= _INT64_MAX else str(value)
    if isinstance(value, Enum):
        return _export_value(value.value, configured)
    if isinstance(value, (UUID, Decimal, datetime, date, time, timedelta, PurePath)):
        return str(value)
    fields = _fields(value)
    if fields is not None:
        value = fields
    if isinstance(value, dict):
        exported = {}
        for key, item in value.items():
            converted = _export_attribute(str(key), item, configured)
            if converted is not None:
                exported[str(key)] = converted
        return exported
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_export_value(item, configured) for item in value]
        kinds = {type(item) for item in items}
        if len(kinds) <= 1 and kinds <= {bool, int, float, str}:
            return items
        # Lists of maps or mixed types are not valid attribute values.
        return json.dumps(items, default=str)
    # The str() or repr() of other objects, exceptions included, can contain secrets;
    # export the type only.
    return f"<{type(value).__name__}>"


def _export_attribute(key: str, value: Any, configured: frozenset[str]) -> Any:
    if _is_sensitive(key, configured):
        return REDACTED
    try:
        return _export_value(value, configured)
    except Exception:
        return _UNEXPORTABLE


def _from_app_code(record: logging.LogRecord) -> bool:
    return record.name == "app" or record.name.startswith("app.")


class ExportFilter(logging.Filter):
    """Prepare a copy of each record for export; the original stays untouched.

    Returning a new record from a filter (Python 3.12+) changes only what this handler
    sees, so stdout handlers, Sentry and other handlers are not affected.
    """

    def __init__(self, instrumentation_enabled: Callable[[], bool]) -> None:
        super().__init__()
        self._instrumentation_enabled = instrumentation_enabled
        # The handler can sit on a logger and on one of its ancestors at the same time
        # (uvicorn propagates under `fastapi dev`); export each record once.
        self._seen: weakref.WeakSet[logging.LogRecord] = weakref.WeakSet()

    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        if record in self._seen:
            return False
        self._seen.add(record)
        # The exporter's own HTTP calls run with instrumentation suppressed; exporting
        # their log records would feed the exporter with its own output.
        if record.name.startswith("opentelemetry") or not self._instrumentation_enabled():
            return False
        try:
            return self._prepare(record)
        except Exception:
            # Export the record without its extra fields rather than lose it.
            fallback = copy.copy(record)
            for key in [key for key in fallback.__dict__ if key not in _STANDARD_RECORD_KEYS]:
                del fallback.__dict__[key]
            return fallback

    def _prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        configured = _configured_names()
        prepared = copy.copy(record)
        structured = prepared.__dict__.pop("structured", None)
        keep_extras = structured is None and _from_app_code(record)
        if record.name.startswith("celery") and isinstance(record.args, Mapping):
            prepared.args = {
                key: _CELERY_OMITTED if key in _CELERY_PAYLOAD_ARGS else value for key, value in record.args.items()
            }
        for key in [key for key in prepared.__dict__ if key not in _STANDARD_RECORD_KEYS]:
            # Extras of library loggers never appear in the stdout line and can carry
            # payloads: Celery attaches task args, kwargs and return values to its
            # task records, uvicorn a colored copy of the message.
            converted = _export_attribute(key, prepared.__dict__[key], configured) if keep_extras else None
            if converted is None:
                del prepared.__dict__[key]
            else:
                prepared.__dict__[key] = converted
        if structured is not None:
            # log_structured attributes go under one `app.` namespace, so they cannot
            # collide with LogRecord fields or OpenTelemetry semantic conventions.
            fields = {"provider": structured["provider"], **structured["attributes"]}
            for key, value in fields.items():
                converted = _export_attribute(key, value, configured)
                if converted is not None:
                    setattr(prepared, f"app.{key}", converted)
        return prepared


def init_otel(service_name: str, *, processor: "LogRecordProcessor | None" = None) -> None:
    """Start log export for this process. A no-op when export is disabled or already running.

    ``processor`` replaces the batching OTLP pipeline; tests pass an in-memory one.
    """
    global _provider, _handler
    if not export_enabled() or _provider is not None:
        return

    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.instrumentation.logging.handler import LoggingHandler
    from opentelemetry.instrumentation.utils import is_instrumentation_enabled
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import OTELResourceDetector, Resource
    from sentry_sdk.integrations.logging import ignore_logger

    # The exporter and the batch processor log their own failures (collector down, rejected
    # credentials) at ERROR. They stay on stdout but must not become Sentry events.
    ignore_logger("opentelemetry.exporter*")
    ignore_logger("opentelemetry.sdk*")

    for variable in ("OTEL_EXPORTER_OTLP_PROTOCOL", "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL"):
        protocol = os.environ.get(variable)
        if protocol and protocol.strip() != _SUPPORTED_PROTOCOL:
            _log.warning("%s=%s is not supported; logs are exported over %s", variable, protocol, _SUPPORTED_PROTOCOL)

    # Code defaults first, then OTEL_RESOURCE_ATTRIBUTES / OTEL_SERVICE_NAME on top.
    # Resource.create() alone would let the code values win over the environment.
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "open-wearables",
            "service.version": __version__,
            "deployment.environment.name": settings.environment.value,
        }
    ).merge(OTELResourceDetector().detect())

    # shutdown_on_exit=False: shutdown_otel() bounds the time spent flushing instead.
    provider = LoggerProvider(resource=resource, shutdown_on_exit=False)
    provider.add_log_record_processor(processor or BatchLogRecordProcessor(OTLPLogExporter()))

    class _ExportHandler(LoggingHandler):
        def emit(self, record: logging.LogRecord) -> None:
            # Exporting must never raise into the code that logged.
            with contextlib.suppress(Exception):
                super().emit(record)

    level = logging.NOTSET if settings.log_level is None else logging.getLevelNamesMapping()[settings.log_level]
    handler = _ExportHandler(level=level, logger_provider=provider, log_code_attributes=False)
    handler.addFilter(ExportFilter(is_instrumentation_enabled))
    _provider, _handler = provider, handler
    attach_handler()
    atexit.register(shutdown_otel)


def _export_logger_names() -> tuple[str, ...]:
    if settings.log_format is LogFormat.LEGACY:
        return ("", "celery", "uvicorn")
    return ("",)


def attach_handler() -> None:
    """Attach the export handler where it is missing.

    Called again after uvicorn or Celery reset their logger handlers.
    """
    if _handler is None:
        return
    for name in _export_logger_names():
        target = logging.getLogger(name)
        if _handler not in target.handlers:
            target.addHandler(_handler)


def is_export_handler(handler: logging.Handler) -> bool:
    return handler is _handler


def export_structured(
    logger: logging.Logger, levelno: int, message: str, provider: str | None, attributes: dict
) -> None:
    """Export one ``log_structured`` call. Never raises."""
    handler = _handler
    if handler is None or levelno < handler.level:
        return
    with contextlib.suppress(Exception):
        record = logger.makeRecord(logger.name, levelno, "", 0, message, (), None)
        record.structured = {"provider": provider, "attributes": attributes}
        handler.handle(record)


def shutdown_otel(deadline_seconds: float = SHUTDOWN_DEADLINE_SECONDS) -> None:
    """Stop exporting and flush what is queued, waiting at most ``deadline_seconds``.

    The SDK's flush does not honour its own timeout, so it runs in a daemon thread;
    records still queued when the deadline passes are dropped.
    """
    global _provider, _handler
    provider, handler = _provider, _handler
    if provider is None:
        return
    _provider, _handler = None, None
    if handler is not None:
        for name in ("", "celery", "uvicorn"):
            logging.getLogger(name).removeHandler(handler)
    worker = threading.Thread(target=provider.shutdown, name="otel-shutdown", daemon=True)
    worker.start()
    worker.join(deadline_seconds)
