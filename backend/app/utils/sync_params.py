from datetime import datetime
from logging import getLogger
from typing import Any

from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


def build_sync_params(start_date: str | None, end_date: str | None) -> dict[str, Any]:
    """Canonical start_date/end_date kwargs, shared by the sync route and the async Celery task.

    Providers translate these into their own format internally (Suunto's
    epoch-ms `since`, Whoop's `start`/`end`, Fitbit's datetime coercion, ...).
    """
    for label, value in (("start_date", start_date), ("end_date", end_date)):
        if value and not isinstance(value, datetime):
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, AttributeError) as e:
                log_structured(
                    logger,
                    "warning",
                    f"Invalid {label} format: {value}, error: {e}",
                    task="build_sync_params",
                )

    return {"start_date": start_date, "end_date": end_date}
