"""RFC 9457 problem details error responses.

Every error response uses the shape {title, status, detail, code} with the
`application/problem+json` media type. `code` is an extension member carrying
a stable machine-readable identifier. `type` is omitted, which RFC 9457
defines as equivalent to "about:blank".
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.exceptions import DatetimeParseError

PROBLEM_SCHEMA: dict[str, Any] = {
    "title": "Problem",
    "type": "object",
    "description": "RFC 9457 problem details error response",
    "properties": {
        "title": {"type": "string", "title": "Title"},
        "status": {"type": "integer", "title": "Status"},
        "detail": {"type": "string", "title": "Detail"},
        "code": {"type": "string", "title": "Code"},
        "errors": {
            "type": "array",
            "title": "Errors",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "title": "Field"},
                    "message": {"type": "string", "title": "Message"},
                    "type": {"type": "string", "title": "Type"},
                },
                "required": ["field", "message", "type"],
            },
        },
    },
    "required": ["title", "status", "detail", "code"],
}


def _status_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _status_code_name(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return f"HTTP_{status_code}"


def problem_response(
    status_code: int,
    code: str,
    detail: str,
    *,
    errors: list[dict[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "title": _status_phrase(status_code),
        "status": status_code,
        "detail": detail,
        "code": code,
    }
    if errors is not None:
        content["errors"] = errors
    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
        headers=headers,
    )


def register_exception_handlers(api: FastAPI) -> None:
    @api.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> Response:
        # 1xx/204/205/304 must not carry a body
        if not is_body_allowed_for_status_code(exc.status_code):
            return Response(status_code=exc.status_code, headers=exc.headers)
        # ApiError carries an explicit code; plain HTTPException falls back to
        # a code derived from the status, e.g. 401 -> UNAUTHORIZED.
        code = getattr(exc, "code", None) or _status_code_name(exc.status_code)
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return problem_response(exc.status_code, code, detail, headers=exc.headers)

    @api.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # (FastAPI >= 0.130 rejects empty required str form fields before the route runs)
        if request.url.path.endswith("/auth/login"):
            return problem_response(
                status.HTTP_401_UNAUTHORIZED,
                "INVALID_CREDENTIALS",
                "Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        errors = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return problem_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "Request validation failed.",
            errors=errors,
        )

    @api.exception_handler(DatetimeParseError)
    async def handle_datetime_parse_error(_: Request, exc: DatetimeParseError) -> JSONResponse:
        return problem_response(status.HTTP_400_BAD_REQUEST, "INVALID_DATETIME", exc.detail)

    @api.exception_handler(Exception)
    async def handle_unexpected_exception(_: Request, exc: Exception) -> JSONResponse:
        # Starlette sends this response and then re-raises the exception, so it
        # still reaches the server log and Sentry.
        return problem_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
        )


def apply_problem_openapi(api: FastAPI) -> None:
    """Replace FastAPI's generated 422 validation schema with the Problem schema."""

    def custom_openapi() -> dict[str, Any]:
        if api.openapi_schema:
            return api.openapi_schema
        schema = get_openapi(
            title=api.title,
            version=api.version,
            description=api.description,
            routes=api.routes,
        )
        schemas = schema.setdefault("components", {}).setdefault("schemas", {})
        schemas["Problem"] = PROBLEM_SCHEMA
        schemas.pop("HTTPValidationError", None)
        schemas.pop("ValidationError", None)
        problem_content = {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}}
        for path_item in schema.get("paths", {}).values():
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                for response_status, response in operation.get("responses", {}).items():
                    if response_status == "422":
                        response["content"] = problem_content
        api.openapi_schema = schema
        return schema

    api.openapi = custom_openapi  # ty:ignore[invalid-assignment]
