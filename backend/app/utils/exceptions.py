import inspect
from collections.abc import Awaitable, Callable
from functools import singledispatch, wraps
from typing import TYPE_CHECKING, overload
from uuid import UUID

from fastapi.exceptions import HTTPException, RequestValidationError
from psycopg.errors import IntegrityError as PsycopgIntegrityError
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError

if TYPE_CHECKING:
    from app.services import AppService


class UnsupportedProviderError(Exception):
    def __init__(self, provider: str, operation: str = "this operation"):
        self.detail = f"Provider '{provider}' does not support {operation}."
        super().__init__(self.detail)


class ResourceNotFoundError(Exception):
    def __init__(self, entity_name: str, entity_id: int | UUID | None = None):
        self.entity_name = entity_name
        if entity_id:
            self.detail = f"{entity_name.capitalize()} with ID: {entity_id} not found."
        else:
            self.detail = f"{entity_name.capitalize()} not found."


class ResourceAlreadyExistsError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class InvalidCursorError(Exception):
    def __init__(self, cursor: str):
        self.detail = f"Invalid cursor format: '{cursor}'. Expected 'timestamp|id'."


class ReconcileWindowTooLargeError(Exception):
    """A source_selection=reconcile page would merge more days on the fly than the server allows."""

    code = "reconcile_too_many_days"

    def __init__(self, days: int, max_days: int, queued: bool):
        self.days, self.max_days, self.queued = days, max_days, queued
        super().__init__(f"{days} days to merge on the fly, at most {max_days}")


class DatetimeParseError(ValueError):
    def __init__(self, value: str):
        self.detail = f"Invalid datetime format: '{value}'. Expected ISO 8601 format or Unix timestamp."
        super().__init__(self.detail)


@singledispatch
def handle_exception(exc: Exception, _: str) -> HTTPException:
    raise exc


@handle_exception.register
def _(exc: SQLAIntegrityError | PsycopgIntegrityError, entity: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=f"{entity.capitalize()} entity already exists. Details: {exc.args[0]}",
    )


@handle_exception.register
def _(exc: ResourceNotFoundError, _: str) -> HTTPException:
    return HTTPException(status_code=404, detail=exc.detail)


@handle_exception.register
def _(exc: ResourceAlreadyExistsError, _: str) -> HTTPException:
    return HTTPException(status_code=409, detail=exc.detail)


@handle_exception.register
def _(exc: InvalidCursorError, _: str) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.detail)


@handle_exception.register
def _(exc: ReconcileWindowTooLargeError, _: str) -> HTTPException:
    # Structured, so a client can lower its page size by the numbers rather than parse a sentence.
    return HTTPException(
        status_code=400,
        detail={
            "code": exc.code,
            "message": "source_selection=reconcile would merge more days on the fly than allowed for one page; "
            "lower `limit` or narrow the range.",
            "days": exc.days,
            "max_days": exc.max_days,
            # Queued to be stored by the rollup; not a promise of when, as its budget decides.
            "queued": exc.queued,
        },
    )


@handle_exception.register
def _(exc: DatetimeParseError, _: str) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.detail)


@handle_exception.register
def _(exc: AttributeError, entity: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=f"{entity.capitalize()} doesn't support attribute or method. Details: {exc.args[0]} ",
    )


@handle_exception.register
def _(exc: RequestValidationError, _: str) -> HTTPException:
    err_args = exc.args[0][0]
    msg = err_args.get("msg", "Validation error")
    ctx = err_args.get("ctx", {})
    error = ctx.get("error", "") if ctx else ""
    detail = f"{msg} - {error}" if error else msg
    return HTTPException(status_code=400, detail=detail)


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
