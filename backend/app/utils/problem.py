"""Error responses as RFC 9457 Problem Details, and their place in the OpenAPI schema."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import Response
from fastapi.responses import JSONResponse
from fastapi.utils import is_body_allowed_for_status_code
from pydantic.json_schema import models_json_schema

from app.schemas.utils.problem import Problem, ValidationErrorItem, ValidationProblem

PROBLEM_MEDIA_TYPE = "application/problem+json"

VALIDATION_ERROR = "VALIDATION_ERROR"
# not HTTPStatus' INTERNAL_SERVER_ERROR: it names our failure, whatever status carries it
INTERNAL_ERROR = "INTERNAL_ERROR"


class ProblemResponse(JSONResponse):
    media_type = PROBLEM_MEDIA_TYPE


def status_code_name(status_code: int) -> str:
    """The ``code`` of an error that has none of its own (an ``HTTPException``): the status' name."""
    if status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
        return INTERNAL_ERROR
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return f"HTTP_{status_code}"


def _title(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def problem_response(
    status_code: int,
    detail: str,
    code: str,
    headers: Mapping[str, str] | None = None,
    errors: list[ValidationErrorItem] | None = None,
) -> Response:
    if not is_body_allowed_for_status_code(status_code):
        return Response(status_code=status_code, headers=headers)
    fields = {"title": _title(status_code), "status": status_code, "detail": detail, "code": code}
    problem = Problem(**fields) if errors is None else ValidationProblem(**fields, errors=errors)
    return ProblemResponse(problem.model_dump(), status_code=status_code, headers=headers)


def _is_error_status(status: str) -> bool:
    return status[0] in "45"


def add_problem_responses(schema: dict[str, Any]) -> dict[str, Any]:
    """Document every error response as Problem Details, FastAPI's own 422 included."""
    ref = "#/components/schemas/{model}"
    _, definitions = models_json_schema(
        [(Problem, "serialization"), (ValidationProblem, "serialization")], ref_template=ref
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.update(definitions["$defs"])

    fastapi_422 = ref.format(model="HTTPValidationError")
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            for status, response in operation.get("responses", {}).items():
                if not _is_error_status(status):
                    continue
                content = response.get("content", {}).get("application/json", {})
                model = ValidationProblem if content.get("schema", {}).get("$ref") == fastapi_422 else Problem
                # a route's own example stays; its schema, if any, is replaced
                entry = {key: value for key, value in content.items() if key != "schema"}
                response["content"] = {
                    PROBLEM_MEDIA_TYPE: {"schema": {"$ref": ref.format(model=model.__name__)}, **entry}
                }

    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)
    return schema
