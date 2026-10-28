from pydantic import BaseModel, ConfigDict, Field


class Problem(BaseModel):
    """An error response: RFC 9457 Problem Details, served as ``application/problem+json``.

    ``type`` is omitted, which per the RFC means ``about:blank``: ``title`` is the status
    phrase, and ``code`` tells errors with the same status apart.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Not Found",
                    "status": 404,
                    "detail": "User with ID: 123e4567-e89b-12d3-a456-426614174000 not found.",
                    "code": "NOT_FOUND",
                }
            ]
        }
    )

    title: str = Field(..., description="HTTP status phrase")
    status: int = Field(..., description="HTTP status code, the same as the response's")
    detail: str = Field(..., description="Human-readable explanation of this occurrence")
    code: str = Field(..., description="Machine-readable error code, stable across releases")


class ValidationErrorItem(BaseModel):
    loc: list[str | int] = Field(..., description="Where the invalid value is, e.g. ['body', 'email']")
    msg: str = Field(..., description="What is wrong with it")
    type: str = Field(..., description="Pydantic error type, e.g. 'missing'")


class ValidationProblem(Problem):
    """A 422 for a request that failed validation, listing every failure."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Unprocessable Content",
                    "status": 422,
                    "detail": "body.email: value is not a valid email address: An email address must have an @-sign. "
                    "(and 1 more)",
                    "code": "VALIDATION_ERROR",
                    "errors": [
                        {
                            "loc": ["body", "email"],
                            "msg": "value is not a valid email address: An email address must have an @-sign.",
                            "type": "value_error",
                        },
                        {
                            "loc": ["body", "first_name"],
                            "msg": "String should have at most 100 characters",
                            "type": "string_too_long",
                        },
                    ],
                }
            ]
        }
    )

    errors: list[ValidationErrorItem] = Field(..., description="Every validation failure in the request")
