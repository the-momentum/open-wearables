"""
Tests for schema validation.

Tests cover:
- EventRecordCreate validation
- EventRecordDetailCreate validation
- OAuthTokenResponse validation
- UserConnectionCreate validation
- Required field enforcement
- Type validation
- Optional field handling
- Edge cases and error messages
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.oauth import OAuthTokenResponse, UserConnectionCreate, ConnectionStatus


class TestEventRecordCreateValidation:
    """Test suite for EventRecordCreate schema validation."""

    def test_valid_event_record_create(self):
        """Should validate with all required fields."""
        # Arrange
        record_id = uuid4()
        user_id = uuid4()
        start_time = datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)

        # Act
        record = EventRecordCreate(
            id=record_id,
            user_id=user_id,
            category="workout",
            source_name="Apple Watch",
            start_datetime=start_time,
            end_datetime=end_time,
        )

        # Assert
        assert record.id == record_id
        assert record.user_id == user_id
        assert record.category == "workout"
        assert record.source_name == "Apple Watch"

    def test_missing_required_field_source_name(self):
        """Should raise ValidationError when source_name is missing."""
        # Arrange
        record_id = uuid4()
        user_id = uuid4()

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            EventRecordCreate(
                id=record_id,
                user_id=user_id,
                start_datetime=datetime.now(timezone.utc),
                end_datetime=datetime.now(timezone.utc),
            )

        assert "source_name" in str(exc_info.value)

class TestEventRecordDetailCreateValidation:
    """Test suite for EventRecordDetailCreate schema validation."""

    def test_valid_event_record_detail_create(self):
        """Should validate with all fields."""
        # Arrange
        record_id = uuid4()

        # Act
        detail = EventRecordDetailCreate(
            record_id=record_id,
            heart_rate_min=120,
            heart_rate_max=175,
            heart_rate_avg=Decimal("145.5"),
            steps_total=8500,
        )

        # Assert
        assert detail.record_id == record_id
        assert detail.heart_rate_min == 120
        assert detail.heart_rate_max == 175
        assert detail.heart_rate_avg == Decimal("145.5")
        assert detail.steps_total == 8500

    def test_missing_required_field_record_id(self):
        """Should raise ValidationError when record_id is missing."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            EventRecordDetailCreate(
                heart_rate_min=120,
                heart_rate_max=175,
            )

        assert "record_id" in str(exc_info.value)


class TestOAuthTokenResponseValidation:
    """Test suite for OAuthTokenResponse schema validation."""

    def test_valid_oauth_token_response(self):
        """Should validate with all required fields."""
        # Act
        response = OAuthTokenResponse(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=3600,
        )

        # Assert
        assert response.access_token == "test_access_token"
        assert response.token_type == "Bearer"
        assert response.expires_in == 3600

    def test_missing_required_field_access_token(self):
        """Should raise ValidationError when access_token is missing."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            OAuthTokenResponse(
                token_type="Bearer",
                expires_in=3600,
            )

        assert "access_token" in str(exc_info.value)

    def test_missing_required_field_token_type(self):
        """Should raise ValidationError when token_type is missing."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            OAuthTokenResponse(
                access_token="test_token",
                expires_in=3600,
            )

        assert "token_type" in str(exc_info.value)

class TestUserConnectionCreateValidation:
    """Test suite for UserConnectionCreate schema validation."""

    def test_valid_user_connection_create(self):
        """Should validate with all required fields."""
        # Arrange
        user_id = uuid4()
        expires_at = datetime.now(timezone.utc)

        # Act
        connection = UserConnectionCreate(
            user_id=user_id,
            provider="garmin",
            access_token="test_access_token",
            token_expires_at=expires_at,
        )

        # Assert
        assert connection.user_id == user_id
        assert connection.provider == "garmin"
        assert connection.access_token == "test_access_token"
        assert connection.token_expires_at == expires_at
        assert connection.status == ConnectionStatus.ACTIVE

    def test_missing_required_field_provider(self):
        """Should raise ValidationError when provider is missing."""
        # Arrange
        user_id = uuid4()

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserConnectionCreate(
                user_id=user_id,
                access_token="test_token",
                token_expires_at=datetime.now(timezone.utc),
            )

        assert "provider" in str(exc_info.value)

    def test_default_status_is_active(self):
        """Should set default status to ACTIVE."""
        # Arrange
        user_id = uuid4()

        # Act
        connection = UserConnectionCreate(
            user_id=user_id,
            provider="garmin",
            access_token="test_token",
            token_expires_at=datetime.now(timezone.utc),
        )

        # Assert
        assert connection.status == ConnectionStatus.ACTIVE
