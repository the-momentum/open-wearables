"""Withings RPC-over-POST adapter: envelopes, pagination, scaling and provider errors.

Withings exposes one endpoint per service and names the operation in an
``action`` form field, answering with a ``{status, body}`` envelope where
``status != 0`` is a failure on HTTP 200. This unwraps that for the four
callers; the HTTP transport, token refresh and HTTP 429 retries stay in
``api_client``, while the envelope's own throttle status is retried here.
"""

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.providers.withings import WithingsMeasure
from app.services.providers.api_client import MAX_RETRIES, RETRY_BASE_DELAY, make_authenticated_request
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

WITHINGS_API_BASE_URL = "https://wbsapi.withings.net"

# Withings' throttle signal, reported in the envelope rather than the HTTP status.
_RATE_LIMIT_STATUS = 601

_AUTHENTICATION_STATUSES = {100, 101, 102, 200, 401}

# Upper bound on pages followed, to contain a pathological never-ending more=1 chain.
_MAX_PAGES = 200


class WithingsAPIError(HTTPException):
    """Map Withings status 601 to HTTP 429 and other provider failures to 5xx."""

    def __init__(self, withings_status: int | None, action: str) -> None:
        self.withings_status = withings_status
        self.action = action
        if withings_status == _RATE_LIMIT_STATUS:
            status_code = 429
        elif withings_status in _AUTHENTICATION_STATUSES:
            status_code = 401
        else:
            status_code = 502
        detail = f"Withings API error (status={withings_status}) for action={action}"
        super().__init__(status_code=status_code, detail=detail)


class WithingsPaginationError(HTTPException):
    """Withings reported another page but did not provide a usable continuation."""

    def __init__(self, action: str, reason: str) -> None:
        self.action = action
        self.reason = reason
        super().__init__(status_code=502, detail=f"Incomplete Withings pagination for action={action}: {reason}")


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

    Raises ``HTTPException`` on a non-zero ``status``. Withings answers HTTP 200 with the
    status in the envelope next to an ``error`` message, so the shared client must not raise
    on that message; a throttle (601) is retried with the backoff it applies to HTTP 429.
    """
    request_params = {"action": action, **params}
    status: Any = None
    for attempt in range(MAX_RETRIES + 1):
        envelope = make_authenticated_request(
            db=db,
            user_id=user_id,
            connection_repo=connection_repo,
            oauth=oauth,
            api_base_url=api_base_url,
            provider_name="withings",
            endpoint=service_path,
            method="POST",
            form_data=request_params,
            check_body_errors=False,
        )
        status = envelope.get("status") if isinstance(envelope, dict) else None
        if status == 0:
            return envelope.get("body", {}) or {}
        if status != _RATE_LIMIT_STATUS or attempt == MAX_RETRIES:
            break
        backoff_delay = RETRY_BASE_DELAY * (2**attempt)
        log_structured(
            logger,
            "warning",
            "Withings throttled the request, retrying",
            provider="withings",
            action=action,
            attempt=attempt + 1,
            max_retries=MAX_RETRIES,
            backoff_delay=backoff_delay,
            user_id=str(user_id),
        )
        time.sleep(backoff_delay)
    log_structured(
        logger,
        "error",
        "Withings API error status",
        provider="withings",
        action=action,
        withings_status=status,
        user_id=str(user_id),
    )
    raise WithingsAPIError(withings_status=status if isinstance(status, int) else None, action=action)


@dataclass(frozen=True)
class PaginatedResult:
    """Return collected rows with first-page context outside the result list."""

    rows: list[dict[str, Any]]
    envelope: dict[str, Any]


def _walk_pages(
    *,
    db: DbSession,
    user_id: UUID,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
    service_path: str,
    action: str,
    params: dict[str, Any],
    api_base_url: str,
) -> Iterator[dict[str, Any]]:
    """Yield each page body, following Withings ``more``/``offset`` pagination."""
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
        yield body
        if not body.get("more"):
            return
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
            raise WithingsPaginationError(action, "offset did not advance")
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
    raise WithingsPaginationError(action, f"exceeded {_MAX_PAGES} pages")


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
) -> PaginatedResult:
    """Follow Withings ``more``/``offset`` pagination, collecting ``body[list_key]``."""
    collected: list[dict[str, Any]] = []
    envelope: dict[str, Any] = {}
    for page, body in enumerate(
        _walk_pages(
            db=db,
            user_id=user_id,
            connection_repo=connection_repo,
            oauth=oauth,
            service_path=service_path,
            action=action,
            params=params,
            api_base_url=api_base_url,
        )
    ):
        if page == 0:
            envelope = {key: value for key, value in body.items() if key != list_key}
        collected.extend(body.get(list_key, []) or [])
    return PaginatedResult(collected, envelope)


def paginate_mapping(
    *,
    db: DbSession,
    user_id: UUID,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
    service_path: str,
    action: str,
    params: dict[str, Any],
    map_key: str,
    api_base_url: str = WITHINGS_API_BASE_URL,
) -> dict[str, Any]:
    """Same pagination for an action whose rows arrive keyed by id rather than as a list.

    ``getintradayactivity`` answers with ``body.series`` as an object keyed by the start
    epoch of each slice, which ``paginate`` would flatten into its keys.
    """
    collected: dict[str, Any] = {}
    for body in _walk_pages(
        db=db,
        user_id=user_id,
        connection_repo=connection_repo,
        oauth=oauth,
        service_path=service_path,
        action=action,
        params=params,
        api_base_url=api_base_url,
    ):
        collected.update(body.get(map_key) or {})
    return collected
