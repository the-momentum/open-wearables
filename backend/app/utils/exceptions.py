import inspect
import re
from collections.abc import Awaitable, Callable
from functools import singledispatch, wraps
from typing import TYPE_CHECKING, overload
from uuid import UUID

from fastapi.exceptions import HTTPException
from psycopg.errors import IntegrityError as PsycopgIntegrityError
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError

if TYPE_CHECKING:
    from app.services import AppService


class ApiError(HTTPException):
    """HTTPException with a stable machine-readable error code.

    Rendered as an RFC 9457 problem details response by the handler in
    app.utils.problem.
    """

    def __init__(self, status_code: int, code: str, detail: str, headers: dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


def not_found_code(entity_name: str) -> str:
    """Derive an error code from an entity name, e.g. ApiKey -> API_KEY_NOT_FOUND."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", entity_name)
    normalized = re.sub(r"[^A-Z0-9]+", "_", words.upper()).strip("_")
    # Dynamic entity descriptions (IDs, dates) would produce unbounded codes
    if not normalized or len(normalized) > 30:
        return "RESOURCE_NOT_FOUND"
    return f"{normalized}_NOT_FOUND"


class UnsupportedProviderError(Exception):
    def __init__(self, provider: str, operation: str = "this operation"):
        self.detail = f"Provider '{provider}' does not support {operation}."
        self.code = "UNSUPPORTED_PROVIDER_OPERATION"
        super().__init__(self.detail)


class ResourceNotFoundError(Exception):
    def __init__(self, entity_name: str, entity_id: int | UUID | None = None, code: str | None = None):
        self.entity_name = entity_name
        self.code = code or not_found_code(entity_name)
        if entity_id:
            self.detail = f"{entity_name.capitalize()} with ID: {entity_id} not found."
        else:
            self.detail = f"{entity_name.capitalize()} not found."


class InvalidCursorError(Exception):
    def __init__(self, cursor: str):
        self.detail = f"Invalid cursor format: '{cursor}'. Expected 'timestamp|id'."


class DatetimeParseError(ValueError):
    def __init__(self, value: str):
        self.detail = f"Invalid datetime format: '{value}'. Expected ISO 8601 format or Unix timestamp."
        super().__init__(self.detail)


@singledispatch
def handle_exception(exc: Exception, _: str) -> HTTPException:
    raise exc


@handle_exception.register
def _(exc: SQLAIntegrityError | PsycopgIntegrityError, entity: str) -> HTTPException:
    return ApiError(
        status_code=400,
        code="ALREADY_EXISTS",
        detail=f"{entity.capitalize()} entity already exists. Details: {exc.args[0]}",
    )


@handle_exception.register
def _(exc: ResourceNotFoundError, _: str) -> HTTPException:
    return ApiError(status_code=404, code=exc.code, detail=exc.detail)


@handle_exception.register
def _(exc: UnsupportedProviderError, _: str) -> HTTPException:
    return ApiError(status_code=400, code=exc.code, detail=exc.detail)


@handle_exception.register
def _(exc: InvalidCursorError, _: str) -> HTTPException:
    return ApiError(status_code=400, code="INVALID_CURSOR", detail=exc.detail)


@handle_exception.register
def _(exc: DatetimeParseError, _: str) -> HTTPException:
    return ApiError(status_code=400, code="INVALID_DATETIME", detail=exc.detail)


@handle_exception.register
def _(exc: AttributeError, entity: str) -> HTTPException:
    return ApiError(
        status_code=400,
        code="UNSUPPORTED_ATTRIBUTE",
        detail=f"{entity.capitalize()} doesn't support attribute or method. Details: {exc.args[0]} ",
    )


@overload
def handle_exceptions[**P, T, Service: AppService](
    func: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]: ...


@overload
def handle_exceptions[**P, T, Service: AppService](
    func: Callable[P, T],
) -> Callable[P, T]: ...


def handle_exceptions[**P, T, Service: AppService](
    func: Callable[P, T] | Callable[P, Awaitable[T]],
) -> Callable[P, T] | Callable[P, Awaitable[T]]:
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(instance: Service, *args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(instance, *args, **kwargs)  # ty:ignore[invalid-argument-type]
            except Exception as exc:
                entity_name = getattr(instance, "name", "unknown")
                raise handle_exception(exc, entity_name) from exc

        return async_wrapper  # ty:ignore[invalid-return-type]

    @wraps(func)
    def sync_wrapper(instance: Service, *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(instance, *args, **kwargs)  # ty:ignore[invalid-argument-type, invalid-return-type]
        except Exception as exc:
            entity_name = getattr(instance, "name", "unknown")
            raise handle_exception(exc, entity_name) from exc

    return sync_wrapper  # ty:ignore[invalid-return-type]
