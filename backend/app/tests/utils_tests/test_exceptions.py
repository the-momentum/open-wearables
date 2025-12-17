"""
Tests for exception utilities.

Tests custom exceptions, exception handlers, and exception decorator.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.exceptions import HTTPException, RequestValidationError
from psycopg.errors import IntegrityError as PsycopgIntegrityError
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError

from app.utils.exceptions import (
    ResourceNotFoundError,
    handle_exception,
    handle_exceptions,
)


class TestResourceNotFoundError:
    """Test suite for ResourceNotFoundError exception."""

    def test_init_with_entity_name_only(self):
        """Test creating error with only entity name."""
        # Arrange
        entity_name = "User"

        # Act
        error = ResourceNotFoundError(entity_name)

        # Assert
        assert error.entity_name == entity_name
        assert error.detail == "User not found."

    def test_init_with_entity_name_and_int_id(self):
        """Test creating error with entity name and integer ID."""
        # Arrange
        entity_name = "user"
        entity_id = 123

        # Act
        error = ResourceNotFoundError(entity_name, entity_id)

        # Assert
        assert error.entity_name == entity_name
        assert error.detail == "User with ID: 123 not found."

    def test_init_with_entity_name_and_uuid_id(self):
        """Test creating error with entity name and UUID."""
        # Arrange
        entity_name = "device"
        entity_id = uuid4()

        # Act
        error = ResourceNotFoundError(entity_name, entity_id)

        # Assert
        assert error.entity_name == entity_name
        assert str(entity_id) in error.detail
        assert error.detail == f"Device with ID: {entity_id} not found."

    def test_init_capitalizes_entity_name(self):
        """Test that entity name is capitalized in detail message."""
        # Arrange
        entity_name = "provider"
        entity_id = 456

        # Act
        error = ResourceNotFoundError(entity_name, entity_id)

        # Assert
        assert error.detail.startswith("Provider")

    def test_init_with_none_id(self):
        """Test creating error with None as entity_id."""
        # Arrange
        entity_name = "session"

        # Act
        error = ResourceNotFoundError(entity_name, None)

        # Assert
        assert error.detail == "Session not found."


class TestHandleExceptionWithSQLAIntegrityError:
    """Test suite for handle_exception with SQLAlchemy IntegrityError."""

    def test_handle_sqlalchemy_integrity_error(self):
        """Test handling SQLAlchemy IntegrityError."""
        # Arrange
        error_msg = "duplicate key value violates unique constraint"
        exc = SQLAIntegrityError("statement", "params", error_msg)
        entity = "user"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert isinstance(result, HTTPException)
        assert result.status_code == 400
        assert "User entity already exists" in result.detail
        assert error_msg in result.detail

    def test_handle_sqlalchemy_integrity_error_capitalizes_entity(self):
        """Test that entity name is capitalized in error message."""
        # Arrange
        exc = SQLAIntegrityError("statement", "params", "error details")
        entity = "device"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert result.detail.startswith("Device")


class TestHandleExceptionWithPsycopgIntegrityError:
    """Test suite for handle_exception with Psycopg IntegrityError."""

    def test_handle_psycopg_integrity_error(self):
        """Test handling Psycopg IntegrityError."""
        # Arrange
        error_msg = "unique constraint violation"
        exc = PsycopgIntegrityError(error_msg)
        entity = "provider"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert isinstance(result, HTTPException)
        assert result.status_code == 400
        assert "Provider entity already exists" in result.detail

    def test_handle_psycopg_integrity_error_with_complex_message(self):
        """Test handling Psycopg IntegrityError with complex error message."""
        # Arrange
        error_msg = 'duplicate key value violates unique constraint "users_email_key"'
        exc = PsycopgIntegrityError(error_msg)
        entity = "user"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert result.status_code == 400
        assert error_msg in result.detail


class TestHandleExceptionWithResourceNotFoundError:
    """Test suite for handle_exception with ResourceNotFoundError."""

    def test_handle_resource_not_found_error(self):
        """Test handling ResourceNotFoundError."""
        # Arrange
        exc = ResourceNotFoundError("session", 999)
        entity = "session"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert isinstance(result, HTTPException)
        assert result.status_code == 404
        assert result.detail == exc.detail

    def test_handle_resource_not_found_error_preserves_detail(self):
        """Test that ResourceNotFoundError detail is preserved."""
        # Arrange
        exc = ResourceNotFoundError("user")
        entity = "user"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert result.detail == "User not found."


class TestHandleExceptionWithAttributeError:
    """Test suite for handle_exception with AttributeError."""

    def test_handle_attribute_error(self):
        """Test handling AttributeError."""
        # Arrange
        error_msg = "'NoneType' object has no attribute 'name'"
        exc = AttributeError(error_msg)
        entity = "device"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert isinstance(result, HTTPException)
        assert result.status_code == 400
        assert "Device doesn't support attribute or method" in result.detail
        assert error_msg in result.detail

    def test_handle_attribute_error_capitalizes_entity(self):
        """Test that entity name is capitalized in AttributeError."""
        # Arrange
        exc = AttributeError("attribute error")
        entity = "provider"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert result.detail.startswith("Provider")


class TestHandleExceptionWithRequestValidationError:
    """Test suite for handle_exception with RequestValidationError."""

    def test_handle_request_validation_error_with_msg_and_ctx(self):
        """Test handling RequestValidationError with message and context."""
        # Arrange
        error_data = [
            {
                "msg": "Invalid email format",
                "ctx": {"error": "Must be a valid email address"},
            },
        ]
        exc = RequestValidationError(error_data)
        entity = "user"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert isinstance(result, HTTPException)
        assert result.status_code == 400
        assert "Invalid email format - Must be a valid email address" in result.detail

    def test_handle_request_validation_error_with_msg_only(self):
        """Test handling RequestValidationError with message but no context."""
        # Arrange
        error_data = [{"msg": "Field required"}]
        exc = RequestValidationError(error_data)
        entity = "user"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert result.status_code == 400
        assert result.detail == "Field required"

    def test_handle_request_validation_error_with_empty_ctx(self):
        """Test handling RequestValidationError with empty context."""
        # Arrange
        error_data = [{"msg": "Validation failed", "ctx": {}}]
        exc = RequestValidationError(error_data)
        entity = "device"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert result.detail == "Validation failed"

    def test_handle_request_validation_error_with_none_ctx(self):
        """Test handling RequestValidationError with None context."""
        # Arrange
        error_data = [{"msg": "Type error", "ctx": None}]
        exc = RequestValidationError(error_data)
        entity = "session"

        # Act
        result = handle_exception(exc, entity)

        # Assert
        assert result.detail == "Type error"


class TestHandleExceptionWithUnknownError:
    """Test suite for handle_exception with unknown exception types."""

    def test_handle_unknown_exception_raises(self):
        """Test that unknown exception types are re-raised."""
        # Arrange
        exc = ValueError("Unknown error")
        entity = "user"

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown error"):
            handle_exception(exc, entity)

    def test_handle_custom_exception_raises(self):
        """Test that custom exceptions are re-raised."""

        # Arrange
        class CustomError(Exception):
            pass

        exc = CustomError("Custom error message")
        entity = "device"

        # Act & Assert
        with pytest.raises(CustomError):
            handle_exception(exc, entity)


class TestHandleExceptionsDecorator:
    """Test suite for handle_exceptions decorator."""

    def test_decorator_successful_execution(self):
        """Test decorator allows successful function execution."""
        # Arrange
        mock_service = MagicMock()
        mock_service.name = "test_service"

        @handle_exceptions
        def test_function(instance, arg1, arg2):
            return arg1 + arg2

        # Act
        result = test_function(mock_service, 5, 10)

        # Assert
        assert result == 15

    def test_decorator_handles_resource_not_found_error(self):
        """Test decorator converts ResourceNotFoundError to HTTPException."""
        # Arrange
        mock_service = MagicMock()
        mock_service.name = "user"

        @handle_exceptions
        def test_function(instance):
            raise ResourceNotFoundError("user", 123)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            test_function(mock_service)

        assert exc_info.value.status_code == 404
        assert "User with ID: 123 not found" in exc_info.value.detail

    def test_decorator_handles_integrity_error(self):
        """Test decorator converts IntegrityError to HTTPException."""
        # Arrange
        mock_service = MagicMock()
        mock_service.name = "provider"

        @handle_exceptions
        def test_function(instance):
            raise SQLAIntegrityError("stmt", "params", "duplicate key")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            test_function(mock_service)

        assert exc_info.value.status_code == 400
        assert "Provider entity already exists" in exc_info.value.detail

    def test_decorator_handles_attribute_error(self):
        """Test decorator converts AttributeError to HTTPException."""
        # Arrange
        mock_service = MagicMock()
        mock_service.name = "device"

        @handle_exceptions
        def test_function(instance):
            raise AttributeError("object has no attribute 'foo'")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            test_function(mock_service)

        assert exc_info.value.status_code == 400
        assert "Device doesn't support attribute or method" in exc_info.value.detail

    def test_decorator_uses_instance_name_for_entity(self):
        """Test decorator uses instance.name attribute for entity name."""
        # Arrange
        mock_service = MagicMock()
        mock_service.name = "custom_entity"

        @handle_exceptions
        def test_function(instance):
            raise ResourceNotFoundError("custom_entity", 999)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            test_function(mock_service)

        assert "Custom_entity with ID: 999 not found" in exc_info.value.detail

    def test_decorator_with_unknown_entity_name(self):
        """Test decorator with service instance without name attribute."""
        # Arrange
        mock_service = MagicMock()
        del mock_service.name  # Remove name attribute

        @handle_exceptions
        def test_function(instance):
            raise ResourceNotFoundError("resource", 1)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            test_function(mock_service)

        # Should default to "unknown"
        assert exc_info.value.status_code == 404

    def test_decorator_preserves_function_metadata(self):
        """Test decorator preserves original function metadata."""

        # Arrange
        @handle_exceptions
        def test_function():
            """Test function docstring."""
            pass

        # Assert
        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test function docstring."

    def test_decorator_with_args_and_kwargs(self):
        """Test decorator works with positional and keyword arguments."""
        # Arrange
        mock_service = MagicMock()
        mock_service.name = "test"

        @handle_exceptions
        def test_function(instance, arg1, arg2, kwarg1=None, kwarg2=None):
            return f"{arg1}-{arg2}-{kwarg1}-{kwarg2}"

        # Act
        result = test_function(mock_service, "a", "b", kwarg1="c", kwarg2="d")

        # Assert
        assert result == "a-b-c-d"
