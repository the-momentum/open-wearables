"""
Tests for conversion utility functions.

Tests SQLAlchemy model to dictionary conversion.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.schemas import ConnectionStatus
from app.schemas.oauth import ProviderName
from app.utils.conversion import base_to_dict
from tests.factories import (
    DataPointSeriesFactory,
    DeveloperFactory,
    EventRecordFactory,
    ExternalDeviceMappingFactory,
    UserConnectionFactory,
    UserFactory,
)


class TestBaseToDictUser:
    """Test suite for base_to_dict with User model."""

    def test_base_to_dict_user_basic(self, db: Session) -> None:
        """Test converting User model to dictionary."""
        # Arrange
        user = UserFactory(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
        )

        # Act
        result = base_to_dict(user)

        # Assert
        assert isinstance(result, dict)
        assert result["id"] == user.id
        assert result["email"] == "test@example.com"
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"

    def test_base_to_dict_user_with_external_id(self, db: Session) -> None:
        """Test converting User with external_user_id."""
        # Arrange
        user = UserFactory(
            email="external@example.com",
            external_user_id="ext-123",
        )

        # Act
        result = base_to_dict(user)

        # Assert
        assert result["external_user_id"] == "ext-123"

    def test_base_to_dict_user_datetime_serialization(self, db: Session) -> None:
        """Test that datetime fields are properly serialized to ISO format."""
        # Arrange
        user = UserFactory()

        # Act
        result = base_to_dict(user)

        # Assert
        assert "created_at" in result
        assert isinstance(result["created_at"], str)
        # Verify it's ISO format by parsing
        datetime.fromisoformat(result["created_at"])

    def test_base_to_dict_user_contains_all_columns(self, db: Session) -> None:
        """Test that all User model columns are included."""
        # Arrange
        user = UserFactory()

        # Act
        result = base_to_dict(user)

        # Assert
        expected_keys = {"id", "created_at", "email", "first_name", "last_name", "external_user_id"}
        assert expected_keys.issubset(result.keys())


class TestBaseToDictDeveloper:
    """Test suite for base_to_dict with Developer model."""

    def test_base_to_dict_developer_basic(self, db: Session) -> None:
        """Test converting Developer model to dictionary."""
        # Arrange
        developer = DeveloperFactory(
            email="dev@example.com",
        )

        # Act
        result = base_to_dict(developer)

        # Assert
        assert isinstance(result, dict)
        assert result["id"] == developer.id
        assert result["email"] == "dev@example.com"
        assert "hashed_password" in result

    def test_base_to_dict_developer_timestamps(self, db: Session) -> None:
        """Test that Developer timestamps are serialized correctly."""
        # Arrange
        developer = DeveloperFactory()

        # Act
        result = base_to_dict(developer)

        # Assert
        assert "created_at" in result
        assert "updated_at" in result
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)


class TestBaseToDictUserConnection:
    """Test suite for base_to_dict with UserConnection model."""

    def test_base_to_dict_user_connection(self, db: Session) -> None:
        """Test converting UserConnection model to dictionary."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
        )

        # Act
        result = base_to_dict(connection)

        # Assert
        assert isinstance(result, dict)
        assert result["id"] == connection.id
        assert result["user_id"] == user.id
        assert result["provider"] == "garmin"
        assert result["status"] == ConnectionStatus.ACTIVE

    def test_base_to_dict_user_connection_with_sync_time(self, db: Session) -> None:
        """Test UserConnection with last_synced_at timestamp."""
        # Arrange
        user = UserFactory()
        sync_time = datetime.now(timezone.utc)
        connection = UserConnectionFactory(
            user=user,
            provider="polar",
            last_synced_at=sync_time,
        )

        # Act
        result = base_to_dict(connection)

        # Assert
        assert "last_synced_at" in result
        assert isinstance(result["last_synced_at"], str)
        # Verify timestamp is serialized correctly
        parsed_time = datetime.fromisoformat(result["last_synced_at"])
        assert abs((parsed_time - sync_time).total_seconds()) < 1

    def test_base_to_dict_user_connection_includes_tokens(self, db: Session) -> None:
        """Test that sensitive token fields are included in conversion."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="suunto",
            access_token="test_access_token",
            refresh_token="test_refresh_token",
        )

        # Act
        result = base_to_dict(connection)

        # Assert
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["access_token"] == "test_access_token"
        assert result["refresh_token"] == "test_refresh_token"


class TestBaseToDictEventRecord:
    """Test suite for base_to_dict with EventRecord model."""

    def test_base_to_dict_event_record(self, db: Session) -> None:
        """Test converting EventRecord model to dictionary."""
        # Arrange
        mapping = ExternalDeviceMappingFactory()
        event = EventRecordFactory(
            mapping=mapping,
            category="workout",
            type_="running",
            source_name="Apple Watch",
            duration_seconds=3600,
        )

        # Act
        result = base_to_dict(event)

        # Assert
        assert isinstance(result, dict)
        assert result["id"] == event.id
        assert result["external_device_mapping_id"] == mapping.id
        assert result["category"] == "workout"
        assert result["type"] == "running"
        assert result["source_name"] == "Apple Watch"
        assert result["duration_seconds"] == 3600

    def test_base_to_dict_event_record_datetime_fields(self, db: Session) -> None:
        """Test EventRecord datetime serialization."""
        # Arrange
        mapping = ExternalDeviceMappingFactory()
        start_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)

        event = EventRecordFactory(
            mapping=mapping,
            start_datetime=start_time,
            end_datetime=end_time,
        )

        # Act
        result = base_to_dict(event)

        # Assert
        assert "start_datetime" in result
        assert "end_datetime" in result
        assert isinstance(result["start_datetime"], str)
        assert isinstance(result["end_datetime"], str)

        # Verify timestamps can be parsed back
        parsed_start = datetime.fromisoformat(result["start_datetime"])
        parsed_end = datetime.fromisoformat(result["end_datetime"])
        assert parsed_start.year == 2025
        assert parsed_end.hour == 11


class TestBaseToDictExternalDeviceMapping:
    """Test suite for base_to_dict with ExternalDeviceMapping model."""

    def test_base_to_dict_external_device_mapping(self, db: Session) -> None:
        """Test converting ExternalDeviceMapping model to dictionary."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(
            user=user,
            source=ProviderName.APPLE,
            device_id="device_123",
        )

        # Act
        result = base_to_dict(mapping)

        # Assert
        assert isinstance(result, dict)
        assert result["id"] == mapping.id
        assert result["user_id"] == user.id
        assert result["source"] == "apple"
        assert result["device_id"] == mapping.device_id


class TestBaseToDictDataPointSeries:
    """Test suite for base_to_dict with DataPointSeries model."""

    def test_base_to_dict_data_point_series(self, db: Session) -> None:
        """Test converting DataPointSeries model to dictionary."""
        # Arrange
        mapping = ExternalDeviceMappingFactory()
        timestamp = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        data_point = DataPointSeriesFactory(
            mapping=mapping,
            value=72.5,
            recorded_at=timestamp,
        )

        # Act
        result = base_to_dict(data_point)

        # Assert
        assert isinstance(result, dict)
        assert result["id"] == data_point.id
        assert result["external_device_mapping_id"] == mapping.id
        # DataPointSeries doesn't have category field, it has series_type_definition_id
        assert "series_type_definition_id" in result

    def test_base_to_dict_data_point_series_timestamp(self, db: Session) -> None:
        """Test DataPointSeries timestamp serialization."""
        # Arrange
        mapping = ExternalDeviceMappingFactory()
        data_point = DataPointSeriesFactory(mapping=mapping)

        # Act
        result = base_to_dict(data_point)

        # Assert
        # DataPointSeries uses recorded_at, not timestamp
        assert "recorded_at" in result
        assert isinstance(result["recorded_at"], str)
        # Verify can be parsed back
        datetime.fromisoformat(result["recorded_at"])


class TestBaseToDictEdgeCases:
    """Test suite for base_to_dict edge cases and special scenarios."""

    def test_base_to_dict_with_null_values(self, db: Session) -> None:
        """Test conversion when optional fields are None."""
        # Arrange
        user = UserFactory(external_user_id=None)

        # Act
        result = base_to_dict(user)

        # Assert
        assert "external_user_id" in result
        assert result["external_user_id"] is None

    def test_base_to_dict_with_uuid_fields(self, db: Session) -> None:
        """Test that UUID fields are properly converted."""
        # Arrange
        user = UserFactory()

        # Act
        result = base_to_dict(user)

        # Assert
        assert "id" in result
        # UUID should be preserved as-is (not converted to string in this function)
        assert result["id"] == user.id

    def test_base_to_dict_multiple_datetime_fields(self, db: Session) -> None:
        """Test model with multiple datetime fields."""
        # Arrange
        connection = UserConnectionFactory(
            last_synced_at=datetime.now(timezone.utc),
        )

        # Act
        result = base_to_dict(connection)

        # Assert
        datetime_fields = ["created_at", "updated_at", "token_expires_at"]
        for field in datetime_fields:
            assert field in result
            if result[field] is not None:
                assert isinstance(result[field], str)

    def test_base_to_dict_preserves_value_types(self, db: Session) -> None:
        """Test that non-datetime values preserve their types."""
        # Arrange
        event = EventRecordFactory(duration_seconds=3600)

        # Act
        result = base_to_dict(event)

        # Assert
        assert isinstance(result["duration_seconds"], int)
        assert result["duration_seconds"] == 3600

    def test_base_to_dict_with_float_values(self, db: Session) -> None:
        """Test conversion of float values."""
        # Arrange
        from decimal import Decimal

        data_point = DataPointSeriesFactory(value=98.6)

        # Act
        result = base_to_dict(data_point)

        # Assert
        # Value is stored as Decimal in database but should be converted to float or Decimal
        assert isinstance(result["value"], (float, Decimal))
        assert float(result["value"]) == 98.6

    def test_base_to_dict_idempotent(self, db: Session) -> None:
        """Test that calling base_to_dict multiple times gives same result."""
        # Arrange
        user = UserFactory()

        # Act
        result1 = base_to_dict(user)
        result2 = base_to_dict(user)

        # Assert
        assert result1 == result2

    def test_base_to_dict_returns_new_dict(self, db: Session) -> None:
        """Test that base_to_dict returns a new dictionary each time."""
        # Arrange
        user = UserFactory()

        # Act
        result1 = base_to_dict(user)
        result2 = base_to_dict(user)

        # Assert
        assert result1 is not result2  # Different objects
        assert result1 == result2  # But equal content


class TestBaseToDictIntegration:
    """Integration tests for base_to_dict with complex scenarios."""

    def test_convert_multiple_related_models(self, db: Session) -> None:
        """Test converting multiple related models."""
        # Arrange
        user = UserFactory(email="integration@example.com")
        mapping = ExternalDeviceMappingFactory(user=user)
        event = EventRecordFactory(mapping=mapping)

        # Act
        user_dict = base_to_dict(user)
        mapping_dict = base_to_dict(mapping)
        event_dict = base_to_dict(event)

        # Assert - All conversions should work
        assert user_dict["id"] == user.id
        assert mapping_dict["user_id"] == user.id
        assert event_dict["external_device_mapping_id"] == mapping.id

    def test_convert_models_with_same_user(self, db: Session) -> None:
        """Test converting multiple models referencing same user."""
        # Arrange
        user = UserFactory()
        mapping1 = ExternalDeviceMappingFactory(user=user, device_id="device-1")
        mapping2 = ExternalDeviceMappingFactory(user=user, device_id="device-2")

        # Act
        dict1 = base_to_dict(mapping1)
        dict2 = base_to_dict(mapping2)

        # Assert
        assert dict1["user_id"] == dict2["user_id"]
        assert dict1["device_id"] != dict2["device_id"]
