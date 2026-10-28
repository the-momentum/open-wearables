"""
Tests for the global exception handlers in app.main.

Domain errors and IntegrityErrors are mapped to their status in one place, and anything
unhandled becomes a 500 that is still re-raised for the access log and Sentry.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from psycopg.errors import ForeignKeyViolation, NotNullViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import _get_db_dependency
from app.main import api
from app.utils.exceptions import AppError, ConflictError
from tests.factories import DeveloperFactory, UserFactory
from tests.utils import developer_auth_headers


def _access_log(mock: MagicMock, status: int) -> dict:
    """The attributes of the access log line for the response with ``status``."""
    return next(call.kwargs for call in mock.call_args_list if call.kwargs.get("status") == status)


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
        assert response.json() == {"detail": "Busy."}

    def test_authentication_error_sends_a_bearer_challenge(self, client: TestClient, api_v1_prefix: str) -> None:
        response = client.get(f"{api_v1_prefix}/users")

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"

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
        assert response.json() == {"detail": "Internal server error"}


class TestInvalidInput:
    @pytest.mark.parametrize(
        ("params", "detail"),
        [
            (
                {"start_date": "2026-01-01", "end_date": "2026-01-10", "cursor": "garbage"},
                "Invalid cursor format: 'garbage'. Expected 'timestamp|id'.",
            ),
            (
                {"start_date": "yesterday", "end_date": "2026-01-10"},
                "Invalid datetime format: 'yesterday'. Expected ISO 8601 format or Unix timestamp.",
            ),
        ],
    )
    def test_invalid_query_input_is_a_400(
        self, client: TestClient, api_v1_prefix: str, params: dict[str, str], detail: str
    ) -> None:
        developer = DeveloperFactory()
        user = UserFactory()

        response = client.get(
            f"{api_v1_prefix}/users/{user.id}/summaries/sleep",
            params=params,
            headers=developer_auth_headers(developer.id),
        )

        assert response.status_code == 400
        assert response.json() == {"detail": detail}

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

        assert response.status_code == 400
        assert response.json()["detail"].startswith("value is not a valid email address")
        line = _access_log(log, 400)
        assert line["error_cause_type"] == "RequestValidationError"
        assert line["error_cause_msg"] == "body.email"
        assert "jane.doe" not in str(line)


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
        assert response.json() == {"detail": "User already exists."}
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
        assert response.json() == {"detail": "Referenced resource does not exist."}

    def test_violation_the_client_did_not_cause_is_a_500(self, lenient_client: TestClient, api_v1_prefix: str) -> None:
        developer = DeveloperFactory()
        user = UserFactory()
        error = IntegrityError("stmt", {}, NotNullViolation("null value in column"))

        with patch("app.api.routes.v1.users.user_service.delete", side_effect=error):
            response = lenient_client.delete(
                f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id)
            )

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}


class TestUnhandledErrors:
    def test_unhandled_error_is_a_json_500(self, lenient_client: TestClient, api_v1_prefix: str) -> None:
        developer = DeveloperFactory()
        user = UserFactory()

        with patch("app.api.routes.v1.users.user_service.delete", side_effect=AttributeError("oops")):
            response = lenient_client.delete(
                f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id)
            )

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}

    def test_unhandled_error_is_still_raised_past_the_app(self, client: TestClient, api_v1_prefix: str) -> None:
        """Sentry's ASGI middleware and the access log only see the error if it propagates."""
        developer = DeveloperFactory()
        user = UserFactory()

        with (
            patch("app.api.routes.v1.users.user_service.delete", side_effect=AttributeError("oops")),
            pytest.raises(AttributeError, match="oops"),
        ):
            client.delete(f"{api_v1_prefix}/users/{user.id}", headers=developer_auth_headers(developer.id))
