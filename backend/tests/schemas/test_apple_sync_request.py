"""Tests for Apple HealthKit sync request schema validation.

Tests that unknown type values are filtered out before Pydantic validation,
so the endpoint doesn't return 400 for new/unknown HealthKit types.
"""

from app.schemas.apple.healthkit.sync_request import SyncRequestData


def _make_record(type_value: str | None = "HKQuantityTypeIdentifierHeartRate", **overrides: object) -> dict:
    """Helper to create a minimal valid record dict."""
    record = {
        "uuid": "00000000-0000-0000-0000-000000000001",
        "type": type_value,
        "startDate": "2025-01-15T10:00:00Z",
        "endDate": "2025-01-15T10:05:00Z",
        "unit": "bpm",
        "value": 72,
    }
    record.update(overrides)
    return record


def _make_sleep(type_value: str | None = "HKCategoryTypeIdentifierSleepAnalysis", **overrides: object) -> dict:
    """Helper to create a minimal valid sleep dict."""
    sleep = {
        "uuid": "00000000-0000-0000-0000-000000000002",
        "type": type_value,
        "startDate": "2025-01-15T22:00:00Z",
        "endDate": "2025-01-15T22:30:00Z",
        "unit": None,
        "value": 3,
    }
    sleep.update(overrides)
    return sleep


def _make_workout(
    type_value: str | None = "running",
    statistics: list[dict] | None = None,
    **overrides: object,
) -> dict:
    """Helper to create a minimal valid workout dict."""
    workout: dict = {
        "uuid": "00000000-0000-0000-0000-000000000003",
        "type": type_value,
        "startDate": "2025-01-15T08:00:00Z",
        "endDate": "2025-01-15T08:30:00Z",
        "workoutStatistics": statistics or [{"type": "duration", "unit": "s", "value": 1800}],
    }
    workout.update(overrides)
    return workout


class TestFilterUnknownRecordTypes:
    def test_metric_record_with_valid_type_preserved(self) -> None:
        data = SyncRequestData.model_validate({"records": [_make_record()]})
        assert len(data.records) == 1
        assert data.records[0].type is not None
        assert data.records[0].type.value == "HKQuantityTypeIdentifierHeartRate"

    def test_metric_record_with_unknown_type_filtered_out(self) -> None:
        data = SyncRequestData.model_validate(
            {"records": [_make_record(type_value="HKQuantityTypeIdentifierSomeNewAppleType")]}
        )
        assert len(data.records) == 0

    def test_metric_record_with_none_type_preserved(self) -> None:
        data = SyncRequestData.model_validate({"records": [_make_record(type_value=None)]})
        assert len(data.records) == 1
        assert data.records[0].type is None


class TestFilterUnknownSleepTypes:
    def test_sleep_record_with_unknown_type_filtered_out(self) -> None:
        data = SyncRequestData.model_validate(
            {"sleep": [_make_sleep(type_value="HKCategoryTypeIdentifierSomeNewSleepType")]}
        )
        assert len(data.sleep) == 0


class TestFilterUnknownWorkoutTypes:
    def test_workout_with_unknown_type_filtered_out(self) -> None:
        data = SyncRequestData.model_validate({"workouts": [_make_workout(type_value="underwater_basket_weaving")]})
        assert len(data.workouts) == 0

    def test_workout_statistic_with_unknown_type_filtered_out(self) -> None:
        """Unknown stat is removed from workoutStatistics, workout itself is kept."""
        data = SyncRequestData.model_validate(
            {
                "workouts": [
                    _make_workout(
                        statistics=[
                            {"type": "duration", "unit": "s", "value": 1800},
                            {"type": "brandNewStatistic", "unit": "units", "value": 99.9},
                        ]
                    )
                ]
            }
        )
        assert len(data.workouts) == 1
        assert len(data.workouts[0].workoutStatistics) == 1
        assert data.workouts[0].workoutStatistics[0].type.value == "duration"


class TestMixedKnownAndUnknown:
    def test_mixed_known_and_unknown_types(self) -> None:
        """Valid items preserved, invalid items removed across all categories."""
        data = SyncRequestData.model_validate(
            {
                "records": [
                    _make_record(type_value="HKQuantityTypeIdentifierHeartRate"),
                    _make_record(type_value="HKQuantityTypeIdentifierFutureMetric"),
                ],
                "sleep": [
                    _make_sleep(),
                    _make_sleep(type_value="HKCategoryTypeIdentifierNewSleep"),
                ],
                "workouts": [
                    _make_workout(type_value="running"),
                    _make_workout(type_value="underwater_basket_weaving"),
                ],
            }
        )
        assert len(data.records) == 1
        assert len(data.sleep) == 1
        assert len(data.workouts) == 1

    def test_valid_payload_unchanged(self) -> None:
        """Standard valid payload passes through without any items removed."""
        data = SyncRequestData.model_validate(
            {
                "records": [
                    _make_record(type_value="HKQuantityTypeIdentifierHeartRate"),
                    _make_record(type_value="HKQuantityTypeIdentifierStepCount", unit="count", value=100),
                ],
                "sleep": [_make_sleep()],
                "workouts": [
                    _make_workout(
                        statistics=[
                            {"type": "duration", "unit": "s", "value": 1800},
                            {"type": "averageHeartRate", "unit": "bpm", "value": 150},
                        ]
                    )
                ],
            }
        )
        assert len(data.records) == 2
        assert len(data.sleep) == 1
        assert len(data.workouts) == 1
        assert len(data.workouts[0].workoutStatistics) == 2
