"""Tests for SuuntoWebhookHandler._process_workout payload normalization.

Regression coverage for two shapes returned by the Suunto REST API:
- `/v3/workouts/{workoutKey}` (webhook path): single workout dict under `payload`.
- `/v3/workouts` (periodic sync path): list of workouts under `payload`.

Bugs fixed:
1. Previous implementation iterated dict keys (strings) when `payload` was a
   dict, raising `'str' object has no attribute 'gear'` in `_process_single_workout`.
2. Fresh webhook payloads omit `stopTime`; the schema marked it as required so
   Pydantic validation crashed even after the iteration fix. `stopTime` is now
   optional with a `startTime + totalTime` fallback in `_normalize_workout`.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas.providers.suunto.workout_import import WorkoutJSON as SuuntoWorkoutJSON
from app.services.providers.suunto.webhook_handler import SuuntoWebhookHandler

WORKOUT_KEY = "test-workout-key-0001"
TRACE_ID = "trace-test"


@pytest.fixture
def live_workout_payload() -> dict:
    """Workout dict captured live from `/v3/workouts/{workoutKey}` (no `stopTime`, no `gear`)."""
    return {
        "workoutId": 0,
        "activityId": 0,
        "startTime": 1779025042670,
        "totalTime": 12.144,
        "estimatedFloorsClimbed": 0,
        "totalDistance": 53.0,
        "totalAscent": 2.4,
        "totalDescent": 0.0,
        "startPosition": {"x": 0.0, "y": 0.0},
        "stopPosition": {"x": 0.0, "y": 0.0},
        "centerPosition": {"x": 0.0, "y": 0.0},
        "maxSpeed": 35.9,
        "stepCount": 0,
        "recoveryTime": 0,
        "cumulativeRecoveryTime": 0,
        "rankings": {
            "totalTimeOnRouteRanking": {"originalRanking": 1, "originalNumberOfWorkouts": 1},
        },
        "extensionTypes": [
            "ALTITUDESTREAM",
            "BATTERYLEVELSTREAM",
            "DISTANCEDELTA",
            "FITNESS",
            "HEARTRATE",
            "HEARTRATESTREAM",
            "INTENSITY",
            "LOCATIONSTREAM",
            "SEALEVELPRESSURESTREAM",
            "SML",
            "SPEEDSTREAM",
            "SUMMARY",
            "TEMPERATURESTREAM",
            "VERTICALSPEEDSTREAM",
            "WEATHER",
        ],
        "minAltitude": 875.0,
        "maxAltitude": 900.0,
        "isEdited": False,
        "isManuallyAdded": False,
        "tss": {
            "calculationMethod": "HR",
            "trainingStressScore": 0.09691667,
            "intensityFactor": None,
            "normalizedPower": None,
            "averageGradeAdjustedPace": 26.675264,
        },
        "tssList": [
            {
                "calculationMethod": "HR",
                "trainingStressScore": 0.09691667,
                "intensityFactor": None,
                "normalizedPower": None,
                "averageGradeAdjustedPace": 26.675264,
            },
            {
                "calculationMethod": "PACE",
                "trainingStressScore": 15.870654,
                "intensityFactor": 9.187365,
                "normalizedPower": None,
                "averageGradeAdjustedPace": 26.675264,
            },
            {
                "calculationMethod": "MET",
                "trainingStressScore": 0.11806667,
                "intensityFactor": None,
                "normalizedPower": None,
                "averageGradeAdjustedPace": None,
            },
        ],
        "avgSpeedInKmH": 15.696000000000002,
        "avgSpeed": 4.36,
        "avgPace": 3.82,
        "commentCount": 0,
        "timeOffsetInMinutes": 120,
        "pictureCount": 0,
        "hrdata": {
            "workoutMaxHR": 79,
            "workoutAvgHR": 78,
            "userMaxHR": 196,
            "hrmax": 79,
            "avg": 78,
            "max": 196,
        },
        "cadence": {"max": 0, "avg": 0},
        "energyConsumption": 0,
        "workoutKey": WORKOUT_KEY,
        "viewCount": 0,
    }


@pytest.fixture
def live_response(live_workout_payload: dict) -> dict:
    """Full `/v3/workouts/{workoutKey}` response wrapping the single workout under `payload`."""
    return {
        "error": None,
        "payload": live_workout_payload,
        "metadata": {"ts": "1779025734324"},
    }


class TestProcessWorkoutPayloadShapes:
    """Verify `_process_workout` handles both single-dict and list `payload` shapes."""

    @pytest.fixture
    def handler(self) -> SuuntoWebhookHandler:
        return SuuntoWebhookHandler(suunto_workouts=MagicMock(), suunto_247=MagicMock())

    @pytest.fixture
    def webhook_payload(self) -> dict:
        return {"workout": {"workoutKey": WORKOUT_KEY}}

    def test_single_object_payload_processed_once(
        self,
        handler: SuuntoWebhookHandler,
        webhook_payload: dict,
        live_response: dict,
        live_workout_payload: dict,
    ) -> None:
        """Single-dict `payload` (real webhook shape) is processed exactly once with the dict itself."""
        handler.suunto_workouts.get_workout_detail.return_value = live_response

        result = handler._process_workout(MagicMock(), uuid4(), webhook_payload, TRACE_ID)

        handler.suunto_workouts.process_push_activity.assert_called_once()
        passed = handler.suunto_workouts.process_push_activity.call_args.args[2]
        assert passed == live_workout_payload
        assert result == {"status": "saved", "workout_key": WORKOUT_KEY, "saved_count": 1}

    def test_list_payload_processes_each_entry(
        self,
        handler: SuuntoWebhookHandler,
        webhook_payload: dict,
        live_workout_payload: dict,
    ) -> None:
        """List `payload` (sync shape) iterates each workout dict."""
        second_workout = {**live_workout_payload, "workoutKey": "second"}
        handler.suunto_workouts.get_workout_detail.return_value = {
            "error": None,
            "payload": [live_workout_payload, second_workout],
            "metadata": {"ts": "1779025734324"},
        }

        result = handler._process_workout(MagicMock(), uuid4(), webhook_payload, TRACE_ID)

        assert handler.suunto_workouts.process_push_activity.call_count == 2
        processed = [c.args[2] for c in handler.suunto_workouts.process_push_activity.call_args_list]
        assert processed == [live_workout_payload, second_workout]
        assert result == {"status": "saved", "workout_key": WORKOUT_KEY, "saved_count": 2}

    def test_missing_workout_key_returns_error(self, handler: SuuntoWebhookHandler) -> None:
        """`WORKOUT_CREATED` without a workoutKey/workoutId is rejected without an API call."""
        result = handler._process_workout(MagicMock(), uuid4(), {"workout": {}}, TRACE_ID)

        assert result == {"status": "error", "error": "Missing workoutKey in WORKOUT_CREATED payload"}
        handler.suunto_workouts.get_workout_detail.assert_not_called()
        handler.suunto_workouts.process_push_activity.assert_not_called()

    def test_duplicate_workout_returns_ignored_status(
        self,
        handler: SuuntoWebhookHandler,
        webhook_payload: dict,
        live_response: dict,
    ) -> None:
        """IntegrityError on save is caught, rolled back, and returned as an `ignored` status."""
        db = MagicMock()
        handler.suunto_workouts.get_workout_detail.return_value = live_response
        handler.suunto_workouts.process_push_activity.side_effect = IntegrityError(
            statement="INSERT INTO event_record ...",
            params={},
            orig=Exception("duplicate key value violates unique constraint ix_event_record_source_time"),
        )

        result = handler._process_workout(db, uuid4(), webhook_payload, TRACE_ID)

        assert result == {"status": "ignored", "reason": "duplicate_workout", "workout_key": WORKOUT_KEY}
        db.rollback.assert_called_once()


class TestLivePayloadParsing:
    """Verify the schema accepts the exact live response shape (no `stopTime`)."""

    def test_pydantic_parses_live_payload(self, live_workout_payload: dict) -> None:
        """Schema accepts a fresh webhook payload without `stopTime`."""
        workout = SuuntoWorkoutJSON(**live_workout_payload)

        assert workout.stopTime is None
        assert workout.startTime == live_workout_payload["startTime"]
        assert workout.totalTime == live_workout_payload["totalTime"]
        assert workout.workoutId == live_workout_payload["workoutId"]
        assert workout.gear is None
