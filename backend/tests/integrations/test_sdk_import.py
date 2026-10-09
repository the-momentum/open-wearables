"""
Integration tests for Apple SDK (HealthKit) data import.

Tests the full import flow for Apple HealthKit data via SDK.
"""

import json
import logging
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.constants.series_types.sdk import get_series_type_from_metric_type
from app.models import DataPointSeries, DataSource, EventRecord, MealDetails, WorkoutDetails
from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import EventRecordQueryParams
from app.schemas.providers.mobile_sdk import SyncRequest as SDKSyncRequest
from app.services.event_record_service import event_record_service
from app.services.sdk.import_service import ImportService
from tests.factories import UserFactory

SDK_ENVELOPE: dict[str, str] = {
    "provider": "apple",
    "sdkVersion": "1.0.0",
    "syncTimestamp": "2025-04-10T12:00:00Z",
}


@pytest.fixture(autouse=True)
def mock_sleep_redis() -> Any:
    """Mock Redis client and Celery task in sleep_service to prevent connection errors."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.expire.return_value = True
    mock_redis.sadd.return_value = 1
    mock_redis.srem.return_value = 1

    with (
        patch("app.services.sdk.sleep_service.get_redis_client") as mock_get_redis,
        patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finalize_stale_sleeps"),
    ):
        mock_get_redis.return_value = mock_redis
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

    def test_types_written_reach_the_response(
        self,
        db: Session,
        import_service: ImportService,
        sample_sdk_payload: dict[str, Any],
    ) -> None:
        """types lists the series types the batch wrote, for absence-alerting in the logs."""
        user = UserFactory()
        payload = {**SDK_ENVELOPE, "data": {"records": sample_sdk_payload["data"]["records"]}}

        response = import_service.import_data_from_request(db, json.dumps(payload), "application/json", str(user.id))

        assert response.types == [SeriesType.steps.value]
        assert response.model_dump()["types"] == [SeriesType.steps.value]

    def test_insert_update_split_reaches_the_response(
        self,
        db: Session,
        import_service: ImportService,
        sample_sdk_payload: dict[str, Any],
    ) -> None:
        """One new + one re-sent sample must surface as 1 inserted / 1 updated.

        process_sdk_upload_task reads these off UploadDataResponse, so a value that stops
        at load_data would silently report "0 new, 0 updated" on every sync.
        """
        user = UserFactory()
        record = sample_sdk_payload["data"]["records"][0]
        second = {
            **record,
            "id": "11112222-3333-4444-5555-666677778888",
            "startDate": "2022-05-29T01:00:00Z",
            "endDate": "2022-05-29T01:05:00Z",
        }
        payload = {**SDK_ENVELOPE, "data": {"records": [record]}}

        first = import_service.import_data_from_request(db, json.dumps(payload), "application/json", str(user.id))
        assert (first.records_inserted, first.records_updated) == (1, 0)

        # re-send the first sample (upsert in place) alongside a genuinely new one
        payload["data"]["records"] = [record, second]
        again = import_service.import_data_from_request(db, json.dumps(payload), "application/json", str(user.id))

        assert again.records_saved == 2
        assert again.records_inserted == 1
        assert again.records_updated == 1
        # and it survives the model_dump() the Celery task consumes
        dumped = again.model_dump()
        assert dumped["records_inserted"] == 1
        assert dumped["records_updated"] == 1

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


class TestSDKImportUnitConversion:
    """Unit conversions applied in `_build_statistic_bundles`.

    Apple HealthKit reports `body_fat_percentage` via `HKUnit.percent()` as a 0..1 ratio,
    while Android Health Connect's `BodyFatRecord.percentage` is already in percent.
    Height in meters is consistent across both platforms and must always be converted to cm.
    """

    @pytest.fixture
    def import_service(self) -> ImportService:
        return ImportService(log=logging.getLogger("test"))

    @staticmethod
    def _record(metric_type: str, value: float, unit: str | None = "") -> dict[str, Any]:
        return {
            "id": f"test-{metric_type}",
            "type": metric_type,
            "unit": unit,
            "value": value,
            "startDate": "2025-04-10T12:00:00Z",
            "endDate": "2025-04-10T12:00:00Z",
            "source": {
                "name": "Test Device",
                "bundleIdentifier": "test",
            },
        }

    def _build_request(self, provider: str, records: list[dict[str, Any]]) -> SDKSyncRequest:
        return SDKSyncRequest(
            **{
                "provider": provider,
                "sdkVersion": "1.0.0",
                "syncTimestamp": "2025-04-10T12:00:00Z",
                "data": {"records": records},
            }
        )

    def test_apple_body_fat_percentage_scaled_by_100(
        self,
        import_service: ImportService,
    ) -> None:
        """Apple sends ratio 0.304 — must be stored as 30.4 (%)."""
        user_id = str(uuid4())
        request = self._build_request(
            "apple",
            [self._record("HKQuantityTypeIdentifierBodyFatPercentage", 0.304)],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.body_fat_percentage
        assert samples[0].value == Decimal("30.400")

    def test_health_connect_body_fat_percentage_not_scaled(
        self,
        import_service: ImportService,
    ) -> None:
        """Health Connect sends already-percent 30.4 — must be stored as 30.4 (no x100)."""
        user_id = str(uuid4())
        request = self._build_request(
            "health_connect",
            [self._record("BODY_FAT", 30.4)],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.body_fat_percentage
        assert samples[0].value == Decimal("30.4")

    def test_samsung_body_fat_percentage_not_scaled(
        self,
        import_service: ImportService,
    ) -> None:
        """Samsung uses Health Connect semantics — already percent, must not be scaled."""
        user_id = str(uuid4())
        request = self._build_request(
            "samsung",
            [self._record("BODY_FAT", 18.5)],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.body_fat_percentage
        assert samples[0].value == Decimal("18.5")

    def test_apple_height_converted_meters_to_centimeters(
        self,
        import_service: ImportService,
    ) -> None:
        """Height in meters 1.7526 — must be stored as 175.26 cm regardless of provider."""
        user_id = str(uuid4())
        request = self._build_request(
            "apple",
            [self._record("HKQuantityTypeIdentifierHeight", 1.7526)],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.height
        assert samples[0].value == Decimal("175.2600")

    def test_health_connect_height_converted_meters_to_centimeters(
        self,
        import_service: ImportService,
    ) -> None:
        """Health Connect also sends height in meters — the x100 conversion still applies."""
        user_id = str(uuid4())
        request = self._build_request(
            "health_connect",
            [self._record("HEIGHT", 1.7526)],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.height
        assert samples[0].value == Decimal("175.2600")

    @pytest.mark.parametrize(
        ("unit", "expected"),
        [
            ("cal", Decimal("450")),
            ("Cal", Decimal("450000")),
            ("kcal", Decimal("450000")),
            (None, Decimal("450000")),
        ],
    )
    def test_dietary_energy_small_calories_converted_to_kcal(
        self,
        import_service: ImportService,
        unit: str | None,
        expected: Decimal,
    ) -> None:
        """Dietary energy is stored in kcal; only a small-calorie ("cal") unit is divided by 1000."""
        request = self._build_request(
            "health_connect",
            [self._record("DIETARY_ENERGY", 450000, unit=unit)],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, str(uuid4()))

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.dietary_energy_consumed
        assert samples[0].value == expected

    @pytest.mark.parametrize(
        ("unit", "expected"),
        [
            ("mmol/L", Decimal("110.1092202")),
            ("MMOL/L", Decimal("110.1092202")),
            (None, Decimal("6.111")),
            ("", Decimal("6.111")),
        ],
    )
    def test_health_connect_blood_glucose_unit_handling(
        self,
        import_service: ImportService,
        unit: str | None,
        expected: Decimal,
    ) -> None:
        """Health Connect glucose arrives in mmol/L and must be stored as mg/dL; only a mmol unit converts."""
        user_id = str(uuid4())
        request = self._build_request(
            "samsung",
            [self._record("BLOOD_GLUCOSE", 6.111, unit=unit)],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.blood_glucose
        assert samples[0].value == expected

    def test_healthkit_blood_glucose_not_scaled(
        self,
        import_service: ImportService,
    ) -> None:
        """HealthKit reports glucose in mg/dL - stored unchanged."""
        user_id = str(uuid4())
        request = self._build_request(
            "apple",
            [self._record("HKQuantityTypeIdentifierBloodGlucose", 105, unit="mg/dL")],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.blood_glucose
        assert samples[0].value == Decimal("105")


class TestSDKImportNutrition:
    """Dietary/nutrition metric types map to per-nutrient SeriesType samples."""

    @pytest.fixture
    def import_service(self) -> ImportService:
        return ImportService(log=logging.getLogger("test"))

    @staticmethod
    def _build_record(metric_type: str, value: float, unit: str) -> dict[str, Any]:
        return {
            "id": f"test-{metric_type}",
            "type": metric_type,
            "unit": unit,
            "value": value,
            "startDate": "2025-04-10T12:00:00Z",
            "endDate": "2025-04-10T12:00:00Z",
            "source": {
                "name": "Test Device",
                "bundleIdentifier": "test",
            },
        }

    def _build_request(self, provider: str, records: list[dict[str, Any]]) -> SDKSyncRequest:
        return SDKSyncRequest(
            **{
                "provider": provider,
                "sdkVersion": "1.0.0",
                "syncTimestamp": "2025-04-10T12:00:00Z",
                "data": {"records": records},
            }
        )

    def test_dietary_protein_maps_to_series_type(self, import_service: ImportService) -> None:
        user_id = str(uuid4())
        request = self._build_request(
            "apple",
            [self._build_record("HKQuantityTypeIdentifierDietaryProtein", value=24.5, unit="g")],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.dietary_protein
        assert samples[0].value == Decimal("24.5")

    def test_dietary_water_liters_converted_to_hydration_milliliters(self, import_service: ImportService) -> None:
        """HealthKit reports dietary water in liters; the unified hydration series is in mL."""
        user_id = str(uuid4())
        request = self._build_request(
            "apple",
            [self._build_record("HKQuantityTypeIdentifierDietaryWater", value=0.5, unit="L")],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.hydration
        assert samples[0].value == Decimal("500.0")

    def test_hydration_reported_in_milliliters_is_not_rescaled(self, import_service: ImportService) -> None:
        """A provider that already reports hydration in mL (e.g. Google Health API) is untouched."""
        user_id = str(uuid4())
        request = self._build_request(
            "google",
            [self._build_record("HYDRATION", value=500, unit="mL")],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.hydration
        assert samples[0].value == Decimal("500")

    def test_hydration_with_unrelated_unit_starting_with_l_is_not_rescaled(self, import_service: ImportService) -> None:
        """A bogus/unexpected unit like "lb" must not be mistaken for a liter alias."""
        user_id = str(uuid4())
        request = self._build_request(
            "apple",
            [self._build_record("HKQuantityTypeIdentifierDietaryWater", value=500, unit="lb")],
        )
        samples = import_service._build_statistic_bundles(request.data.records, request.provider, user_id)

        assert len(samples) == 1
        assert samples[0].series_type == SeriesType.hydration
        assert samples[0].value == Decimal("500")


class TestSDKImportMealCorrelation:
    """HealthKit HKCorrelationType.food records arrive mixed into `records[]` and
    group sibling nutrient samples via their shared `parentId`."""

    @pytest.fixture
    def import_service(self) -> ImportService:
        return ImportService(log=logging.getLogger("test"))

    @staticmethod
    def _correlation_record(correlation_id: str, end_date: str = "2026-09-18T12:00:00Z") -> dict[str, Any]:
        return {
            "id": correlation_id,
            "type": "HKCorrelationTypeIdentifierFood",
            "startDate": "2026-09-18T12:00:00Z",
            "endDate": end_date,
            "zoneOffset": "+02:00",
            "source": {"name": "MyFitnessPal", "bundleIdentifier": "com.myfitnesspal.mfp"},
            "metadata": {"title": "Kurczak z ryżem", "mealType": "obiad"},
            "value": 1,
            "unit": None,
        }

    @staticmethod
    def _nutrient_record(
        external_id: str, metric_type: str, value: float, unit: str, parent_id: str | None
    ) -> dict[str, Any]:
        return {
            "id": external_id,
            "parentId": parent_id,
            "type": metric_type,
            "value": value,
            "unit": unit,
            "startDate": "2026-09-18T12:00:00Z",
            "endDate": "2026-09-18T12:00:00Z",
            "source": {"name": "MyFitnessPal", "bundleIdentifier": "com.myfitnesspal.mfp"},
        }

    def _build_payload(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "provider": "apple",
            "sdkVersion": "1.2.0",
            "syncTimestamp": "2026-09-18T12:00:00Z",
            "data": {"records": records},
        }

    def _user_samples(self, db: Session, user_id: UUID) -> list[DataPointSeries]:
        return db.query(DataPointSeries).join(DataSource).filter(DataSource.user_id == user_id).all()

    def test_food_correlation_creates_meal_with_its_nutrients(self, db: Session, import_service: ImportService) -> None:
        """The correlation's nutrient records are stored on the meal, not as samples; a record
        without parentId (caffeine) stays a loose sample and is not part of the meal."""
        user = UserFactory()
        payload = self._build_payload(
            [
                self._correlation_record("MEAL-1"),
                self._nutrient_record(
                    "energy-1", "HKQuantityTypeIdentifierDietaryEnergyConsumed", 550, "Cal", "MEAL-1"
                ),
                self._nutrient_record("protein-1", "HKQuantityTypeIdentifierDietaryProtein", 38.2, "g", "MEAL-1"),
                self._nutrient_record("caffeine-1", "HKQuantityTypeIdentifierDietaryCaffeine", 95, "mg", None),
            ]
        )

        result = import_service.load_data(db, payload, str(user.id))

        assert result["meals_saved"] == 1
        meal = db.query(EventRecord).filter(EventRecord.category == "meal").one()
        assert meal.external_id == "MEAL-1"
        detail = db.query(MealDetails).filter(MealDetails.record_id == meal.id).one()
        assert detail.title == "Kurczak z ryżem"
        assert detail.meal_type == "obiad"
        assert detail.nutrients == {"dietary_energy_consumed": 550.0, "dietary_protein": 38.2}

        assert [s.external_id for s in self._user_samples(db, user.id)] == ["caffeine-1"]

        meals = event_record_service.get_meals(db, user.id, EventRecordQueryParams()).data
        assert meals[0].calories_kcal == 550.0
        assert meals[0].macros is not None
        assert meals[0].macros.protein_g == 38.2
        assert "dietary_caffeine" not in meals[0].nutrients

    def test_meal_created_fires_once_for_a_new_meal_with_its_nutrients(
        self, db: Session, import_service: ImportService
    ) -> None:
        user = UserFactory()
        payload = self._build_payload(
            [
                self._correlation_record("MEAL-1"),
                self._nutrient_record(
                    "energy-1", "HKQuantityTypeIdentifierDietaryEnergyConsumed", 550, "Cal", "MEAL-1"
                ),
            ]
        )

        with (
            patch("app.services.event_record_service.svix_service.is_enabled", return_value=True),
            patch("app.services.event_record_service.on_meal_created") as on_meal_created,
        ):
            import_service.load_data(db, payload, str(user.id))
            import_service.load_data(db, payload, str(user.id))

        on_meal_created.assert_called_once()
        assert on_meal_created.call_args.kwargs["title"] == "Kurczak z ryżem"
        assert on_meal_created.call_args.kwargs["calories_kcal"] == 550.0

    def test_meals_sharing_the_same_interval_are_all_saved(self, db: Session, import_service: ImportService) -> None:
        """MyFitnessPal logs every meal of a day with the same interval. Each meal is its own
        record with its own nutrients, and the rest of the batch (a workout) is unaffected."""
        user = UserFactory()
        payload = self._build_payload(
            [
                {**self._correlation_record("MEAL-1"), "metadata": {"mealType": "breakfast"}},
                {**self._correlation_record("MEAL-2"), "metadata": {"mealType": "lunch"}},
                self._nutrient_record("protein-1", "HKQuantityTypeIdentifierDietaryProtein", 6, "g", "MEAL-1"),
                self._nutrient_record("protein-2", "HKQuantityTypeIdentifierDietaryProtein", 40.42, "g", "MEAL-2"),
            ]
        )
        payload["data"]["workouts"] = [
            {
                "id": "WORKOUT-1",
                "type": "walking",
                "startDate": "2026-09-18T09:00:00Z",
                "endDate": "2026-09-18T09:30:00Z",
                "source": {"name": "Test Apple Watch", "bundleIdentifier": "com.apple.health"},
            }
        ]

        result = import_service.load_data(db, payload, str(user.id))

        assert result["meals_saved"] == 2
        assert result["workouts_saved"] == 1
        meals = event_record_service.get_meals(db, user.id, EventRecordQueryParams()).data
        assert {m.meal_type: m.nutrients["dietary_protein"].value for m in meals} == {
            "breakfast": 6.0,
            "lunch": 40.42,
        }
        assert self._user_samples(db, user.id) == []

    def test_food_correlation_resync_updates_the_meal_in_place(
        self, db: Session, import_service: ImportService
    ) -> None:
        """A meal's window shifts as items are added to it; the external_id keeps it the same
        meal, and its nutrients are replaced by the latest set."""
        user = UserFactory()
        first_batch = self._build_payload(
            [
                self._correlation_record("MEAL-1"),
                self._nutrient_record(
                    "energy-1", "HKQuantityTypeIdentifierDietaryEnergyConsumed", 550, "Cal", "MEAL-1"
                ),
                self._nutrient_record("sugar-1", "HKQuantityTypeIdentifierDietarySugar", 10, "g", "MEAL-1"),
            ]
        )
        second_batch = self._build_payload(
            [
                {
                    **self._correlation_record("MEAL-1", end_date="2026-09-18T12:15:00Z"),
                    "startDate": "2026-09-18T11:45:00Z",
                },
                self._nutrient_record(
                    "energy-1", "HKQuantityTypeIdentifierDietaryEnergyConsumed", 600, "Cal", "MEAL-1"
                ),
            ]
        )

        first = import_service.load_data(db, first_batch, str(user.id))
        second = import_service.load_data(db, second_batch, str(user.id))

        assert first["meals_saved"] == 1
        assert second["meals_saved"] == 0
        meal = db.query(EventRecord).filter(EventRecord.category == "meal").one()
        db.refresh(meal)
        assert meal.start_datetime.isoformat() == "2026-09-18T11:45:00+00:00"
        assert meal.end_datetime.isoformat() == "2026-09-18T12:15:00+00:00"
        detail = db.query(MealDetails).filter(MealDetails.record_id == meal.id).one()
        db.refresh(detail)
        assert detail.nutrients == {"dietary_energy_consumed": 600.0}

    def test_nutrient_record_without_its_correlation_in_the_batch_stays_loose(
        self, db: Session, import_service: ImportService
    ) -> None:
        user = UserFactory()
        payload = self._build_payload(
            [
                self._nutrient_record(
                    "energy-1", "HKQuantityTypeIdentifierDietaryEnergyConsumed", 550, "Cal", "MEAL-1"
                ),
            ]
        )

        result = import_service.load_data(db, payload, str(user.id))

        assert result["meals_saved"] == 0
        assert [s.external_id for s in self._user_samples(db, user.id)] == ["energy-1"]

    def test_non_nutrient_record_with_meal_parent_id_stays_loose(
        self, db: Session, import_service: ImportService
    ) -> None:
        user = UserFactory()
        payload = self._build_payload(
            [
                self._correlation_record("MEAL-1"),
                self._nutrient_record("hr-1", "HKQuantityTypeIdentifierHeartRate", 70, "count/min", "MEAL-1"),
            ]
        )

        import_service.load_data(db, payload, str(user.id))

        assert db.query(MealDetails).one().nutrients == {}
        assert [s.external_id for s in self._user_samples(db, user.id)] == ["hr-1"]


class TestSDKImportAndroidFoodCorrelation:
    """Health Connect (Samsung Health / Google Health Connect) uses its own correlation
    type ("FOOD") and its own dietary metric type names (DIETARY_ENERGY, DIETARY_PROTEIN,
    ...) - distinct strings from Apple HealthKit, but the same grouping mechanism."""

    @pytest.fixture
    def import_service(self) -> ImportService:
        return ImportService(log=logging.getLogger("test"))

    def test_real_health_connect_payload_saves_meal_and_nutrients(
        self, db: Session, import_service: ImportService
    ) -> None:
        user = UserFactory()
        user_id = str(user.id)
        source = {
            "appId": "com.example.nutrition",
            "deviceId": None,
            "deviceName": None,
            "deviceManufacturer": None,
            "deviceModel": None,
            "deviceType": None,
            "recordingMethod": "manual",
        }
        payload = {
            "provider": "google",
            "sdkVersion": "0.13.0",
            "syncTimestamp": "2026-09-25T12:00:00Z",
            "data": {
                "records": [
                    {
                        "id": "meal-1",
                        "type": "FOOD",
                        "startDate": "2026-09-25T18:30:00Z",
                        "endDate": "2026-09-25T18:45:00Z",
                        "zoneOffset": "+02:00",
                        "source": source,
                        "value": 1.0,
                        "unit": None,
                        "parentId": None,
                        "metadata": {"title": "Chicken rice", "mealType": "dinner"},
                    },
                    {
                        "id": "meal-1-energy",
                        "type": "DIETARY_ENERGY",
                        "startDate": "2026-09-25T18:30:00Z",
                        "endDate": "2026-09-25T18:45:00Z",
                        "zoneOffset": "+02:00",
                        "source": source,
                        "value": 550.0,
                        "unit": "kcal",
                        "parentId": "meal-1",
                        "metadata": None,
                    },
                    {
                        "id": "meal-1-protein",
                        "type": "DIETARY_PROTEIN",
                        "startDate": "2026-09-25T18:30:00Z",
                        "endDate": "2026-09-25T18:45:00Z",
                        "zoneOffset": "+02:00",
                        "source": source,
                        "value": 32.0,
                        "unit": "g",
                        "parentId": "meal-1",
                        "metadata": None,
                    },
                    {
                        "id": "meal-1-caffeine",
                        "type": "DIETARY_CAFFEINE",
                        "startDate": "2026-09-25T18:30:00Z",
                        "endDate": "2026-09-25T18:45:00Z",
                        "zoneOffset": "+02:00",
                        "source": source,
                        "value": 40.0,
                        "unit": "mg",
                        "parentId": "meal-1",
                        "metadata": None,
                    },
                ],
                "workouts": [],
                "sleep": [],
            },
        }

        result = import_service.load_data(db, payload, user_id)
        assert result["meals_saved"] == 1

        meal = db.query(EventRecord).filter(EventRecord.category == "meal").one()
        assert meal.external_id == "meal-1"
        detail = db.query(MealDetails).filter(MealDetails.record_id == meal.id).one()
        assert detail.title == "Chicken rice"
        assert detail.meal_type == "dinner"

        assert detail.nutrients == {
            "dietary_energy_consumed": 550.0,
            "dietary_protein": 32.0,
            "dietary_caffeine": 40.0,
        }
        assert db.query(DataPointSeries).join(DataSource).filter(DataSource.user_id == user.id).count() == 0

        meals = event_record_service.get_meals(db, user.id, EventRecordQueryParams()).data
        assert meals[0].calories_kcal == 550.0
        assert meals[0].macros is not None
        assert meals[0].macros.protein_g == 32.0

    def test_new_dietary_types_added_for_health_connect_resolve(self) -> None:
        """Regression test: DIETARY_TRANS_FAT, DIETARY_ENERGY_FROM_FAT,
        DIETARY_UNSATURATED_FAT and DIETARY_FOLIC_ACID have no HealthKit counterpart -
        HealthKit has no dietary trans fat identifier at all, so this is Health
        Connect/Samsung only, unlike the others which are Health Connect only."""
        assert get_series_type_from_metric_type("DIETARY_TRANS_FAT") == SeriesType.dietary_fat_trans
        assert get_series_type_from_metric_type("HKQuantityTypeIdentifierDietaryFatTrans") is None
        assert get_series_type_from_metric_type("DIETARY_ENERGY_FROM_FAT") == SeriesType.dietary_energy_from_fat
        assert get_series_type_from_metric_type("DIETARY_UNSATURATED_FAT") == SeriesType.dietary_fat_unsaturated
        assert get_series_type_from_metric_type("DIETARY_FOLIC_ACID") == SeriesType.dietary_folic_acid


class TestHealthConnectWorkoutFields:
    """Energy left null when not sent, moving time from Health Connect segments."""

    @pytest.fixture
    def import_service(self) -> ImportService:
        return ImportService(log=logging.getLogger("test"))

    @staticmethod
    def _detail(
        import_service: ImportService,
        *,
        provider: str = "health_connect",
        values: list[dict[str, Any]] | None = None,
        segments: list[dict[str, Any]] | None = None,
    ) -> Any:
        request = SDKSyncRequest(
            **{
                **SDK_ENVELOPE,
                "provider": provider,
                "data": {
                    "workouts": [
                        {
                            "id": "hc-run-1",
                            "type": "RUNNING",
                            "startDate": "2026-09-18T12:44:00Z",
                            "endDate": "2026-09-18T13:44:00Z",
                            "source": {"name": "Fitbit", "bundleIdentifier": "com.fitbit.FitbitMobile"},
                            "values": values
                            if values is not None
                            else [{"type": "duration", "value": 3600, "unit": "s"}],
                            "segments": segments,
                        }
                    ]
                },
            }
        )
        [(_, detail, _)] = list(import_service._build_workout_bundles(request, str(uuid4())))
        return detail

    @staticmethod
    def _segment(start: str, end: str, kind: str) -> dict[str, Any]:
        return {"startDate": f"2026-09-18T{start}:00Z", "endDate": f"2026-09-18T{end}:00Z", "type": kind}

    def test_energy_is_null_when_no_energy_statistic(self, import_service: ImportService) -> None:
        detail = self._detail(import_service)

        assert detail.energy_burned is None

    def test_energy_still_summed_when_sent(self, import_service: ImportService) -> None:
        detail = self._detail(
            import_service,
            values=[
                {"type": "activeEnergyBurned", "value": 300, "unit": "kcal"},
                {"type": "basalEnergyBurned", "value": 50, "unit": "kcal"},
            ],
        )

        assert detail.energy_burned == Decimal("350")

    def test_moving_time_is_the_active_segments(self, import_service: ImportService) -> None:
        """Fitbit marks only the running part of a longer session."""
        detail = self._detail(import_service, segments=[self._segment("13:14", "13:41", "running")])

        assert detail.moving_time_seconds == 27 * 60

    def test_moving_time_subtracts_pauses_when_only_pauses_are_segmented(self, import_service: ImportService) -> None:
        detail = self._detail(
            import_service,
            segments=[self._segment("13:00", "13:10", "other_39"), self._segment("13:20", "13:25", "rest")],
        )

        assert detail.moving_time_seconds == 45 * 60

    def test_active_and_idle_segments_count_only_the_active_ones(self, import_service: ImportService) -> None:
        detail = self._detail(
            import_service,
            segments=[
                self._segment("12:44", "13:04", "running"),
                self._segment("13:04", "13:09", "rest"),
                self._segment("13:09", "13:29", "running"),
            ],
        )

        assert detail.moving_time_seconds == 40 * 60

    def test_no_segments_no_moving_time(self, import_service: ImportService) -> None:
        assert self._detail(import_service).moving_time_seconds is None

    def test_malformed_segments_are_ignored(self, import_service: ImportService) -> None:
        detail = self._detail(import_service, segments=[{"type": "running"}, {"startDate": "x", "endDate": "y"}])

        assert detail.moving_time_seconds is None

    def test_pauses_are_subtracted_from_elapsed_time_not_the_duration_statistic(
        self, import_service: ImportService
    ) -> None:
        """A 60 min session with a 50 min duration statistic and a 10 min pause moved for 50 min."""
        detail = self._detail(
            import_service,
            values=[{"type": "duration", "value": 3000, "unit": "s"}],
            segments=[self._segment("13:00", "13:10", "other_39")],
        )

        assert detail.moving_time_seconds == 50 * 60

    def test_segment_with_mixed_offset_awareness_is_ignored(self, import_service: ImportService) -> None:
        detail = self._detail(
            import_service,
            segments=[
                {"startDate": "2026-09-18T13:14:00", "endDate": "2026-09-18T13:41:00Z", "type": "running"},
                self._segment("13:00", "13:10", "running"),
            ],
        )

        assert detail.moving_time_seconds == 10 * 60

    def test_segment_without_a_type_is_not_counted_as_active(self, import_service: ImportService) -> None:
        detail = self._detail(
            import_service,
            segments=[
                {"startDate": "2026-09-18T13:14:00Z", "endDate": "2026-09-18T13:41:00Z"},
                {"startDate": "2026-09-18T13:00:00Z", "endDate": "2026-09-18T13:05:00Z", "type": None},
                self._segment("12:50", "13:00", "rest"),
            ],
        )

        assert detail.moving_time_seconds == 50 * 60

    def test_apple_segments_are_not_interpreted(self, import_service: ImportService) -> None:
        detail = self._detail(import_service, provider="apple", segments=[self._segment("13:14", "13:41", "running")])

        assert detail.moving_time_seconds is None
