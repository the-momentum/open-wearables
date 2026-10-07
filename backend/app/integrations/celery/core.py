import logging
import ssl
import sys
from logging import Formatter, LogRecord, StreamHandler, getLogger
from typing import Any, cast

from celery import Celery, signals
from celery import current_app as current_celery_app
from celery.schedules import crontab

from app.config import settings
from app.extensions import collect_beat_schedule, collect_event_handlers, events, get_active_extensions
from app.integrations.otel import init_otel, shutdown_otel
from app.services import raw_payload_storage
from app.utils.config_utils import LogFormat
from app.utils.logging_setup import configure_logging

_WEBHOOK_TASK = "emit_webhook_event_task.emit_webhook_event"


class _WebhookTraceFilter(logging.Filter):
    """Drop celery.app.trace success/retry records for the webhook emit task.

    Failures (ERROR and above) are always passed through.
    """

    def filter(self, record: LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            return True
        msg = record.getMessage()
        return _WEBHOOK_TASK not in msg


@signals.setup_logging.connect
def setup_celery_logging(**kwargs) -> None:
    """
    Configure Celery logging to use stdout instead of stderr.

    Some platforms convert stderr logs to level.error automatically, so we must use stdout
    to ensure platforms correctly identify log levels from JSON structured logs.

    This signal is called when Celery sets up its logging configuration. With
    LOG_FORMAT=json or text the Celery logger has no handler of its own and its records
    go through the root handler instead, so every line shares one format.
    """
    # Get Celery's logger
    celery_logger = getLogger("celery")

    # Remove existing handlers that might use stderr
    celery_logger.handlers.clear()
    celery_logger.setLevel(logging.INFO)

    if settings.log_format is LogFormat.LEGACY:
        # Create a handler that uses stdout
        stdout_handler = StreamHandler(sys.stdout)
        stdout_handler.setFormatter(
            Formatter(
                "[%(asctime)s - %(name)s] (%(levelname)s) %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        celery_logger.addHandler(stdout_handler)
        celery_logger.propagate = False
    else:
        celery_logger.propagate = True

    # celery.app.trace logs "Task ... succeeded in Xs: {result}" at INFO for
    # every task execution.  Suppress those lines only for the high-frequency
    # webhook emit task to avoid log spam while keeping traces for all others.
    getLogger("celery.app.trace").addFilter(_WebhookTraceFilter())

    configure_logging()


_worker_service_name = "open-wearables-worker"


def _worker_service_name_for(hostname: str | None) -> str:
    # scripts/start/worker.sh names its workers io@%h and cpu@%h.
    prefix = (hostname or "").split("@", 1)[0]
    return f"open-wearables-worker-{prefix}" if prefix and prefix != "celery" else "open-wearables-worker"


def _uses_prefork(pool_cls: Any) -> bool:
    from celery.concurrency import get_implementation
    from celery.concurrency.prefork import TaskPool as PreforkPool

    try:
        # Resolves aliases such as "prefork" and "processes" and "module:Class" paths.
        pool = get_implementation(pool_cls) if isinstance(pool_cls, str) else pool_cls
    except Exception:
        return False
    return isinstance(pool, type) and issubclass(pool, PreforkPool)


@signals.worker_init.connect
def init_worker_log_export(sender: Any, **kwargs) -> None:
    """Start OTel log export in thread and solo pool workers.

    Prefork workers start it in each child instead (worker_process_init): the export
    thread of a provider created here would not survive the fork.
    """
    global _worker_service_name
    _worker_service_name = _worker_service_name_for(getattr(sender, "hostname", None))
    if not _uses_prefork(getattr(sender, "pool_cls", "")):
        init_otel(_worker_service_name)


@signals.worker_process_init.connect
def init_worker_process_log_export(**kwargs) -> None:
    init_otel(_worker_service_name)


@signals.worker_process_shutdown.connect
def stop_worker_process_log_export(**kwargs) -> None:
    # Prefork children leave through os._exit, which skips atexit handlers.
    shutdown_otel()


@signals.worker_shutdown.connect
def stop_worker_log_export(**kwargs) -> None:
    shutdown_otel()


@signals.beat_init.connect
def init_beat_log_export(**kwargs) -> None:
    init_otel("open-wearables-beat")


@signals.worker_ready.connect
def enqueue_startup_telemetry_ping(sender: Any, **kwargs) -> None:
    """Send the "startup" telemetry ping once the worker can reach the broker.

    Multiple workers may each enqueue this; the 12h debounce in
    TelemetryService turns the extras into no-ops.
    """
    if not settings.telemetry_enabled:
        return
    try:
        sender.app.send_task(
            "app.integrations.celery.tasks.telemetry_task.send_telemetry_ping",
            kwargs={"event": "startup"},
            queue="default",
        )
    except Exception:
        getLogger(__name__).debug("Could not enqueue startup telemetry ping", exc_info=True)


@signals.worker_init.connect
def init_raw_payload_storage(**kwargs) -> None:
    """Initialize raw payload storage in celery workers."""
    raw_payload_storage.configure(
        settings.raw_payload_storage,
        settings.raw_payload_max_size_bytes,
        s3_bucket=settings.raw_payload_bucket,
        s3_prefix=settings.raw_payload_s3_prefix,
        s3_endpoint_url=settings.raw_payload_s3_endpoint_url,
        fit_files_enabled=settings.store_fit_files,
        transport_enabled=settings.sdk_payload_s3_offload,
    )


def create_celery() -> Celery:
    celery_app = cast(Celery, current_celery_app)
    celery_app.conf.update(
        broker_url=settings.redis_url,
        result_backend=settings.redis_url,
        # Detect and drop half-open TCP connections to Redis. Behind a NAT (e.g. Docker ->
        # ElastiCache) the conntrack entry can expire and the server-side RST never reaches
        # the worker, so it hangs forever on a dead socket and stops consuming — which is
        # what let the queue grow until Redis hit maxmemory. Keepalive probes surface the
        # dead socket so the connection is recycled instead of blocking indefinitely.
        broker_transport_options={
            "socket_keepalive": True,
            # Linux TCP socket-option ints: 4=TCP_KEEPIDLE (60s idle before probing),
            # 5=TCP_KEEPINTVL (10s between probes), 6=TCP_KEEPCNT (3 failed probes -> drop).
            "socket_keepalive_options": {4: 60, 5: 10, 6: 3},
            # redis-py periodic health check: PING idle pooled connections so a dead one is
            # replaced rather than handed to the next publish/consume.
            "health_check_interval": 30,
        },
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_default_queue="default",
        task_default_exchange="default",
        result_expires=3 * 24 * 3600,
        control_queue_ttl=300,
        control_queue_expires=300,
        task_queues={
            "default": {},
            "sdk_sync": {},
            "garmin_sync": {},
            "webhook_sync": {},
            "xml_sync": {},
        },
        task_routes={
            "app.integrations.celery.tasks.process_sdk_upload_task.process_sdk_upload": {"queue": "sdk_sync"},
            "app.integrations.celery.tasks.process_aws_upload_task.process_aws_upload": {"queue": "xml_sync"},
            "app.integrations.celery.tasks.process_aws_upload_task.complete_and_process_aws_upload": {
                "queue": "xml_sync"
            },
            "app.integrations.celery.tasks.process_xml_upload_task.process_xml_upload": {"queue": "xml_sync"},
        },
    )

    # rediss:// alone isn't enough for Celery — the broker/result transports read
    # their TLS requirements from these dicts. Required for ElastiCache (TLS).
    if settings.redis_ssl:
        ssl_options = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
        celery_app.conf.broker_use_ssl = ssl_options
        celery_app.conf.redis_backend_use_ssl = ssl_options

    extensions = get_active_extensions()
    celery_app.autodiscover_tasks(
        ["app.integrations.celery.tasks", "app.integrations.celery.tasks.garmin"]
        + [package for extension in extensions for package in extension.celery_task_packages]
    )

    celery_app.conf.beat_schedule = {
        "sync-all-users-periodic": {
            "task": "app.integrations.celery.tasks.periodic_sync_task.sync_all_users",
            "schedule": float(settings.sync_interval_seconds),
            "args": (),  # No args - task calculates date range dynamically
            "kwargs": {"user_id": None},
        },
        "finalize-stale-sleeps-periodic": {
            "task": "app.integrations.celery.tasks.finalize_stale_sleep_task.finalize_stale_sleeps",
            "schedule": float(settings.sleep_sync_interval_seconds),
            "args": (),
            "kwargs": {},
        },
        "close-stale-sync-runs": {
            "task": "app.integrations.celery.tasks.close_stale_sync_runs_task.close_stale_sync_runs",
            "schedule": float(settings.sync_run_sweep_interval_seconds),
            "args": (),
            "kwargs": {},
        },
        "renew-oura-webhooks-monthly": {
            "task": "app.integrations.celery.tasks.renew_oura_webhooks_task.renew_oura_webhooks",
            "schedule": crontab(day_of_month=1, hour=0, minute=0),  # 1st of each month at 00:00 UTC
            "args": (),
            "kwargs": {},
        },
    }

    if settings.data_lifecycle_enabled:
        celery_app.conf.beat_schedule["run-daily-archival"] = {
            "task": "app.integrations.celery.tasks.archival_task.run_daily_archival",
            "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 UTC
            "args": (),
            "kwargs": {},
        }

    if settings.ow_scores_enabled:
        celery_app.conf.beat_schedule["fill-missing-sleep-scores"] = {
            "task": "app.integrations.celery.tasks.fill_missing_sleep_scores_task.fill_missing_sleep_scores",
            "schedule": float(settings.sleep_score_interval_seconds),
            "args": (),
            "kwargs": {},
        }
        celery_app.conf.beat_schedule["fill-missing-resilience-scores"] = {
            "task": "app.integrations.celery.tasks.fill_missing_resilience_scores_task.fill_missing_resilience_scores",
            "schedule": float(settings.resilience_score_interval_seconds),
            "args": (),
            "kwargs": {},
        }

    if settings.telemetry_enabled:
        # Hourly due-check, not an hourly ping: the task delivers at most one
        # ping per 24h (see TelemetryService) and the hourly cadence doubles as
        # the retry mechanism after failed deliveries.
        celery_app.conf.beat_schedule["send-telemetry-ping"] = {
            "task": "app.integrations.celery.tasks.telemetry_task.send_telemetry_ping",
            "schedule": settings.telemetry_beat_interval_seconds,
            "args": (),
            "kwargs": {"event": "daily"},
        }

    event_handlers = collect_event_handlers()
    events.register(event_handlers)
    if event_handlers:
        celery_app.conf.beat_schedule["dispatch-extension-events"] = {
            "task": "app.integrations.celery.tasks.extension_events_task.dispatch_extension_events",
            "schedule": float(settings.extension_event_sweep_interval_seconds),
        }

    celery_app.conf.beat_schedule.update(collect_beat_schedule(reserved=set(celery_app.conf.beat_schedule)))

    return celery_app
