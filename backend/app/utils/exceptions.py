from collections.abc import Callable
from functools import singledispatch, wraps
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi.exceptions import HTTPException, RequestValidationError
from psycopg.errors import IntegrityError as PsycopgIntegrityError
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError

if TYPE_CHECKING:
    from app.services import AppService


class ResourceNotFoundError(Exception):
    def __init__(self, entity_name: str, entity_id: int | UUID | None = None):
        self.entity_name = entity_name
        if entity_id:
            self.detail = f"{entity_name.capitalize()} with ID: {entity_id} not found."
        else:
            self.detail = f"{entity_name.capitalize()} not found."


class InvalidCursorError(Exception):
    def __init__(self, cursor: str):
        self.detail = f"Invalid cursor format: '{cursor}'. Expected 'timestamp|id'."


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
def _(exc: InvalidCursorError, _: str) -> HTTPException:
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


def handle_exceptions[**P, T, Service: AppService](func: Callable[P, T]) -> Callable[P, T]:
    @wraps(func)
    def async_wrapper(instance: Service, *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(instance, *args, **kwargs)
        except Exception as exc:
            entity_name = getattr(instance, "name", "unknown")
            raise handle_exception(exc, entity_name) from exc

    return async_wrapper
