"""Celery task: subscribe a single user to Withings notifications after connect."""

import logging
from uuid import UUID

from celery import Task, shared_task

from app.config import settings
from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory
from app.services.providers.withings.notify_service import WithingsNotifyService
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="app.integrations.celery.tasks.withings.subscribe_task.subscribe_withings_user",
)
def subscribe_withings_user(self: Task, user_id: str) -> dict:
    """Subscribe the given user to the Withings notify categories.

    Retries (up to 3×, 60s apart) while any appli subscription fails. Withings'
    ``subscribe`` is idempotent for an already-subscribed (callbackurl, appli)
    pair, so retrying the whole set is safe.
    """
    strategy = ProviderFactory().get_provider("withings")
    assert strategy.oauth is not None
    callback_url = f"{settings.api_base_url}/api/v1/providers/withings/webhooks"
    service = WithingsNotifyService()
    with SessionLocal() as db:
        results = service.subscribe_user(db, UUID(user_id), strategy.connection_repo, strategy.oauth, callback_url)

    failed = [r for r in results if r.get("status") == "error"]
    if failed:
        log_structured(
            logger,
            "error",
            "Withings subscription task had failures, retrying",
            provider="withings",
            user_id=user_id,
            failed_appli=[r.get("appli") for r in failed],
            attempt=self.request.retries,
            max_retries=3,
        )
        raise self.retry(countdown=60, max_retries=3)

    log_structured(
        logger,
        "info",
        "Withings subscription task complete",
        provider="withings",
        user_id=user_id,
        results=results,
    )
    return {"user_id": user_id, "results": results}
