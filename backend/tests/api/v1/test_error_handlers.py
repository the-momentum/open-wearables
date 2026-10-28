"""
Tests for the global exception handlers in app.main.

Domain errors and IntegrityErrors are mapped to their status in one place, and anything
unhandled becomes a 500 that is still re-raised for the access log and Sentry. Every error
is answered as RFC 9457 Problem Details.
"""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from psycopg.errors import ForeignKeyViolation, NotNullViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import _get_db_dependency
from app.main import api
from app.utils.exceptions import (
    AppError,
    ConflictError,
    ProviderError,
    ProviderRateLimitError,
    ServiceUnavailableError,
    WebhookVerificationError,
)
from tests.factories import DeveloperFactory, UserFactory
from tests.utils import developer_auth_headers


def _access_log(mock: MagicMock, status: int) -> dict:
    """The attributes of the access log line for the response with ``status``."""
    return next(call.kwargs for call in mock.call_args_list if call.kwargs.get("status") == status)


def _problem(status: int, detail: str, code: str) -> dict:
    return {"title": HTTPStatus(status).phrase, "status": status, "detail": detail, "code": code}


INTERNAL_ERROR = _problem(500, "Internal server error", "INTERNAL_ERROR")


@pytest.fixture
def lenient_client(db: Session) -> Generator[TestClient, None, None]:
    """A client that returns the 500 response instead of raising the server exception."""
    api.dependency_overrides[_get_db_dependency] = lambda: db
    with TestClient(api, raise_server_exceptions=False) as test_client:
        yield test_client
    api.dependency_overrides.clear()


class TestDomainErrors:
    def test_conflict_error(self, client: TestClient, api_v1_prefix: str) -> None:
        developer = DeveloperFactory()
        user = UserFactory()

        with patch("app.api.routes.v1.users.user_service.delete", side_effect=ConflictError("Busy.")):
            response = client.delete(f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id))

        assert response.status_code == 409
        assert response.headers["Content-Type"] == "application/problem+json"
        assert response.json() == _problem(409, "Busy.", "CONFLICT")

    def test_authentication_error_sends_a_bearer_challenge(self, client: TestClient, api_v1_prefix: str) -> None:
        response = client.get(f"{api_v1_prefix}/users")

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["code"] == "UNAUTHORIZED"

    def test_server_side_app_error_does_not_leak_its_detail(
        self, lenient_client: TestClient, api_v1_prefix: str
    ) -> None:
        developer = DeveloperFactory()
        user = UserFactory()

        with patch("app.api.routes.v1.users.user_service.delete", side_effect=AppError("internal state")):
            response = lenient_client.delete(
                f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id)
            )

        assert response.status_code == 500
        assert response.json() == INTERNAL_ERROR

    @pytest.mark.parametrize(
        ("error", "status", "detail", "code"),
        [
            (
                ProviderError("garmin", upstream_status=404, upstream_body='{"error": "user 42 not found"}'),
                502,
                "Garmin API error (status 404)",
                "PROVIDER_ERROR",
            ),
            (ProviderError("garmin"), 502, "Garmin API request failed", "PROVIDER_ERROR"),
            (
                ProviderRateLimitError("garmin", upstream_status=429),
                503,
                "Garmin API error (status 429)",
                "PROVIDER_RATE_LIMITED",
            ),
            (
                ServiceUnavailableError("Failed to complete multipart upload: SlowDown"),
                503,
                "Failed to complete multipart upload: SlowDown",
                "SERVICE_UNAVAILABLE",
            ),
        ],
    )
    def test_upstream_error_keeps_its_status_and_detail(
        self, client: TestClient, api_v1_prefix: str, error: AppError, status: int, detail: str, code: str
    ) -> None:
        """Not our bug: answered like a 4xx instead of re-raised (the default client would
        raise it), so it stays out of Sentry, and the provider's answer stays out of the body."""
        developer = DeveloperFactory()
        user = UserFactory()

        with patch("app.api.routes.v1.users.user_service.delete", side_effect=error):
            response = client.delete(f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id))

        assert response.status_code == status
        assert response.json() == _problem(status, detail, code)

    def test_webhook_verification_error_sends_no_bearer_challenge(self, client: TestClient, api_v1_prefix: str) -> None:
        developer = DeveloperFactory()
        user = UserFactory()

        with patch(
            "app.api.routes.v1.users.user_service.delete",
            side_effect=WebhookVerificationError("Invalid webhook signature"),
        ):
            response = client.delete(f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id))

        assert response.status_code == 401
        assert "WWW-Authenticate" not in response.headers
        assert response.json()["code"] == "WEBHOOK_VERIFICATION_FAILED"


class TestInvalidInput:
    @pytest.mark.parametrize(
        ("params", "detail", "code"),
        [
            (
                {"start_date": "2026-01-01", "end_date": "2026-01-10", "cursor": "garbage"},
                "Invalid cursor format: 'garbage'. Expected 'timestamp|id'.",
                "INVALID_CURSOR",
            ),
            (
                {"start_date": "yesterday", "end_date": "2026-01-10"},
                "Invalid datetime format: 'yesterday'. Expected ISO 8601 format or Unix timestamp.",
                "INVALID_DATETIME",
            ),
        ],
    )
    def test_invalid_query_input_is_a_400(
        self, client: TestClient, api_v1_prefix: str, params: dict[str, str], detail: str, code: str
    ) -> None:
        developer = DeveloperFactory()
        user = UserFactory()

        response = client.get(
            f"{api_v1_prefix}/users/{user.id}/summaries/sleep",
            params=params,
            headers=developer_auth_headers(developer.id),
        )

        assert response.status_code == 400
        assert response.json() == _problem(400, detail, code)

    def test_request_validation_error_names_the_field_but_not_the_value(
        self, client: TestClient, api_v1_prefix: str
    ) -> None:
        developer = DeveloperFactory()

        with patch("app.middlewares.logger.log") as log:
            response = client.post(
                f"{api_v1_prefix}/users",
                json={"email": "jane.doe-at-example"},
                headers=developer_auth_headers(developer.id),
            )

        assert response.status_code == 422
        assert response.json()["detail"].startswith("body.email: value is not a valid email address")
        line = _access_log(log, 422)
        assert line["error_cause_type"] == "RequestValidationError"
        assert line["error_cause_msg"] == "body.email"
        assert "jane.doe" not in str(line)

    def test_request_validation_error_lists_every_failure_without_the_values(
        self, client: TestClient, api_v1_prefix: str
    ) -> None:
        developer = DeveloperFactory()

        response = client.post(
            f"{api_v1_prefix}/users",
            json={"email": "jane.doe-at-example", "first_name": "Jane" * 30},
            headers=developer_auth_headers(developer.id),
        )

        assert response.status_code == 422
        assert response.headers["Content-Type"] == "application/problem+json"
        body = response.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert body["title"] == "Unprocessable Content"
        assert body["detail"].endswith("(and 1 more)")
        assert [(error["loc"], error["type"]) for error in body["errors"]] == [
            (["body", "first_name"], "string_too_long"),
            (["body", "email"], "value_error"),
        ]
        assert "JaneJane" not in response.text
        assert "jane.doe" not in response.text

    def test_login_validation_error_is_a_failed_login(self, client: TestClient, api_v1_prefix: str) -> None:
        response = client.post(f"{api_v1_prefix}/auth/login", data={"username": "jane@example.com"})

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == _problem(401, "Incorrect email or password", "UNAUTHORIZED")


class TestHTTPExceptions:
    def test_code_is_named_after_the_status(self, client: TestClient, api_v1_prefix: str) -> None:
        developer = DeveloperFactory()
        user = UserFactory()

        response = client.delete(
            f"{api_v1_prefix}/users/{user.id}/events/workouts/00000000-0000-4000-8000-000000000000",
            headers=developer_auth_headers(developer.id),
        )

        assert response.status_code == 404
        assert response.headers["Content-Type"] == "application/problem+json"
        assert response.json() == _problem(404, "Workout not found", "NOT_FOUND")

    def test_starlette_routing_errors_are_problems_too(self, client: TestClient) -> None:
        response = client.get("/no/such/path")

        assert response.status_code == 404
        assert response.json() == _problem(404, "Not Found", "NOT_FOUND")


class TestIntegrityErrors:
    def test_unique_violation_is_a_conflict(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        developer = DeveloperFactory()
        UserFactory(external_user_id="taken")
        user = UserFactory(external_user_id="mine")

        def write_a_duplicate(*_args: object, **_kwargs: object) -> None:
            # a real violation, as a write the service didn't check up front would raise
            user.external_user_id = "taken"
            db.flush()

        with (
            patch("app.api.routes.v1.users.user_service.delete", side_effect=write_a_duplicate),
            patch("app.middlewares.logger.log") as log,
        ):
            response = client.delete(f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id))

        assert response.status_code == 409
        assert response.json() == _problem(409, "User already exists.", "CONFLICT")
        line = _access_log(log, 409)
        assert line["error_cause_type"] == "UniqueViolation"
        assert line["error_cause_msg"] == "constraint user_external_user_id_key"
        assert "taken" not in str(line)

    def test_raw_psycopg_violation_is_mapped_too(self, client: TestClient, api_v1_prefix: str) -> None:
        """Writes on the raw psycopg connection (COPY) raise psycopg's error, not SQLAlchemy's."""
        developer = DeveloperFactory()
        user = UserFactory()

        with patch("app.api.routes.v1.users.user_service.delete", side_effect=ForeignKeyViolation("fk")):
            response = client.delete(f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id))

        assert response.status_code == 400
        assert response.json() == _problem(400, "Referenced resource does not exist.", "BAD_REQUEST")

    def test_violation_the_client_did_not_cause_is_a_500(self, lenient_client: TestClient, api_v1_prefix: str) -> None:
        developer = DeveloperFactory()
        user = UserFactory()
        error = IntegrityError("stmt", {}, NotNullViolation("null value in column"))

        with patch("app.api.routes.v1.users.user_service.delete", side_effect=error):
            response = lenient_client.delete(
                f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id)
            )

        assert response.status_code == 500
        assert response.json() == INTERNAL_ERROR


class TestUnhandledErrors:
    def test_unhandled_error_is_a_json_500(self, lenient_client: TestClient, api_v1_prefix: str) -> None:
        developer = DeveloperFactory()
        user = UserFactory()

        with patch("app.api.routes.v1.users.user_service.delete", side_effect=AttributeError("oops")):
            response = lenient_client.delete(
                f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id)
            )

        assert response.status_code == 500
        assert response.json() == INTERNAL_ERROR

    def test_unhandled_error_is_still_raised_past_the_app(self, client: TestClient, api_v1_prefix: str) -> None:
        """Sentry's ASGI middleware and the access log only see the error if it propagates."""
        developer = DeveloperFactory()
        user = UserFactory()

        with (
            patch("app.api.routes.v1.users.user_service.delete", side_effect=AttributeError("oops")),
            pytest.raises(AttributeError, match="oops"),
        ):
            client.delete(f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id))


class TestOpenAPI:
    def test_every_error_response_is_documented_as_a_problem(self) -> None:
        schema = api.openapi()

        error_responses = [
            (path, status, response)
            for path, operations in schema["paths"].items()
            for operation in operations.values()
            for status, response in operation["responses"].items()
            if status[0] in "45"
        ]

        assert error_responses
        for path, status, response in error_responses:
            assert list(response["content"]) == ["application/problem+json"], (path, status)
        assert "HTTPValidationError" not in schema["components"]["schemas"]
        assert schema["paths"]["/api/v1/users"]["post"]["responses"]["422"]["content"]["application/problem+json"][
            "schema"
        ] == {"$ref": "#/components/schemas/ValidationProblem"}

    def test_login_documents_its_validation_errors_as_a_failed_login(self) -> None:
        responses = api.openapi()["paths"]["/api/v1/auth/login"]["post"]["responses"]

        assert "422" not in responses
        assert responses["401"]["content"]["application/problem+json"]["schema"] == {
            "$ref": "#/components/schemas/Problem"
        }
