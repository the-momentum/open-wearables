from typing import ClassVar
from uuid import UUID

from fastapi import status
from psycopg import Error as PsycopgError
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.errors import IntegrityError as PsycopgIntegrityError
from sqlalchemy.exc import IntegrityError

# ORM writes raise SQLAlchemy's wrapper; writes on the raw psycopg connection (COPY) raise psycopg's own
INTEGRITY_ERRORS = (IntegrityError, PsycopgIntegrityError)


class AppError(Exception):
    """Base of the domain errors raised by services and repositories.

    Raise a subclass instead of ``HTTPException``: the global handler in ``app.main`` turns
    ``status_code`` and ``detail`` into the response, and Celery tasks can catch it by type.
    """

    status_code: ClassVar[int] = status.HTTP_500_INTERNAL_SERVER_ERROR
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)

    @property
    def is_client_error(self) -> bool:
        return 400 <= self.status_code < 500


class InvalidInputError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    headers = {"WWW-Authenticate": "Bearer"}


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
    def __init__(self, provider: str, operation: str = "this operation"):
        super().__init__(f"Provider '{provider}' does not support {operation}.")


class InvalidCursorError(InvalidInputError):
    def __init__(self, cursor: str):
        super().__init__(f"Invalid cursor format: '{cursor}'. Expected 'timestamp|id'.")


class DatetimeParseError(InvalidInputError, ValueError):
    def __init__(self, value: str):
        super().__init__(f"Invalid datetime format: '{value}'. Expected ISO 8601 format or Unix timestamp.")


def integrity_violation(exc: IntegrityError | PsycopgIntegrityError) -> BaseException | None:
    """The driver error behind ``exc``, whether SQLAlchemy wrapped it or not."""
    return exc.orig if isinstance(exc, IntegrityError) else exc


def describe_integrity_error(exc: IntegrityError | PsycopgIntegrityError) -> tuple[str, str | None]:
    """The violation type and constraint name - never the message, which carries the offending values."""
    violation = integrity_violation(exc)
    constraint = violation.diag.constraint_name if isinstance(violation, PsycopgError) else None
    return type(violation).__name__, constraint


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
