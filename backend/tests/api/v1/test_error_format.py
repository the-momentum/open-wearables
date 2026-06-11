"""
Tests for the RFC 9457 problem details error format.

Covers the handlers registered by app.utils.problem.register_exception_handlers
through a minimal FastAPI app, plus real endpoints migrated to ApiError.
"""

from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.utils.exceptions import ApiError, DatetimeParseError
from app.utils.problem import register_exception_handlers
from tests.factories import ApiKeyFactory, DeveloperFactory, UserFactory
from tests.utils import api_key_headers, developer_auth_headers

PROBLEM_CONTENT_TYPE = "application/problem+json"


def build_problem_app() -> FastAPI:
    """Build a minimal app exercising every registered exception handler."""
    app = FastAPI()
    register_exception_handlers(app)

    class ItemPayload(BaseModel):
        name: str = Field(min_length=5)
        quantity: int

    @app.get("/api-error")
    def raise_api_error() -> None:
        raise ApiError(status_code=409, code="ITEM_CONFLICT", detail="Item already exists.")

    @app.get("/http-error")
    def raise_http_exception() -> None:
        raise HTTPException(status_code=404, detail="Item not found.")

    @app.post("/items")
    def create_item(payload: ItemPayload) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/unhandled-error")
    def raise_runtime_error() -> None:
        raise RuntimeError("boom")

    @app.get("/datetime-error")
    def raise_datetime_parse_error() -> None:
        raise DatetimeParseError("not-a-datetime")

    @app.get("/auth-error")
    def raise_api_error_with_headers() -> None:
        raise ApiError(
            status_code=401,
            code="NOT_AUTHENTICATED",
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return app


class TestProblemResponses:
    """Test suite for the problem details handlers on a minimal app."""

    def test_api_error_renders_problem_body(self) -> None:
        """Test that ApiError renders the full problem body with its code."""
        # Arrange
        test_client = TestClient(build_problem_app())

        # Act
        response = test_client.get("/api-error")

        # Assert
        assert response.status_code == 409
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.json() == {
            "title": "Conflict",
            "status": 409,
            "detail": "Item already exists.",
            "code": "ITEM_CONFLICT",
        }

    def test_plain_http_exception_derives_code_from_status(self) -> None:
        """Test that plain HTTPException gets a code derived from the status."""
        # Arrange
        test_client = TestClient(build_problem_app())

        # Act
        response = test_client.get("/http-error")

        # Assert
        assert response.status_code == 404
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.json() == {
            "title": "Not Found",
            "status": 404,
            "detail": "Item not found.",
            "code": "NOT_FOUND",
        }

    def test_validation_error_lists_all_errors(self) -> None:
        """Test that a validation failure returns 422 with one entry per error."""
        # Arrange
        test_client = TestClient(build_problem_app())

        # Act - both fields are invalid
        response = test_client.post("/items", json={"name": "ab", "quantity": "not-a-number"})

        # Assert
        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        body = response.json()
        assert body["title"] == "Unprocessable Content"
        assert body["status"] == 422
        assert body["detail"] == "Request validation failed."
        assert body["code"] == "VALIDATION_ERROR"
        assert {error["field"] for error in body["errors"]} == {"body.name", "body.quantity"}
        for error in body["errors"]:
            assert set(error) == {"field", "message", "type"}
            assert error["message"]
            assert error["type"]

    def test_datetime_parse_error_returns_invalid_datetime(self) -> None:
        """Test that DatetimeParseError renders a 400 with code INVALID_DATETIME."""
        # Arrange
        test_client = TestClient(build_problem_app())

        # Act
        response = test_client.get("/datetime-error")

        # Assert
        assert response.status_code == 400
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.json() == {
            "title": "Bad Request",
            "status": 400,
            "detail": "Invalid datetime format: 'not-a-datetime'. Expected ISO 8601 format or Unix timestamp.",
            "code": "INVALID_DATETIME",
        }

    def test_api_error_preserves_www_authenticate_header(self) -> None:
        """Test that headers set on ApiError survive the exception handler."""
        # Arrange
        test_client = TestClient(build_problem_app())

        # Act
        response = test_client.get("/auth-error")

        # Assert
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.json()["code"] == "NOT_AUTHENTICATED"

    def test_unhandled_exception_becomes_internal_error(self) -> None:
        """Test that an unhandled exception returns 500 INTERNAL_ERROR."""
        # Arrange - Starlette re-raises after responding, so the client must not
        test_client = TestClient(build_problem_app(), raise_server_exceptions=False)

        # Act
        response = test_client.get("/unhandled-error")

        # Assert
        assert response.status_code == 500
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.json() == {
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred.",
            "code": "INTERNAL_ERROR",
        }


class TestLoginProblemFormat:
    """Test suite for the login validation special case on the real app."""

    def test_login_validation_failure_returns_invalid_credentials(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        """Test that a login validation failure stays 401 INVALID_CREDENTIALS."""
        # Act - missing password fails request validation before the route runs
        response = client.post(f"{api_v1_prefix}/auth/login", data={"username": "test@example.com"})

        # Assert
        assert response.status_code == 401
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.headers["WWW-Authenticate"] == "Bearer"
        body = response.json()
        assert body["code"] == "INVALID_CREDENTIALS"
        assert body["detail"] == "Incorrect email or password"


class TestDeveloperAuthCodes:
    """Test suite for the auth error code split on developer (JWT) endpoints."""

    def test_missing_token_returns_not_authenticated(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test that a missing Authorization header yields NOT_AUTHENTICATED."""
        # Act
        response = client.get(f"{api_v1_prefix}/auth/me")

        # Assert
        assert response.status_code == 401
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["code"] == "NOT_AUTHENTICATED"

    def test_garbage_token_returns_invalid_token(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test that an unparseable bearer token yields INVALID_TOKEN."""
        # Act
        response = client.get(f"{api_v1_prefix}/auth/me", headers={"Authorization": "Bearer garbage"})

        # Assert
        assert response.status_code == 401
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["code"] == "INVALID_TOKEN"


class TestDerivedNotFoundCode:
    """Test suite for not-found codes derived from CamelCase model names."""

    def test_unknown_api_key_uses_word_boundary_code(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test that a missing ApiKey yields API_KEY_NOT_FOUND, not APIKEY_NOT_FOUND."""
        # Arrange
        developer = DeveloperFactory()
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.delete(f"{api_v1_prefix}/developer/api-keys/sk-{uuid4().hex}", headers=headers)

        # Assert
        assert response.status_code == 404
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.json()["code"] == "API_KEY_NOT_FOUND"


class TestProblemOpenApi:
    """Test suite for the OpenAPI schema patch in apply_problem_openapi."""

    def test_problem_schema_replaces_validation_schemas(self, client: TestClient) -> None:
        """Test that Problem is registered and FastAPI's validation schemas are gone."""
        # Act
        schema = client.get("/openapi.json").json()

        # Assert
        schemas = schema["components"]["schemas"]
        assert "Problem" in schemas
        assert "HTTPValidationError" not in schemas
        assert "ValidationError" not in schemas

    def test_every_422_response_references_problem(self, client: TestClient) -> None:
        """Test that all 422 responses use application/problem+json with the Problem ref."""
        # Act
        schema = client.get("/openapi.json").json()

        # Assert
        expected_content = {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}}
        checked = 0
        for path_item in schema["paths"].values():
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                response_422 = operation.get("responses", {}).get("422")
                if response_422 is None:
                    continue
                assert response_422["content"] == expected_content
                checked += 1
        assert checked > 0

    def test_explicit_user_responses_resolve_against_components(self, client: TestClient) -> None:
        """Test that the documented 401/404 responses on GET /users/{user_id} resolve."""
        # Act
        schema = client.get("/openapi.json").json()

        # Assert
        operation = schema["paths"]["/api/v1/users/{user_id}"]["get"]
        for status_code in ("401", "404"):
            ref = operation["responses"][status_code]["content"]["application/problem+json"]["schema"]["$ref"]
            assert ref == "#/components/schemas/Problem"
            assert ref.rsplit("/", 1)[-1] in schema["components"]["schemas"]


class TestMigratedEndpointCodes:
    """Test suite for error codes on endpoints migrated to ApiError."""

    def test_async_sync_with_unsupported_parameters(self, client: TestClient, db: Session) -> None:
        """Test that provider-specific flags in async mode return a coded 400."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()

        # Act
        response = client.post(
            f"/api/v1/providers/garmin/users/{user.id}/sync",
            headers=api_key_headers(api_key.id),
            params={"samples": "true"},
        )

        # Assert
        assert response.status_code == 400
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        body = response.json()
        assert body["code"] == "UNSUPPORTED_SYNC_PARAMETERS"
        assert "samples" in body["detail"]

    def test_garmin_backfill_retry_invalid_type(self, client: TestClient, db: Session) -> None:
        """Test that an unknown backfill type returns a coded 400."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()

        # Act
        response = client.post(
            f"/api/v1/providers/garmin/users/{user.id}/backfill/not_a_type/retry",
            headers=api_key_headers(api_key.id),
        )

        # Assert
        assert response.status_code == 400
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        body = response.json()
        assert body["code"] == "INVALID_BACKFILL_TYPE"
        assert "not_a_type" in body["detail"]
