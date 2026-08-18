"""Tests for SDK logs endpoint."""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.api.routes.v1.sdk_logs import _event_fields
from app.schemas.enums import SeriesType
from app.schemas.providers.mobile_sdk import SDKLogRequest
from app.services.sdk_token_service import create_sdk_user_token
from tests.factories import ApiKeyFactory

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
ENDPOINT = "/api/v1/sdk/users/{user_id}/logs"

SYNC_START_EVENT = {
    "eventType": "historical_data_sync_start",
    "timestamp": "2026-04-09T10:00:00Z",
    "dataTypeCounts": [
        {"type": "HKQuantityTypeIdentifierHeartRate", "count": 500},
        {"type": "HKQuantityTypeIdentifierStepCount", "count": 200},
        {"type": "workouts", "count": 3},
        {"type": "sleep", "count": 12},
    ],
    "timeRange": {
        "startDate": "2026-01-09T00:00:00Z",
        "endDate": "2026-04-09T10:00:00Z",
    },
}

SYNC_END_EVENT = {
    "eventType": "historical_data_type_sync_end",
    "timestamp": "2026-04-09T10:00:05Z",
    "dataType": "HKQuantityTypeIdentifierHeartRate",
    "success": True,
    "recordCount": 500,
    "durationMs": 1200,
}

DEVICE_STATE_EVENT = {
    "eventType": "device_state",
    "timestamp": "2026-04-09T10:00:00Z",
    "batteryLevel": 0.72,
    "batteryState": "unplugged",
    "isLowPowerMode": False,
    "thermalState": "nominal",
    "taskType": "background",
    "availableRamBytes": 1073741824,
    "totalRamBytes": 6442450944,
}


def _url(user_id: str = USER_ID) -> str:
    return ENDPOINT.format(user_id=user_id)


def _payload(*events: dict) -> dict:
    return {
        "sdkVersion": "1.2.0",
        "provider": "apple",
        "events": list(events),
    }


class TestSDKLogsHappyPath:
    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_all_event_types_accepted(self, mock_store: MagicMock, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json=_payload(SYNC_START_EVENT, SYNC_END_EVENT, DEVICE_STATE_EVENT),
        )
        assert response.status_code == 202
        assert response.json()["user_id"] == USER_ID
        mock_store.assert_called_once()

    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_sync_start_only(self, mock_store: MagicMock, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json=_payload(SYNC_START_EVENT),
        )
        assert response.status_code == 202

    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_per_type_sync_end(self, mock_store: MagicMock, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json=_payload(SYNC_END_EVENT),
        )
        assert response.status_code == 202

    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_device_state_only(self, mock_store: MagicMock, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json=_payload(DEVICE_STATE_EVENT),
        )
        assert response.status_code == 202

    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_provider_omitted_defaults_to_unknown(self, mock_store: MagicMock, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json={"sdkVersion": "1.0.0", "events": [DEVICE_STATE_EVENT]},
        )
        assert response.status_code == 202
        mock_store.assert_called_once()
        assert mock_store.call_args.kwargs["provider"] == "unknown"

    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_time_range_without_start_date_accepted(
        self, mock_store: MagicMock, client: TestClient, db: Session
    ) -> None:
        """Full-history sync: the SDK omits startDate when no day limit is configured."""
        api_key = ApiKeyFactory()
        event = {
            **SYNC_START_EVENT,
            "timeRange": {"endDate": "2026-04-09T10:00:00Z"},
        }
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json=_payload(event, DEVICE_STATE_EVENT),
        )
        assert response.status_code == 202
        mock_store.assert_called_once()

    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_android_data_types_accepted(self, mock_store: MagicMock, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        event = {
            "eventType": "historical_data_sync_start",
            "timestamp": "2026-04-09T10:00:00Z",
            "dataTypeCounts": [
                {"type": "HEART_RATE", "count": 300},
                {"type": "STEP_COUNT", "count": 150},
            ],
        }
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json=_payload(event),
        )
        assert response.status_code == 202


class TestSDKLogsEventFields:
    """The flattened fields are what makes per-type outcomes queryable in the logs."""

    def test_data_type_is_normalised_native_kept(self) -> None:
        fields = _event_fields(SDKLogRequest(**_payload(SYNC_END_EVENT, DEVICE_STATE_EVENT)))

        assert fields["data_type"] == SeriesType.heart_rate.value
        assert fields["native_data_type"] == "HKQuantityTypeIdentifierHeartRate"
        assert fields["success"] is True
        assert fields["record_count"] == 500
        assert fields["task_type"] == "background"
        assert fields["low_power"] is False
        assert fields["thermal_state"] == "nominal"

    def test_android_data_type_maps_to_same_series_type(self) -> None:
        """Health Connect and HealthKit heart rate must land on one series for a shared panel."""
        event = {**SYNC_END_EVENT, "dataType": "HEART_RATE"}

        fields = _event_fields(SDKLogRequest(**_payload(event)))

        assert fields["data_type"] == SeriesType.heart_rate.value
        assert fields["native_data_type"] == "HEART_RATE"

    def test_unmappable_data_type_falls_back_to_native(self) -> None:
        """Sleep and workout identifiers are not series types."""
        event = {**SYNC_END_EVENT, "dataType": "HKWorkoutTypeIdentifier"}

        fields = _event_fields(SDKLogRequest(**_payload(event)))

        assert fields["data_type"] == "HKWorkoutTypeIdentifier"
        assert fields["native_data_type"] == "HKWorkoutTypeIdentifier"

    def test_two_outcome_events_are_not_flattened(self) -> None:
        """Sharing the fields would silently report only the last outcome."""
        second = {**SYNC_END_EVENT, "dataType": "HKQuantityTypeIdentifierStepCount", "recordCount": 200}

        fields = _event_fields(SDKLogRequest(**_payload(SYNC_END_EVENT, second)))

        for key in ("data_type", "native_data_type", "success", "record_count"):
            assert key not in fields

    def test_two_outcome_events_still_report_device_state(self) -> None:
        second = {**SYNC_END_EVENT, "dataType": "HKQuantityTypeIdentifierStepCount"}

        fields = _event_fields(SDKLogRequest(**_payload(SYNC_END_EVENT, second, DEVICE_STATE_EVENT)))

        assert "data_type" not in fields
        assert fields["task_type"] == "background"

    def test_start_event_reports_declared_totals(self) -> None:
        fields = _event_fields(SDKLogRequest(**_payload(SYNC_START_EVENT)))

        assert fields["types_declared"] == 4
        assert fields["samples_expected"] == 715
        assert "data_type" not in fields


class TestSDKLogsAuth:
    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_sdk_token_accepted(self, mock_store: MagicMock, client: TestClient, db: Session) -> None:
        token = create_sdk_user_token("app_123", USER_ID)
        response = client.post(
            _url(),
            headers={"Authorization": f"Bearer {token}"},
            json=_payload(DEVICE_STATE_EVENT),
        )
        assert response.status_code == 202

    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_api_key_accepted(self, mock_store: MagicMock, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json=_payload(DEVICE_STATE_EVENT),
        )
        assert response.status_code == 202

    def test_no_auth_returns_401(self, client: TestClient, db: Session) -> None:
        response = client.post(
            _url(),
            json=_payload(DEVICE_STATE_EVENT),
        )
        assert response.status_code == 401

    @patch("app.api.routes.v1.sdk_logs.store_raw_payload")
    def test_token_user_id_mismatch_returns_403(self, mock_store: MagicMock, client: TestClient, db: Session) -> None:
        token = create_sdk_user_token("app_123", "00000000-0000-0000-0000-000000000000")
        response = client.post(
            _url(),
            headers={"Authorization": f"Bearer {token}"},
            json=_payload(DEVICE_STATE_EVENT),
        )
        assert response.status_code == 403


class TestSDKLogsValidation:
    def test_empty_events_rejected(self, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json={"sdkVersion": "1.0.0", "provider": "apple", "events": []},
        )
        assert response.status_code in (400, 422)

    def test_unknown_event_type_rejected(self, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json=_payload({"eventType": "something_unknown", "timestamp": "2026-04-09T10:00:00Z"}),
        )
        assert response.status_code in (400, 422)

    def test_missing_sdk_version_rejected(self, client: TestClient, db: Session) -> None:
        api_key = ApiKeyFactory()
        response = client.post(
            _url(),
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json={"provider": "apple", "events": [DEVICE_STATE_EVENT]},
        )
        assert response.status_code in (400, 422)
