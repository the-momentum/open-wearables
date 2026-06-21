"""Shared Withings request helpers.

Withings' data API is RPC-over-POST: one URL per service, the verb is the
``action`` param, and every response is wrapped in ``{"status": int, "body": {…}}``
with measures encoded as ``value × 10^unit``. Envelope unwrapping, status
handling, pagination and scaling are centralised here; token refresh, 429 retry
and Bearer auth come from ``make_authenticated_request``. Error detection lives
here rather than in the shared client because Withings signals errors through
``status``, not the ``error``/``code`` fields that client inspects.
"""

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.providers.withings import WithingsMeasure
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

WITHINGS_API_BASE_URL = "https://wbsapi.withings.net"

# status 0 = OK, 100 = no data (treat as empty), everything else is an error.
_NO_DATA_STATUS = 100

# Upper bound on pages followed, to contain a pathological never-ending more=1 chain.
_MAX_PAGES = 200


def scale_measure(measure: WithingsMeasure) -> Decimal:
    """Decode a Withings measure: ``actual = value × 10^unit``."""
    return Decimal(measure.value) * (Decimal(10) ** measure.unit)


def withings_request(
    *,
    db: DbSession,
    user_id: UUID,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
    service_path: str,
    action: str,
    params: dict[str, Any],
    api_base_url: str = WITHINGS_API_BASE_URL,
) -> dict[str, Any]:
    """POST an action to a Withings service and return the unwrapped ``body``.

    Raises ``HTTPException`` on a non-zero, non-100 ``status`` (Withings reports
    errors in the envelope, not via the HTTP status or an ``error`` field).
    """
    request_params = {"action": action, **params}
    envelope = make_authenticated_request(
        db=db,
        user_id=user_id,
        connection_repo=connection_repo,
        oauth=oauth,
        api_base_url=api_base_url,
        provider_name="withings",
        endpoint=service_path,
        method="POST",
        params=request_params,
    )

    status = envelope.get("status") if isinstance(envelope, dict) else None
    if status == 0:
        return envelope.get("body", {}) or {}
    if status == _NO_DATA_STATUS:
        return {}

    log_structured(
        logger,
        "error",
        "Withings API error status",
        provider="withings",
        action=action,
        withings_status=status,
        user_id=str(user_id),
    )
    raise HTTPException(status_code=502, detail=f"Withings API error (status={status}) for action={action}")


def paginate(
    *,
    db: DbSession,
    user_id: UUID,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
    service_path: str,
    action: str,
    params: dict[str, Any],
    list_key: str,
    api_base_url: str = WITHINGS_API_BASE_URL,
) -> list[dict[str, Any]]:
    """Follow Withings ``more``/``offset`` pagination, collecting ``body[list_key]``."""
    collected: list[dict[str, Any]] = []
    offset = 0
    for _ in range(_MAX_PAGES):
        page_params = {**params}
        if offset:
            page_params["offset"] = offset
        body = withings_request(
            db=db,
            user_id=user_id,
            connection_repo=connection_repo,
            oauth=oauth,
            service_path=service_path,
            action=action,
            params=page_params,
            api_base_url=api_base_url,
        )
        collected.extend(body.get(list_key, []) or [])
        if not body.get("more"):
            return collected
        next_offset = int(body.get("offset") or 0)
        if next_offset <= offset:
            # Non-advancing offset would refetch the same page indefinitely.
            log_structured(
                logger,
                "warning",
                "Withings pagination made no progress; stopping",
                provider="withings",
                action=action,
                offset=next_offset,
                user_id=str(user_id),
            )
            return collected
        offset = next_offset

    log_structured(
        logger,
        "warning",
        "Withings pagination hit page cap; results may be truncated",
        provider="withings",
        action=action,
        max_pages=_MAX_PAGES,
        user_id=str(user_id),
    )
    return collected
