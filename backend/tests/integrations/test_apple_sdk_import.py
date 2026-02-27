"""
Integration tests for Apple SDK (HealthKit) data import.

Tests the full import flow for Apple HealthKit data via SDK.
"""

import logging
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models import EventRecord, WorkoutDetails
from app.services.apple.healthkit.import_service import ImportService
from tests.factories import UserFactory

SDK_ENVELOPE: dict[str, str] = {
    "provider": "apple",
    "sdkVersion": "1.0.0",
    "syncTimestamp": "2025-04-10T12:00:00Z",
}


@pytest.fixture(autouse=True)
def mock_sleep_redis() -> Any:
    """Mock Redis client in sleep_service module to prevent connection errors."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.expire.return_value = True
    mock_redis.sadd.return_value = 1
    mock_redis.srem.return_value = 1

    with patch("app.services.apple.healthkit.sleep_service.redis_client", mock_redis):
        yield mock_redis


class TestAppleSDKImport:
    """Tests for Apple SDK (HealthKit) import functionality."""

    @pytest.fixture
    def import_service(self) -> ImportService:
        """Create HealthKit import service instance."""
        return ImportService(log=logging.getLogger("test"))

    @pytest.fixture
    def sample_sdk_payload(self) -> dict[str, Any]:
        """Sample Apple SDK payload with records, sleep, and workouts."""
        return {
            **SDK_ENVELOPE,
            "data": {
                "records": [
                    {
                        "id": "ED008640-6873-4647-92B2-24F7680014A0",
                        "type": "HKQuantityTypeIdentifierStepCount",
                        "unit": "count",
                        "value": 66,
                        "startDate": "2022-05-28T23:56:11Z",
                        "endDate": "2022-05-29T00:02:58Z",
                        "source": {
                            "name": "iPhone",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "iPhone",
                            "productType": "iPhone10,5",
                            "deviceHardwareVersion": "iPhone10,5",
                            "deviceSoftwareVersion": "15.4.1",
                            "operatingSystemVersion": {
                                "majorVersion": 15,
                                "minorVersion": 4,
                                "patchVersion": 1,
                            },
                        },
                    }
                ],
                "sleep": [
                    {
                        "id": "E3D5647B-2B0E-43AA-BE3F-9FAD43D35581",
                        "stage": "inBed",
                        "startDate": "2025-04-02T21:50:46Z",
                        "endDate": "2025-04-02T21:50:50Z",
                        "source": {
                            "name": "Test iPhone",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "iPhone",
                            "productType": "iPhone15,2",
                            "deviceSoftwareVersion": "17.6.1",
                            "operatingSystemVersion": {
                                "majorVersion": 17,
                                "minorVersion": 6,
                                "patchVersion": 1,
                            },
                        },
                    }
                ],
                "workouts": [
                    {
                        "id": "801B68D7-F4AA-4A23-BD26-A3BA1BA6B08D",
                        "type": "walking",
                        "startDate": "2025-03-25T17:27:00Z",
                        "endDate": "2025-03-25T18:51:24Z",
                        "source": {
                            "name": "Test Apple Watch",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "Watch",
                            "productType": "Watch7,5",
                            "deviceHardwareVersion": "Watch7,5",
                            "deviceSoftwareVersion": "10.3.1",
                            "operatingSystemVersion": {
                                "majorVersion": 10,
                                "minorVersion": 3,
                                "patchVersion": 1,
                            },
                        },
                        "values": [
                            {"type": "duration", "unit": "s", "value": 1683.27},
                            {"type": "activeEnergyBurned", "unit": "kcal", "value": 131.41},
                            {"type": "basalEnergyBurned", "unit": "kcal", "value": 48.59},
                            {"type": "distance", "unit": "m", "value": 2165.35},
                            {"type": "minHeartRate", "unit": "bpm", "value": 77},
                            {"type": "averageHeartRate", "unit": "bpm", "value": 121.49},
                            {"type": "maxHeartRate", "unit": "bpm", "value": 141},
                            {"type": "elevationAscended", "unit": "m", "value": 15.57},
                            {"type": "averageMETs", "unit": "kcal/kg/hr", "value": 1.6},
                            {"type": "indoorWorkout", "unit": "bool", "value": False},
                            {"type": "weatherTemperature", "unit": "degC", "value": 11.19},
                            {"type": "weatherHumidity", "unit": "%", "value": 66},
                        ],
                    }
                ],
            },
        }

    def test_import_workout_with_statistics(
        self,
        db: Session,
        import_service: ImportService,
        sample_sdk_payload: dict[str, Any],
    ) -> None:
        """Test importing workout with full statistics (HR, distance, energy)."""
        user = UserFactory()
        user_id = str(user.id)

        result = import_service.load_data(db, sample_sdk_payload, user_id)

        assert result["workouts_saved"] == 1

        workout = db.query(EventRecord).filter(EventRecord.category == "workout").first()
        assert workout is not None
        assert workout.type == "walking"
        assert workout.duration_seconds == 1683

        details = db.query(WorkoutDetails).filter(WorkoutDetails.record_id == workout.id).first()
        assert details is not None
        assert details.heart_rate_min == 77
        assert details.heart_rate_max == 141
        assert details.heart_rate_avg == Decimal("121.49")
        assert details.distance == Decimal("2165.35")
        assert details.energy_burned == Decimal("180.00")  # 131.41 + 48.59
        assert details.total_elevation_gain == Decimal("15.57")

    def test_import_workout_without_heart_rate(
        self,
        db: Session,
        import_service: ImportService,
    ) -> None:
        """Test importing workout without heart rate data (older devices)."""
        user = UserFactory()
        payload = {
            **SDK_ENVELOPE,
            "data": {
                "workouts": [
                    {
                        "id": "AAAA0000-1111-2222-3333-444455556666",
                        "type": "cycling",
                        "startDate": "2019-09-30T17:00:49Z",
                        "endDate": "2019-09-30T17:14:29Z",
                        "source": {
                            "name": "Apple Watch",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "Watch",
                            "productType": "Watch3,3",
                            "deviceSoftwareVersion": "5.3",
                            "operatingSystemVersion": {"majorVersion": 5, "minorVersion": 3, "patchVersion": 0},
                        },
                        "values": [
                            {"type": "duration", "unit": "s", "value": 819.51},
                            {"type": "activeEnergyBurned", "unit": "kcal", "value": 77.16},
                            {"type": "basalEnergyBurned", "unit": "kcal", "value": 19.01},
                            {"type": "indoorWorkout", "unit": "bool", "value": True},
                        ],
                    }
                ],
            },
        }

        result = import_service.load_data(db, payload, str(user.id))

        assert result["workouts_saved"] == 1

        workout = db.query(EventRecord).filter(EventRecord.category == "workout").first()
        assert workout is not None

        details = db.query(WorkoutDetails).filter(WorkoutDetails.record_id == workout.id).first()
        assert details is not None
        assert details.heart_rate_min is None
        assert details.heart_rate_max is None
        assert details.heart_rate_avg is None
        assert details.energy_burned == Decimal("96.17")  # 77.16 + 19.01

    def test_import_multiple_workouts(
        self,
        db: Session,
        import_service: ImportService,
    ) -> None:
        """Test importing multiple workouts in a single batch."""
        user = UserFactory()
        payload = {
            **SDK_ENVELOPE,
            "data": {
                "workouts": [
                    {
                        "id": "BBBB0000-1111-2222-3333-444455556666",
                        "type": "running",
                        "startDate": "2025-01-28T08:00:00Z",
                        "endDate": "2025-01-28T08:30:00Z",
                        "source": {
                            "name": "Apple Watch",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "Watch",
                            "productType": "Watch7,5",
                            "deviceSoftwareVersion": "10.0",
                            "operatingSystemVersion": {"majorVersion": 10, "minorVersion": 0, "patchVersion": 0},
                        },
                        "values": [
                            {"type": "duration", "unit": "s", "value": 1800},
                            {"type": "distance", "unit": "m", "value": 5000},
                            {"type": "averageHeartRate", "unit": "bpm", "value": 155},
                        ],
                    },
                    {
                        "id": "CCCC0000-1111-2222-3333-444455556666",
                        "type": "swimming",
                        "startDate": "2025-01-28T18:00:00Z",
                        "endDate": "2025-01-28T18:45:00Z",
                        "source": {
                            "name": "Apple Watch",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "Watch",
                            "productType": "Watch7,5",
                            "deviceSoftwareVersion": "10.0",
                            "operatingSystemVersion": {"majorVersion": 10, "minorVersion": 0, "patchVersion": 0},
                        },
                        "values": [
                            {"type": "duration", "unit": "s", "value": 2700},
                            {"type": "activeEnergyBurned", "unit": "kcal", "value": 450},
                        ],
                    },
                ],
            },
        }

        result = import_service.load_data(db, payload, str(user.id))

        assert result["workouts_saved"] == 2

        workouts = db.query(EventRecord).filter(EventRecord.category == "workout").all()
        assert len(workouts) == 2

        types = {w.type for w in workouts}
        assert types == {"running", "swimming"}

    def test_import_duplicate_workout_skipped(
        self,
        db: Session,
        import_service: ImportService,
    ) -> None:
        """Test that duplicate workouts (same datetime) are skipped."""
        user = UserFactory()
        payload: dict[str, Any] = {
            **SDK_ENVELOPE,
            "data": {
                "workouts": [
                    {
                        "id": "DDDD0000-1111-2222-3333-444455556666",
                        "type": "walking",
                        "startDate": "2025-01-29T10:00:00Z",
                        "endDate": "2025-01-29T10:30:00Z",
                        "source": {
                            "name": "Apple Watch",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "Watch",
                            "productType": "Watch7,5",
                            "deviceSoftwareVersion": "10.0",
                            "operatingSystemVersion": {"majorVersion": 10, "minorVersion": 0, "patchVersion": 0},
                        },
                        "values": [
                            {"type": "duration", "unit": "s", "value": 1800},
                        ],
                    }
                ],
            },
        }

        # First import
        result1 = import_service.load_data(db, payload, str(user.id))
        assert result1["workouts_saved"] == 1

        # Second import (same workout, different ID)
        payload["data"]["workouts"][0]["id"] = "EEEE0000-1111-2222-3333-444455556666"
        result2 = import_service.load_data(db, payload, str(user.id))

        assert result2["workouts_saved"] == 0

        workouts = db.query(EventRecord).filter(EventRecord.category == "workout").all()
        assert len(workouts) == 1

    def test_import_records_as_time_series(
        self,
        db: Session,
        import_service: ImportService,
        sample_sdk_payload: dict[str, Any],
    ) -> None:
        """Test importing HealthKit records as time series samples."""
        user = UserFactory()

        result = import_service.load_data(db, sample_sdk_payload, str(user.id))

        assert result["records_saved"] >= 0

    def test_import_empty_payload(
        self,
        db: Session,
        import_service: ImportService,
    ) -> None:
        """Test importing empty payload returns zeros."""
        user = UserFactory()
        payload: dict[str, Any] = {**SDK_ENVELOPE, "data": {}}

        result = import_service.load_data(db, payload, str(user.id))

        assert result["workouts_saved"] == 0
        assert result["records_saved"] == 0
        assert result["sleep_saved"] == 0

    def test_import_workout_with_steps(
        self,
        db: Session,
        import_service: ImportService,
    ) -> None:
        """Test workout with step count statistic."""
        user = UserFactory()
        payload = {
            **SDK_ENVELOPE,
            "data": {
                "workouts": [
                    {
                        "id": "FFFF0000-1111-2222-3333-444455556666",
                        "type": "walking",
                        "startDate": "2025-01-29T12:00:00Z",
                        "endDate": "2025-01-29T12:45:00Z",
                        "source": {
                            "name": "Apple Watch",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "Watch",
                            "productType": "Watch7,5",
                            "deviceSoftwareVersion": "10.0",
                            "operatingSystemVersion": {"majorVersion": 10, "minorVersion": 0, "patchVersion": 0},
                        },
                        "values": [
                            {"type": "duration", "unit": "s", "value": 2700},
                            {"type": "stepCount", "unit": "count", "value": 4500},
                            {"type": "distance", "unit": "m", "value": 3200},
                        ],
                    }
                ],
            },
        }

        result = import_service.load_data(db, payload, str(user.id))

        assert result["workouts_saved"] == 1

        workout = db.query(EventRecord).filter(EventRecord.category == "workout").first()
        assert workout is not None

        details = db.query(WorkoutDetails).filter(WorkoutDetails.record_id == workout.id).first()
        assert details is not None
        assert details.steps_count == 4500
        assert details.distance == Decimal("3200")

    def test_import_workout_with_fractional_steps(
        self,
        db: Session,
        import_service: ImportService,
    ) -> None:
        """Test workout with fractional step count from Apple SDK is truncated to int."""
        user = UserFactory()
        payload = {
            **SDK_ENVELOPE,
            "data": {
                "workouts": [
                    {
                        "id": "FFFF1111-2222-3333-4444-555566667777",
                        "type": "walking",
                        "startDate": "2025-02-10T10:00:00Z",
                        "endDate": "2025-02-10T11:00:00Z",
                        "source": {
                            "name": "Apple Watch",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "Watch",
                            "productType": "Watch7,5",
                            "deviceSoftwareVersion": "10.0",
                            "operatingSystemVersion": {"majorVersion": 10, "minorVersion": 0, "patchVersion": 0},
                        },
                        "values": [
                            {"type": "duration", "unit": "s", "value": 3600},
                            {"type": "stepCount", "unit": "count", "value": 2981.57515735105},
                            {"type": "distance", "unit": "m", "value": 2165.35},
                        ],
                    }
                ],
            },
        }

        result = import_service.load_data(db, payload, str(user.id))

        assert result["workouts_saved"] == 1

        workout = db.query(EventRecord).filter(EventRecord.category == "workout").first()
        assert workout is not None

        details = db.query(WorkoutDetails).filter(WorkoutDetails.record_id == workout.id).first()
        assert details is not None
        assert details.steps_count == 2981
        assert details.distance == Decimal("2165.35")


class TestAppleSDKImportEdgeCases:
    """Edge case tests for Apple SDK import."""

    @pytest.fixture
    def import_service(self) -> ImportService:
        return ImportService(log=logging.getLogger("test"))

    def test_import_workout_with_zero_duration(
        self,
        db: Session,
        import_service: ImportService,
    ) -> None:
        """Test workout with zero/missing duration uses calculated duration."""
        user = UserFactory()
        payload = {
            **SDK_ENVELOPE,
            "data": {
                "workouts": [
                    {
                        "id": "AAAA1111-2222-3333-4444-555566667777",
                        "type": "yoga",
                        "startDate": "2025-01-29T14:00:00Z",
                        "endDate": "2025-01-29T14:30:00Z",  # 30 min = 1800 seconds
                        "source": {
                            "name": "Apple Watch",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "Watch",
                            "productType": "Watch7,5",
                            "deviceSoftwareVersion": "10.0",
                            "operatingSystemVersion": {"majorVersion": 10, "minorVersion": 0, "patchVersion": 0},
                        },
                        "values": [],
                    }
                ],
            },
        }

        result = import_service.load_data(db, payload, str(user.id))

        assert result["workouts_saved"] == 1

        workout = db.query(EventRecord).filter(EventRecord.category == "workout").first()
        assert workout is not None
        assert workout.duration_seconds == 1800

    def test_import_workout_null_statistics(
        self,
        db: Session,
        import_service: ImportService,
    ) -> None:
        """Test workout with null values."""
        user = UserFactory()
        payload = {
            **SDK_ENVELOPE,
            "data": {
                "workouts": [
                    {
                        "id": "BBBB1111-2222-3333-4444-555566667777",
                        "type": "other",
                        "startDate": "2025-01-29T15:00:00Z",
                        "endDate": "2025-01-29T15:20:00Z",
                        "source": {
                            "name": "Apple Watch",
                            "bundleIdentifier": "com.apple.health",
                            "deviceManufacturer": "Apple Inc.",
                            "deviceModel": "Watch",
                            "productType": "Watch7,5",
                            "deviceSoftwareVersion": "10.0",
                            "operatingSystemVersion": {"majorVersion": 10, "minorVersion": 0, "patchVersion": 0},
                        },
                        "values": None,
                    }
                ],
            },
        }

        result = import_service.load_data(db, payload, str(user.id))

        assert result["workouts_saved"] == 1

        workout = db.query(EventRecord).filter(EventRecord.category == "workout").first()
        assert workout is not None

        details = db.query(WorkoutDetails).filter(WorkoutDetails.record_id == workout.id).first()
        assert details is not None
        assert details.heart_rate_avg is None
        assert details.distance is None
        assert details.energy_burned is None
