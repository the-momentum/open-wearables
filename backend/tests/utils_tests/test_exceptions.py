"""
Tests for the domain exceptions and the IntegrityError translation.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from psycopg.errors import ForeignKeyViolation, NotNullViolation, UniqueViolation
from sqlalchemy.exc import IntegrityError

from app.utils.exceptions import (
    AppError,
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    DatetimeParseError,
    InvalidCursorError,
    InvalidInputError,
    NotFoundError,
    PermissionDeniedError,
    ProviderError,
    ProviderNotConnectedError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    UnsupportedProviderError,
    app_error_from_integrity_error,
    is_upstream_outage,
)


class TestResourceNotFoundError:
    """Test suite for ResourceNotFoundError exception."""

    def test_init_with_entity_name_only(self) -> None:
        error = ResourceNotFoundError("User")

        assert error.entity_name == "User"
        assert error.detail == "User not found."

    def test_init_with_entity_name_and_int_id(self) -> None:
        error = ResourceNotFoundError("user", 123)

        assert error.entity_name == "user"
        assert error.detail == "User with ID: 123 not found."

    def test_init_with_entity_name_and_uuid_id(self) -> None:
        entity_id = uuid4()

        error = ResourceNotFoundError("device", entity_id)

        assert error.detail == f"Device with ID: {entity_id} not found."

    def test_init_with_none_id(self) -> None:
        error = ResourceNotFoundError("session", None)

        assert error.detail == "Session not found."

    def test_is_a_not_found_error(self) -> None:
        error = ResourceNotFoundError("user", 1)

        assert isinstance(error, NotFoundError)
        assert error.status_code == 404
        assert str(error) == error.detail


class TestStatusCodes:
    """Each category carries the HTTP status the global handler responds with."""

    @pytest.mark.parametrize(
        ("error", "status_code"),
        [
            (AppError("boom"), 500),
            (InvalidInputError("bad"), 400),
            (AuthenticationError("who?"), 401),
            (PermissionDeniedError("no"), 403),
            (NotFoundError("gone"), 404),
            (ConflictError("taken"), 409),
            (InvalidCursorError("abc"), 400),
            (DatetimeParseError("yesterday"), 400),
            (UnsupportedProviderError("apple", "historical sync"), 400),
        ],
    )
    def test_status_code(self, error: AppError, status_code: int) -> None:
        assert error.status_code == status_code
        assert error.is_client_error is (status_code < 500)

    def test_authentication_error_sends_a_bearer_challenge(self) -> None:
        assert AuthenticationError("who?").headers == {"WWW-Authenticate": "Bearer"}
        assert NotFoundError("gone").headers is None

    def test_datetime_parse_error_is_still_a_value_error(self) -> None:
        # pydantic validators turn a ValueError into a validation error
        assert isinstance(DatetimeParseError("yesterday"), ValueError)

    def test_details(self) -> None:
        assert InvalidCursorError("abc").detail == "Invalid cursor format: 'abc'. Expected 'timestamp|id'."
        assert UnsupportedProviderError("apple", "historical sync").detail == (
            "Provider 'apple' does not support historical sync."
        )


def _integrity_error(orig_type: type[Exception], table_name: str | None) -> IntegrityError:
    orig = MagicMock(spec=orig_type)
    orig.diag.table_name = table_name
    orig.diag.message_detail = "Key (email)=(jane@example.com) already exists."
    return IntegrityError("stmt", {}, orig)


class TestAppErrorFromIntegrityError:
    def test_unique_violation_names_the_table(self) -> None:
        error = app_error_from_integrity_error(_integrity_error(UniqueViolation, "user_connection"))

        assert isinstance(error, ConflictError)
        assert error.detail == "User connection already exists."

    def test_unique_violation_never_echoes_the_values(self) -> None:
        error = app_error_from_integrity_error(_integrity_error(UniqueViolation, "user"))

        assert error is not None
        assert "jane@example.com" not in error.detail
        assert "email" not in error.detail

    def test_unique_violation_without_diagnostics(self) -> None:
        error = app_error_from_integrity_error(_integrity_error(UniqueViolation, None))

        assert isinstance(error, ConflictError)
        assert error.detail == "Resource already exists."

    def test_foreign_key_violation_is_invalid_input(self) -> None:
        error = app_error_from_integrity_error(_integrity_error(ForeignKeyViolation, "event_record"))

        assert isinstance(error, InvalidInputError)
        assert error.detail == "Referenced resource does not exist."

    def test_raw_psycopg_errors_are_translated_too(self) -> None:
        assert isinstance(app_error_from_integrity_error(ForeignKeyViolation("fk")), InvalidInputError)
        assert app_error_from_integrity_error(NotNullViolation("null")) is None

    def test_other_violations_are_not_the_clients_fault(self) -> None:
        exc = IntegrityError("stmt", {}, NotNullViolation("null value in column"))

        assert app_error_from_integrity_error(exc) is None


class TestProviderErrors:
    def test_label_spells_out_multi_word_providers(self) -> None:
        assert ProviderNotConnectedError("google_health").detail == "User is not connected to Google Health."
        assert ProviderError("garmin", upstream_status=500).detail == "Garmin API error (status 500)"

    @pytest.mark.parametrize("upstream_status", [400, 405, 415, 422])
    def test_a_refused_request_is_reported(self, upstream_status: int) -> None:
        """The provider refused what we sent: most likely our bug, e.g. after an API change."""
        error = ProviderError("garmin", upstream_status=upstream_status)

        assert error.request_rejected
        assert not is_upstream_outage(error)

    @pytest.mark.parametrize("upstream_status", [None, 500, 503, 401, 403, 404, 409, 410, 412, 429])
    def test_an_outage_or_a_users_state_is_not(self, upstream_status: int | None) -> None:
        error = ProviderError("garmin", upstream_status=upstream_status)

        assert not error.request_rejected
        assert is_upstream_outage(error)

    def test_the_caller_can_mark_a_refusal_the_status_does_not_show(self) -> None:
        """e.g. Withings reports a bad request in the body of an HTTP 200."""
        assert not is_upstream_outage(ProviderError("withings", request_rejected=True))

    def test_storage_failure_is_an_outage_and_a_missing_setting_is_not(self) -> None:
        assert is_upstream_outage(ServiceUnavailableError("Failed to complete upload: SlowDown"))
        assert not is_upstream_outage(ConfigurationError("S3 bucket not configured"))
