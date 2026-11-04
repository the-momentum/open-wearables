from collections.abc import Iterable
from typing import Any, ClassVar
from uuid import UUID

from fastapi import status
from fastapi.exceptions import RequestValidationError
from psycopg import Error as PsycopgError
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.errors import IntegrityError as PsycopgIntegrityError
from sqlalchemy.exc import IntegrityError, StatementError

# ORM writes raise SQLAlchemy's wrapper; writes on the raw psycopg connection (COPY) raise psycopg's own
INTEGRITY_ERRORS = (IntegrityError, PsycopgIntegrityError)


# The code of an error that has none of its own: its status' name. Spelled out, not HTTPStatus.name, which
# Python renamed for 413 and 422 in 3.13: codes are part of the API contract.
STATUS_CODE_NAMES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "CONTENT_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "UNPROCESSABLE_CONTENT",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
    501: "NOT_IMPLEMENTED",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def status_code_name(status_code: int) -> str:
    return STATUS_CODE_NAMES.get(status_code, f"HTTP_{status_code}")


class AppError(Exception):
    """Base of the domain errors raised by services and repositories.

    Raise a subclass instead of ``HTTPException``: the global handler in ``app.main`` turns
    ``status_code``, ``code`` and ``detail`` into the response, and Celery tasks can catch it by type.
    ``code`` is part of the API contract: a status' base class has the status' name, the one
    an ``HTTPException`` with that status gets, and a subclass a code of its own only where
    a client can act on the difference.
    """

    status_code: ClassVar[int] = status.HTTP_500_INTERNAL_SERVER_ERROR
    # Stable across releases: sync history and webhooks report it, clients branch on it.
    code: ClassVar[str] = "INTERNAL_ERROR"
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(self, detail: str, extensions: dict[str, Any] | None = None) -> None:
        self.detail = detail
        # Extra members of the problem body (RFC 9457 extensions), for what a client acts on by value
        self.extensions = extensions or {}
        super().__init__(detail)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # A class that sets a status and no code of its own gets the status' name, never its parent's code
        if "status_code" in cls.__dict__ and "code" not in cls.__dict__:
            cls.code = status_code_name(cls.status_code)

    @property
    def is_client_error(self) -> bool:
        return 400 <= self.status_code < 500


class InvalidInputError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    headers = {"WWW-Authenticate": "Bearer"}


class WebhookVerificationError(AuthenticationError):
    """A provider callback failed verification (signature, token): no bearer scheme to advertise."""

    code = "WEBHOOK_VERIFICATION_FAILED"
    headers = None


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT


class ResourceNotFoundError(NotFoundError):
    def __init__(self, entity_name: str, entity_id: int | UUID | None = None):
        self.entity_name = entity_name
        if entity_id:
            super().__init__(f"{entity_name.capitalize()} with ID: {entity_id} not found.")
        else:
            super().__init__(f"{entity_name.capitalize()} not found.")


class UnsupportedProviderError(InvalidInputError):
    code = "UNSUPPORTED_PROVIDER"

    def __init__(self, provider: str, operation: str = "this operation"):
        super().__init__(f"Provider '{provider}' does not support {operation}.")


class InvalidCursorError(InvalidInputError):
    code = "INVALID_CURSOR"

    def __init__(self, cursor: str):
        super().__init__(f"Invalid cursor format: '{cursor}'. Expected 'timestamp|id'.")


class ReconcileWindowTooLargeError(InvalidInputError):
    """A source_selection=reconcile page would merge more days on the fly than the server allows."""

    code = "RECONCILE_TOO_MANY_DAYS"

    def __init__(self, days: int, max_days: int, queued: bool):
        self.days, self.max_days, self.queued = days, max_days, queued
        # The numbers as members, so a client sizes its next page by them rather than by parsing a sentence;
        # queued: the rollup will store these days, not a promise of when, as its budget decides.
        super().__init__(
            "source_selection=reconcile would merge more days on the fly than allowed for one page; "
            "lower `limit` or narrow the range.",
            {"days": days, "max_days": max_days, "queued": queued},
        )


class DatetimeParseError(InvalidInputError, ValueError):
    code = "INVALID_DATETIME"

    def __init__(self, value: str):
        super().__init__(f"Invalid datetime format: '{value}'. Expected ISO 8601 format or Unix timestamp.")


class UpstreamError(AppError):
    """A service we call failed: a provider API, object storage.

    Not a bug in our code, so unlike other 5xx errors the client gets this status and
    ``detail`` instead of a bare 500. Still reported to Sentry: an outage breaks syncs, and
    Sentry is where we hear about it first. Only a provider's answer about a user's state
    stays out (``is_provider_state_error``).
    """

    status_code = status.HTTP_502_BAD_GATEWAY


class ServiceUnavailableError(UpstreamError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class ConfigurationError(AppError):
    """A setting the request needs is missing or rejected (storage bucket, credentials).

    The deployment's to fix, not the client's: the client gets 503 with the detail, but
    unlike an UpstreamError the failure is ours, not the called service's.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "CONFIGURATION_ERROR"


def unknown_provider(value: str, loc: tuple[str, ...], allowed: Iterable[str]) -> RequestValidationError:
    """An unknown provider slug, answered like a ``ProviderName`` parameter FastAPI validated: a 422
    ``VALIDATION_ERROR`` pointing at ``loc``, so a typo gets one code whatever the route."""
    expected = ", ".join(f"'{slug}'" for slug in sorted(allowed))
    return RequestValidationError(
        [{"loc": loc, "msg": f"Input should be one of {expected}", "type": "enum", "input": value}]
    )


def provider_label(provider: str) -> str:
    return provider.replace("_", " ").title()


# Provider 4xx answers that describe a user's or a resource's state (a revoked grant, a scope not
# granted, data that isn't there, a duplicate, a throttle): only the user or time can change them.
# Any other 4xx means the provider rejected the request itself, which is most likely our bug.
_STATE_STATUSES = frozenset({401, 403, 404, 409, 410, 412, 429})


class ProviderError(UpstreamError):
    """A provider API call failed.

    ``upstream_status`` is the provider's HTTP status, None when no response came back.
    ``upstream_body`` is what the provider answered: for logs and for callers that branch
    on it, never for ``detail``, which the client sees.
    ``request_rejected``: the provider refused the request itself (a 400, a 422), most likely
    because we built it wrong, so unlike a 4xx about the user's state it is reported to Sentry.
    Derived from ``upstream_status`` unless the caller knows better, e.g. from a status in the body.
    """

    code = "PROVIDER_ERROR"

    def __init__(
        self,
        provider: str,
        detail: str | None = None,
        *,
        upstream_status: int | None = None,
        upstream_body: str | None = None,
        request_rejected: bool | None = None,
    ) -> None:
        self.provider = provider
        self.upstream_status = upstream_status
        self.upstream_body = upstream_body
        if request_rejected is None:
            request_rejected = (
                upstream_status is not None and 400 <= upstream_status < 500 and upstream_status not in _STATE_STATUSES
            )
        self.request_rejected = request_rejected
        if detail is None:
            label = provider_label(provider)
            detail = (
                f"{label} API error (status {upstream_status})"
                if upstream_status is not None
                else f"{label} API request failed"
            )
        super().__init__(detail)


class ProviderRateLimitError(ProviderError):
    """The provider kept throttling us after the client's own backoff."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "PROVIDER_RATE_LIMITED"


class ProviderAuthRejectedError(ProviderError):
    """The provider rejected a token we just refreshed (or can't refresh): often a data type the user did not
    consent to. Not proof the grant is dead, so the connection stays; ``api_client`` revokes it, raising
    ``ReauthRequiredError``, only after a day of nothing but rejections."""

    code = "PROVIDER_AUTH_REJECTED"

    def __init__(self, provider: str, detail: str | None = None, *, upstream_body: str | None = None) -> None:
        super().__init__(provider, detail, upstream_status=401, upstream_body=upstream_body)


def is_provider_state_error(exc: BaseException | None) -> bool:
    """A provider's answer about a user's or a resource's state (data that isn't there, a
    throttle we couldn't wait out): nothing we can fix, logged as a warning, kept out of Sentry.

    Every other upstream failure is reported: an outage (a 5xx, no response) breaks syncs for
    every user of the provider, and a request it rejected (``ProviderError.request_rejected``)
    most likely means it changed its API. Sentry groups both per provider and status.
    """
    if isinstance(exc, ProviderRateLimitError):
        # Withings throttles in the body of an HTTP 200: the type says it, not the status.
        return True
    return isinstance(exc, ProviderError) and not exc.request_rejected and exc.upstream_status in _STATE_STATUSES


class ProviderConnectionError(AppError):
    """The user's connection to the provider can't be used: no request to the provider
    succeeds, and no retry helps, until the user connects again."""

    def __init__(self, provider: str, detail: str) -> None:
        self.provider = provider
        super().__init__(detail)


class ProviderNotConnectedError(ProviderConnectionError, NotFoundError):
    code = "PROVIDER_NOT_CONNECTED"

    def __init__(self, provider: str) -> None:
        super().__init__(provider, f"User is not connected to {provider_label(provider)}.")


class ProviderTokenUnavailableError(ProviderConnectionError, InvalidInputError):
    """The connection has no API token, e.g. an SDK-based provider."""

    code = "PROVIDER_TOKEN_UNAVAILABLE"

    def __init__(self, provider: str) -> None:
        super().__init__(provider, f"No {provider_label(provider)} API access token for this user.")


class InvitationExpiredError(InvalidInputError):
    code = "INVITATION_EXPIRED"

    def __init__(self) -> None:
        super().__init__("Invitation has expired")


class InvitationAlreadyAcceptedError(InvalidInputError):
    code = "INVITATION_ALREADY_ACCEPTED"

    def __init__(self) -> None:
        super().__init__("Invitation is accepted")


class InvitationWithdrawnError(InvalidInputError):
    """Revoked, or its email never got through: the link is dead, but no one used it."""

    code = "INVITATION_WITHDRAWN"

    def __init__(self, invitation_status: str) -> None:
        super().__init__(f"Invitation is {invitation_status}")


class ReauthRequiredError(ProviderConnectionError, ConflictError):
    """The grant is dead and the connection revoked: nothing fetches until the user reconnects.

    ``reason`` says why, for logs; the client gets the generic ``detail``.
    """

    code = "REAUTH_REQUIRED"

    def __init__(self, provider: str, user_id: UUID, reason: str) -> None:
        self.user_id = user_id
        self.reason = reason
        super().__init__(
            provider, f"{provider_label(provider)} authorization expired or was revoked; the user must reconnect."
        )


# Error code a dead grant is reported under, in sync logs and per-notification results
REAUTH_REQUIRED = ReauthRequiredError.code.lower()


def integrity_violation(exc: IntegrityError | PsycopgIntegrityError) -> BaseException | None:
    """The driver error behind ``exc``, whether SQLAlchemy wrapped it or not."""
    return exc.orig if isinstance(exc, IntegrityError) else exc


def describe_integrity_error(exc: IntegrityError | PsycopgIntegrityError) -> tuple[str, str | None]:
    """The violation type and constraint name - never the message, which carries the offending values."""
    violation = integrity_violation(exc)
    constraint = violation.diag.constraint_name if isinstance(violation, PsycopgError) else None
    return type(violation).__name__, constraint


def is_unique_violation(exc: IntegrityError | PsycopgIntegrityError) -> bool:
    """A duplicate row, as opposed to a NOT NULL, CHECK or foreign key violation, which is our bug."""
    return isinstance(integrity_violation(exc), UniqueViolation)


def public_error_text(exc: BaseException) -> str:
    """Text of ``exc`` safe to store or send: a database error's own text quotes the SQL, its parameters and row
    values, so only its type (and a violated constraint) is kept."""
    if isinstance(exc, INTEGRITY_ERRORS):
        kind, constraint = describe_integrity_error(exc)
        return f"{kind} ({constraint})" if constraint else kind
    if isinstance(exc, StatementError):
        return type(exc.orig or exc).__name__
    if isinstance(exc, PsycopgError):
        return type(exc).__name__
    return str(exc)


def app_error_from_integrity_error(exc: IntegrityError | PsycopgIntegrityError) -> AppError | None:
    """The client-caused constraint violation behind ``exc``, or None for one that is our bug."""
    orig = integrity_violation(exc)
    if isinstance(orig, UniqueViolation):
        entity = (orig.diag.table_name or "resource").replace("_", " ").capitalize()
        return ConflictError(f"{entity} already exists.")
    if isinstance(orig, ForeignKeyViolation):
        # FKs cascade or null on delete, except to series_type_definition (RESTRICT), whose
        # seeded rows no endpoint deletes - so this is a reference to a missing row
        return InvalidInputError("Referenced resource does not exist.")
    return None


def provider_error_from_response(
    provider: str, upstream_status: int | None, upstream_body: str | None = None
) -> ProviderError:
    """The error for a failed provider response: a throttle we couldn't wait out is a 503, anything else a 502."""
    if upstream_status == 401:
        return ProviderAuthRejectedError(provider, upstream_body=upstream_body)
    if upstream_status == 429:
        return ProviderRateLimitError(provider, upstream_status=upstream_status, upstream_body=upstream_body)
    return ProviderError(provider, upstream_status=upstream_status, upstream_body=upstream_body)
