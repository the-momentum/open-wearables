"""Celery tasks: subscribe / revoke a single user's Withings notify subscriptions.

These per-user tasks are dispatched both from the connect lifecycle
(``on_connect``) and, on a live-sync-mode switch, fanned out per active
connection by the generic ``sync_provider_subscriptions`` task.
"""

import logging
from typing import Any
from uuid import UUID

from celery import Task, shared_task

from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory
from app.services.providers.withings.applis import withings_callback_url
from app.services.providers.withings.notify_service import WithingsNotifyService
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


def _withings_notify_context() -> tuple[Any, str, WithingsNotifyService]:
    strategy = ProviderFactory().get_provider("withings")
    assert strategy.oauth is not None
    return strategy, withings_callback_url(), WithingsNotifyService()


def _failed(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in results if r.get("status") == "error"]


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
    strategy, callback_url, service = _withings_notify_context()
    with SessionLocal() as db:
        results = service.subscribe_user(db, UUID(user_id), strategy.connection_repo, strategy.oauth, callback_url)

    failed = _failed(results)
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


@shared_task(
    bind=True,
    name="app.integrations.celery.tasks.withings.subscribe_task.revoke_withings_user",
)
def revoke_withings_user(self: Task, user_id: str) -> dict:
    """Revoke the given user's Withings notify subscriptions.

    Used on a switch to PULL mode (active connection, live token). Disconnect
    uses ``WithingsOAuth.deregister_user`` instead, since the token is nulled there.
    """
    strategy, callback_url, service = _withings_notify_context()
    with SessionLocal() as db:
        results = service.revoke_user(db, UUID(user_id), strategy.connection_repo, strategy.oauth, callback_url)

    failed = _failed(results)
    if failed:
        log_structured(
            logger,
            "error",
            "Withings revoke task had failures, retrying",
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
        "Withings revoke task complete",
        provider="withings",
        user_id=user_id,
        results=results,
    )
    return {"user_id": user_id, "results": results}
