import inspect
import logging
from collections.abc import Awaitable, Callable
from functools import singledispatch, wraps
from typing import TYPE_CHECKING, overload
from uuid import UUID

from fastapi.exceptions import HTTPException, RequestValidationError
from psycopg.errors import IntegrityError as PsycopgIntegrityError
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError

if TYPE_CHECKING:
    from app.services import AppService

logger = logging.getLogger(__name__)


class ResourceNotFoundError(Exception):
    def __init__(self, entity_name: str, entity_id: int | UUID | None = None) -> None:
        self.entity_name = entity_name
        if entity_id is not None:
            self.detail = f"{entity_name.capitalize()} with ID: {entity_id} not found."
        else:
            self.detail = f"{entity_name.capitalize()} not found."


class AccessDeniedError(Exception):
    def __init__(self, entity_name: str) -> None:
        self.detail = f"Access to {entity_name} denied."


class GoneError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail


class ConflictError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail


@singledispatch
def handle_exception(exc: Exception, _: str) -> HTTPException:
    raise exc


@handle_exception.register
def _(exc: SQLAIntegrityError | PsycopgIntegrityError, entity: str) -> HTTPException:
    logger.warning("Integrity error for %s: %s", entity, exc.args[0] if exc.args else "unknown")
    return HTTPException(
        status_code=400,
        detail=f"{entity.capitalize()} entity already exists.",
    )


@handle_exception.register
def _(exc: ResourceNotFoundError, _: str) -> HTTPException:
    return HTTPException(status_code=404, detail=exc.detail)


@handle_exception.register
def _(exc: AccessDeniedError, _: str) -> HTTPException:
    return HTTPException(status_code=403, detail=exc.detail)


@handle_exception.register
def _(exc: GoneError, _: str) -> HTTPException:
    return HTTPException(status_code=410, detail=exc.detail)


@handle_exception.register
def _(exc: ConflictError, _: str) -> HTTPException:
    return HTTPException(status_code=409, detail=exc.detail)


@handle_exception.register
def _(exc: AttributeError, entity: str) -> HTTPException:
    logger.warning("AttributeError for %s: %s", entity, exc.args[0] if exc.args else "unknown")
    return HTTPException(
        status_code=400,
        detail=f"{entity.capitalize()} doesn't support this operation.",
    )


@handle_exception.register
def _(exc: RequestValidationError, _: str) -> HTTPException:
    errors = exc.errors()
    err_args = errors[0] if errors else {}
    msg = err_args.get("msg", "Validation error")
    ctx = err_args.get("ctx", {})
    error = ctx.get("error", "") if ctx else ""
    detail = f"{msg} - {error}" if error else msg
    return HTTPException(status_code=422, detail=detail)


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
                return await func(instance, *args, **kwargs)  # ty: ignore[invalid-argument-type]
            except Exception as exc:
                entity_name = getattr(instance, "name", "unknown")
                raise handle_exception(exc, entity_name) from exc

        return async_wrapper  # ty: ignore[invalid-return-type]

    @wraps(func)
    def sync_wrapper(instance: Service, *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(instance, *args, **kwargs)  # ty: ignore[invalid-argument-type, invalid-return-type]
        except Exception as exc:
            entity_name = getattr(instance, "name", "unknown")
            raise handle_exception(exc, entity_name) from exc

    return sync_wrapper  # ty: ignore[invalid-return-type]
