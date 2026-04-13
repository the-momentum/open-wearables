from app.services.providers.garmin.backfill_config import (
    BACKFILL_DATA_TYPES as GARMIN_BACKFILL_DATA_TYPES,
)
from app.services.providers.garmin.backfill_state import (
    get_backfill_status as get_garmin_backfill_status,
)
from app.services.providers.garmin.backfill_state import (
    get_pending_types as get_garmin_pending_types,
)
from app.services.providers.garmin.backfill_state import (
    is_cancelled as is_garmin_backfill_cancelled,
)
from app.services.providers.garmin.backfill_state import (
    reset_type_status as reset_garmin_type_status,
)
from app.services.providers.garmin.backfill_state import (
    set_cancel_flag as set_garmin_cancel_flag,
)

from .archival_task import run_daily_archival
from .emit_webhook_event_task import emit_webhook_event
from .fill_missing_sleep_scores_task import fill_missing_sleep_scores
from .finalize_stale_sleep_task import finalize_stale_sleeps
from .garmin_backfill_task import (
    start_full_backfill as start_garmin_full_backfill,
)
from .garmin_backfill_task import (
    trigger_next_pending_type as trigger_garmin_next_pending_type,
)
from .garmin_backfill_timeout import (
    check_triggered_timeout as check_garmin_triggered_timeout,
)
from .garmin_backfill_trigger import (
    trigger_backfill_for_type as trigger_garmin_backfill_for_type,
)
from .garmin_gc_task import gc_stuck_backfills
from .periodic_sync_task import sync_all_users
from .process_aws_upload_task import process_aws_upload
from .process_sdk_upload_task import process_sdk_upload
from .process_xml_upload_task import process_xml_upload
from .seed_data_task import generate_seed_data
from .send_email_task import send_invitation_email_task
from .sync_vendor_data_task import sync_vendor_data

__all__ = [
    # Garmin backfill (30-day webhook-based sync)
    "GARMIN_BACKFILL_DATA_TYPES",
    "check_garmin_triggered_timeout",
    "get_garmin_backfill_status",
    "get_garmin_pending_types",
    "reset_garmin_type_status",
    "start_garmin_full_backfill",
    "trigger_garmin_backfill_for_type",
    "trigger_garmin_next_pending_type",
    "set_garmin_cancel_flag",
    "is_garmin_backfill_cancelled",
    "gc_stuck_backfills",
    # Archival
    "run_daily_archival",
    # Sleep score calculation
    "fill_missing_sleep_scores",
    # Other tasks
    "finalize_stale_sleeps",
    "process_sdk_upload",
    "process_aws_upload",
    "process_xml_upload",
    "sync_vendor_data",
    "sync_all_users",
    "generate_seed_data",
    "send_invitation_email_task",
    # Outgoing webhooks
    "emit_webhook_event",
]
