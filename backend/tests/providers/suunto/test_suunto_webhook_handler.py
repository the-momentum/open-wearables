"""Tests for SuuntoWebhookHandler._process_workout payload normalization.

Regression coverage for two shapes returned by the Suunto REST API:
- `/v3/workouts/{workoutKey}` (webhook path): single workout dict under `payload`.
- `/v3/workouts` (periodic sync path): list of workouts under `payload`.

Bugs fixed:
1. Previous implementation iterated dict keys (strings) when `payload` was a
   dict, raising `'str' object has no attribute 'gear'` in `process_push_activity`.
2. Fresh webhook payloads omit `stopTime`; the schema marked it as required so
   Pydantic validation crashed even after the iteration fix. `stopTime` is now
   optional with a `startTime + totalTime` fallback in `_normalize_workout`.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import EventRecord
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.providers.suunto.workout_import import WorkoutJSON as SuuntoWorkoutJSON
from app.services.providers.suunto.oauth import SuuntoOAuth
from app.services.providers.suunto.webhook_handler import SuuntoWebhookHandler
from app.services.providers.suunto.workouts import SuuntoWorkouts

WORKOUT_KEY = "test-workout-key-0001"
PAUSED_WORKOUT_KEY = "test-paused-workout-0001"
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


@pytest.fixture
def paused_workout_payload() -> dict:
    """Live `/v3/workouts/{workoutKey}?extensions=...` capture (anonymized) for a workout with two manual pauses.

    Active timer time: 210.56s. Pause durations: 69.92s + 20.77s = 90.69s.
    Elapsed time including pauses: 301.25s. Gear is shipped via SummaryExtension (Race 2 pattern).
    """
    return {
        "workoutId": 0,
        "activityId": 0,
        "startTime": 1700000000000,
        "totalTime": 210.56,
        "estimatedFloorsClimbed": 0,
        "totalDistance": 37.0,
        "totalAscent": 0.0,
        "totalDescent": 0.0,
        "startPosition": {"x": 0.0, "y": 0.0},
        "stopPosition": {"x": 0.0, "y": 0.0},
        "centerPosition": {"x": 0.0, "y": 0.0},
        "maxSpeed": 2.03,
        "stepCount": 46,
        "recoveryTime": 0,
        "cumulativeRecoveryTime": 0,
        "rankings": {
            "totalTimeOnRouteRanking": {"originalRanking": 2, "originalNumberOfWorkouts": 2},
        },
        "extensions": [
            {
                "type": "PauseMarkerExtension",
                "pauseMarkers": [
                    {"startTime": 1700000137500, "endTime": 1700000207420, "automatic": False},
                    {"startTime": 1700000235740, "endTime": 1700000256510, "automatic": False},
                ],
            },
            {
                "type": "SummaryExtension",
                "avgSpeed": 0.176,
                "avgPower": None,
                "maxPower": None,
                "avgCadence": 1.037,
                "maxCadence": 1.833,
                "ascent": 0.0,
                "descent": 0.0,
                "ascentTime": 0.0,
                "descentTime": 0.0,
                "pte": 1.1,
                "peakEpoc": 1.2,
                "performanceLevel": None,
                "recoveryTime": 0.0,
                "weather": None,
                "minTemperature": 302.6,
                "avgTemperature": 302.8,
                "maxTemperature": 302.9,
                "workoutType": None,
                "feeling": 5,
                "gear": {
                    "manufacturer": "Suunto",
                    "name": "Suunto Race 2",
                    "displayName": None,
                    "serialNumber": "TEST-SERIAL-0001",
                    "softwareVersion": "2.53.42",
                    "hardwareVersion": "Sailfish_RevA1",
                    "productType": "SPORT_WATCH",
                },
                "heartRateRecovery": {"comparisonLevel": "Invalid", "drop": 0, "level": "Invalid"},
            },
        ],
        "extensionTypes": [
            "ALTITUDESTREAM",
            "BATTERYLEVELSTREAM",
            "CADENCESTREAM",
            "DISTANCEDELTA",
            "FITNESS",
            "HEARTRATE",
            "HEARTRATESTREAM",
            "INTENSITY",
            "LOCATIONSTREAM",
            "PAUSEMARKER",
            "SEALEVELPRESSURESTREAM",
            "SML",
            "SPEEDSTREAM",
            "SUMMARY",
            "TEMPERATURESTREAM",
            "VERTICALSPEEDSTREAM",
            "WEATHER",
        ],
        "minAltitude": 920.0,
        "maxAltitude": 932.0,
        "isEdited": False,
        "isManuallyAdded": False,
        "tss": {
            "calculationMethod": "HR",
            "trainingStressScore": 1.75,
            "intensityFactor": None,
            "normalizedPower": None,
            "averageGradeAdjustedPace": 0.17576045,
        },
        "avgSpeedInKmH": 0.6335999965667725,
        "avgSpeed": 0.17599999904632568,
        "viewCount": 0,
        "pictureCount": 0,
        "commentCount": 0,
        "avgPace": 94.85,
        "timeOffsetInMinutes": 120,
        "energyConsumption": 17,
        "hrdata": {
            "workoutMaxHR": 92,
            "workoutAvgHR": 80,
            "userMaxHR": 190,
            "avg": 80,
            "hrmax": 92,
            "max": 190,
        },
        "cadence": {"max": 110, "avg": 62},
        "workoutKey": PAUSED_WORKOUT_KEY,
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

        handler.suunto_workouts.get_workout_detail.assert_called_once()
        requested_extensions = handler.suunto_workouts.get_workout_detail.call_args.kwargs["extensions"]
        assert "PauseMarkerExtension" in requested_extensions
        assert "SummaryExtension" in requested_extensions

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


class TestPauseAwarePayload:
    """Verify pause markers and gear are extracted from the `extensions` array."""

    def test_pause_markers_parsed_from_extension(self, paused_workout_payload: dict) -> None:
        workout = SuuntoWorkoutJSON(**paused_workout_payload)

        markers = workout.pause_markers
        assert len(markers) == 2
        # Durations preserved from the live capture: 69.92s + 20.77s = 90.69s.
        durations_ms = [m.duration_ms for m in markers]
        assert durations_ms == [69920, 20770]
        assert sum(durations_ms) == 90690

    def test_gear_extracted_from_summary_extension(self, paused_workout_payload: dict) -> None:
        """Race 2 ships gear inside SummaryExtension, not at the workout root."""
        workout = SuuntoWorkoutJSON(**paused_workout_payload)

        assert workout.gear is None
        gear = workout.gear_from_summary_extension
        assert gear is not None
        assert gear.name == "Suunto Race 2"
        assert gear.serialNumber == "TEST-SERIAL-0001"
        # AliasChoices: SummaryExtension.gear ships `softwareVersion`/`hardwareVersion`,
        # which must be exposed via the canonical `swVersion`/`hwVersion` attributes.
        assert gear.swVersion == "2.53.42"
        assert gear.hwVersion == "Sailfish_RevA1"

    def test_no_extensions_returns_empty(self, live_workout_payload: dict) -> None:
        """A payload without `extensions` yields no pause markers and no extension gear."""
        workout = SuuntoWorkoutJSON(**live_workout_payload)

        assert workout.pause_markers == []
        assert workout.gear_from_summary_extension is None

    def test_unknown_extension_type_does_not_raise(self) -> None:
        """Forward-compat: unrecognized extension `type` routes to UnknownExtension instead of failing validation."""
        payload = {
            "workoutId": 0,
            "activityId": 0,
            "startTime": 1700000000000,
            "totalTime": 1.0,
            "extensions": [{"type": "FutureExtensionWeDontKnow", "foo": "bar"}],
        }

        workout = SuuntoWorkoutJSON(**payload)

        assert workout.pause_markers == []
        assert workout.gear_from_summary_extension is None


class TestNormalizeWithPauses:
    """End-to-end: `_normalize_workout` must produce a pause-aware `end_datetime`."""

    @pytest.fixture
    def suunto_workouts(self) -> SuuntoWorkouts:
        connection_repo = UserConnectionRepository()
        oauth = SuuntoOAuth(
            user_repo=MagicMock(),
            connection_repo=connection_repo,
            provider_name="suunto",
            api_base_url="https://cloudapi.suunto.com",
        )
        return SuuntoWorkouts(
            workout_repo=EventRecordRepository(EventRecord),
            connection_repo=connection_repo,
            provider_name="suunto",
            api_base_url="https://cloudapi.suunto.com",
            oauth=oauth,
        )

    def test_end_datetime_includes_pauses(
        self,
        suunto_workouts: SuuntoWorkouts,
        paused_workout_payload: dict,
    ) -> None:
        """end_datetime = startTime + active_time + sum(pauses).

        Live capture: 210.56s active + 69.92s + 20.77s pauses = 301.25s elapsed.
        """
        workout = SuuntoWorkoutJSON(**paused_workout_payload)

        record, _ = suunto_workouts._normalize_workout(workout, uuid4())

        elapsed_seconds = (record.end_datetime - record.start_datetime).total_seconds()
        assert elapsed_seconds == pytest.approx(301.25, abs=0.01)
        # duration_seconds keeps the active timer time, unchanged by pauses.
        assert record.duration_seconds == 210

    def test_gear_pulled_from_summary_extension(
        self,
        suunto_workouts: SuuntoWorkouts,
        paused_workout_payload: dict,
    ) -> None:
        """When top-level gear is absent, the SummaryExtension copy populates source/device."""
        workout = SuuntoWorkoutJSON(**paused_workout_payload)

        record, _ = suunto_workouts._normalize_workout(workout, uuid4())

        assert record.source_name == "Suunto Race 2"
        assert record.device_model == "Suunto Race 2"
