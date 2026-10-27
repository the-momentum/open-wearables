from enum import StrEnum

_PREFIX = "app.integrations.celery.tasks"


class CeleryTask(StrEnum):
    """Registered Celery task names. Must stay import-free so any layer can use it."""

    RUN_DAILY_ARCHIVAL = f"{_PREFIX}.archival_task.run_daily_archival"
    BACKFILL_DATA_TYPE_COVERAGE = f"{_PREFIX}.backfill_data_type_coverage_task.backfill_data_type_coverage"
    CLOSE_STALE_SYNC_RUNS = f"{_PREFIX}.close_stale_sync_runs_task.close_stale_sync_runs"
    DELETE_USER_WEBHOOK_PAYLOADS = f"{_PREFIX}.delete_user_webhook_payloads_task.delete_user_webhook_payloads"
    EMIT_WEBHOOK_EVENT = f"{_PREFIX}.emit_webhook_event_task.emit_webhook_event"
    DISPATCH_EXTENSION_EVENTS = f"{_PREFIX}.extension_events_task.dispatch_extension_events"
    FILL_MISSING_RESILIENCE_SCORES = f"{_PREFIX}.fill_missing_resilience_scores_task.fill_missing_resilience_scores"
    FILL_MISSING_SLEEP_SCORES = f"{_PREFIX}.fill_missing_sleep_scores_task.fill_missing_sleep_scores"
    FINALIZE_STALE_SLEEPS = f"{_PREFIX}.finalize_stale_sleep_task.finalize_stale_sleeps"
    GARMIN_START_FULL_BACKFILL = f"{_PREFIX}.garmin.backfill_task.start_full_backfill"
    GARMIN_TRIGGER_NEXT_PENDING_TYPE = f"{_PREFIX}.garmin.backfill_task.trigger_next_pending_type"
    GARMIN_CHECK_TRIGGERED_TIMEOUT = f"{_PREFIX}.garmin.backfill_timeout.check_triggered_timeout"
    GARMIN_TRIGGER_BACKFILL_FOR_TYPE = f"{_PREFIX}.garmin.backfill_trigger.trigger_backfill_for_type"
    SYNC_ALL_USERS = f"{_PREFIX}.periodic_sync_task.sync_all_users"
    PROCESS_AWS_UPLOAD = f"{_PREFIX}.process_aws_upload_task.process_aws_upload"
    COMPLETE_AND_PROCESS_AWS_UPLOAD = f"{_PREFIX}.process_aws_upload_task.complete_and_process_aws_upload"
    PROCESS_SDK_UPLOAD = f"{_PREFIX}.process_sdk_upload_task.process_sdk_upload"
    PROCESS_XML_UPLOAD = f"{_PREFIX}.process_xml_upload_task.process_xml_upload"
    RECONCILE_PROVIDER_WEBHOOKS = f"{_PREFIX}.provider_webhooks_task.reconcile_provider_webhooks"
    REFRESH_DASHBOARD_TOTAL_DATA_POINTS = f"{_PREFIX}.refresh_dashboard_stats_task.refresh_dashboard_total_data_points"
    RENEW_OURA_WEBHOOKS = f"{_PREFIX}.renew_oura_webhooks_task.renew_oura_webhooks"
    GENERATE_SEED_DATA = f"{_PREFIX}.seed_data_task.generate_seed_data"
    RETRY_STRAVA_STREAM_INGEST = f"{_PREFIX}.strava_stream_retry_task.retry_strava_stream_ingest"
    SEND_INVITATION_EMAIL = f"{_PREFIX}.send_email_task.send_invitation_email_task"
    SYNC_VENDOR_DATA = f"{_PREFIX}.sync_vendor_data_task.sync_vendor_data"
    SEND_TELEMETRY_PING = f"{_PREFIX}.telemetry_task.send_telemetry_ping"
    PROCESS_WEBHOOK_PUSH = f"{_PREFIX}.webhook_push_task.process_webhook_push"
    WITHINGS_SYNC_USER_SUBSCRIPTIONS = f"{_PREFIX}.withings.notify_sync_task.sync_user_subscriptions"


class CeleryQueue(StrEnum):
    """Queues the workers consume. A task sent to any other name waits in a queue nobody reads."""

    DEFAULT = "default"
    SDK_SYNC = "sdk_sync"
    GARMIN_SYNC = "garmin_sync"
    WEBHOOK_SYNC = "webhook_sync"
    XML_SYNC = "xml_sync"
