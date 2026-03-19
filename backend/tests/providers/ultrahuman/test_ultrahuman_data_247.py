"""
Tests for Ultrahuman 24/7 data implementation.

Tests the Ultrahuman247Data class for sleep, recovery, and activity data handling.
"""

from sqlalchemy.orm import Session

from app.services.providers.ultrahuman.data_247 import Ultrahuman247Data
from app.services.providers.ultrahuman.oauth import UltrahumanOAuth
from tests.factories import UserFactory


class TestUltrahuman247Data:
    """Test suite for Ultrahuman247Data."""

    def test_ultrahuman_247_initialization(self, db: Session) -> None:
        """Should initialize Ultrahuman247Data successfully."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        # Act
        data_247 = Ultrahuman247Data(
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
            oauth=oauth,
        )

        # Assert
        assert data_247.provider_name == "ultrahuman"
        assert data_247.api_base_url == "https://partner.ultrahuman.com"
        assert data_247.oauth is not None


class TestUltrahumanSleepData:
    """Tests for Ultrahuman sleep data handling."""

    def test_normalize_sleep_with_complete_data(self, db: Session) -> None:
        """Test normalizing sleep data with all fields present."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        data_247 = Ultrahuman247Data(
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
            oauth=oauth,
        )

        raw_sleep = {
            "ultrahuman_date": "2025-01-14",
            "bedtime_start": 1736816400,  # 2025-01-14T01:00:00Z
            "bedtime_end": 1736928000,  # 2025-01-15T08:00:00Z
            "quick_metrics": [
                {"type": "time_in_bed", "value": 25200},
                {"type": "sleep_efic", "value": 90},
            ],
            "sleep_stages": [
                {"type": "deep_sleep", "stage_time": 3600},
                {"type": "rem_sleep", "stage_time": 5400},
                {"type": "light_sleep", "stage_time": 16200},
                {"type": "awake", "stage_time": 1800},
            ],
        }

        # Act
        normalized = data_247.normalize_sleep(raw_sleep, user.id)

        # Assert
        assert normalized["user_id"] == user.id
        assert normalized["provider"] == "ultrahuman"
        assert normalized["ultrahuman_date"] == "2025-01-14"
        assert normalized["start_time"].year == 2025
        assert normalized["end_time"].year == 2025
        assert normalized["duration_seconds"] == 25200
        assert normalized["efficiency_percent"] == 90
        assert normalized["stages"]["deep_seconds"] == 3600
        assert normalized["stages"]["rem_seconds"] == 5400
        assert normalized["stages"]["light_seconds"] == 16200

    def test_normalize_sleep_with_minimal_data(self, db: Session) -> None:
        """Test normalizing sleep data with minimal fields."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        data_247 = Ultrahuman247Data(
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
            oauth=oauth,
        )

        raw_sleep = {
            "ultrahuman_date": "2025-01-14",
        }

        # Act
        normalized = data_247.normalize_sleep(raw_sleep, user.id)

        # Assert
        assert normalized["user_id"] == user.id
        assert normalized["provider"] == "ultrahuman"
        assert normalized["ultrahuman_date"] == "2025-01-14"
        assert normalized["duration_seconds"] == 0
        assert normalized["efficiency_percent"] is None


class TestUltrahumanRecoveryData:
    """Tests for Ultrahuman recovery data handling."""

    def test_normalize_recovery_with_complete_data(self, db: Session) -> None:
        """Test normalizing recovery data with all fields present."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        data_247 = Ultrahuman247Data(
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
            oauth=oauth,
        )

        raw_recovery = {
            "ultrahuman_date": "2025-01-14",
            "recovery_index": {"value": 85},
            "movement_index": {"value": 72},
            "metabolic_score": {"value": 78},
        }

        # Act
        normalized = data_247.normalize_recovery(raw_recovery, user.id)

        # Assert
        assert normalized["user_id"] == user.id
        assert normalized["provider"] == "ultrahuman"
        assert normalized["date"] == "2025-01-14"
        assert normalized["recovery_index"] == 85
        assert normalized["movement_index"] == 72
        assert normalized["metabolic_score"] == 78


class TestUltrahumanActivitySamples:
    """Tests for Ultrahuman activity samples handling."""

    def test_normalize_activity_samples(self, db: Session) -> None:
        """Test normalizing activity samples."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        data_247 = Ultrahuman247Data(
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
            oauth=oauth,
        )

        raw_samples = [
            {
                "type": "hr",
                "values": [
                    {"timestamp": 1705309200, "value": 72},
                    {"timestamp": 1705309500, "value": 75},
                ],
            },
            {
                "type": "hrv",
                "values": [
                    {"timestamp": 1705309200, "value": 45},
                    {"timestamp": 1705309500, "value": 50},
                ],
            },
            {
                "type": "temp",
                "values": [
                    {"timestamp": 1705309200, "value": 36.5},
                    {"timestamp": 1705309500, "value": 36.6},
                ],
            },
            {
                "type": "steps",
                "values": [
                    {"timestamp": 1705309200, "value": 8500},
                ],
            },
        ]

        # Act
        normalized = data_247.normalize_activity_samples(raw_samples, user.id)

        # Assert
        assert "heart_rate" in normalized
        assert "hrv" in normalized
        assert "temperature" in normalized
        assert "steps" in normalized
        assert len(normalized["heart_rate"]) == 2
        assert len(normalized["hrv"]) == 2
        assert len(normalized["temperature"]) == 2
        assert len(normalized["steps"]) == 1
        assert normalized["heart_rate"][0]["value"] == 72
        assert normalized["hrv"][0]["value"] == 45
        assert normalized["temperature"][0]["value"] == 36.5
        assert normalized["steps"][0]["value"] == 8500
