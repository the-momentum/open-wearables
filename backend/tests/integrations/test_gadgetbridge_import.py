import json
import logging
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.constants.sdk_providers import normalize_sdk_provider
from app.integrations.celery.tasks.process_sdk_upload_task import process_sdk_upload
from app.models import DataPointSeries, DataSource, EventRecord, SeriesTypeDefinition, UserConnection
from app.schemas.enums import ProviderName
from app.services.providers.factory import ProviderFactory
from app.services.sdk.import_service import ImportService
from tests.factories import ApiKeyFactory, UserFactory

MODULE = "app.integrations.celery.tasks.process_sdk_upload_task"
SOURCE = {
    "name": "Gadgetbridge: test device",
    "appId": "nodomain.freeyourgadget.gadgetbridge",
    "deviceModel": "Huawei Band 11",
    "deviceType": "fitness_band",
    "deviceManufacturer": "Huawei",
}


@pytest.fixture
def payload() -> dict[str, Any]:
    # Synthetic SDK records exercise the native interface, not an unverified SQLite schema.
    records = []
    for index, (metric, value, unit) in enumerate(
        [
            ("STEP_COUNT", 42, "count"),
            ("HEART_RATE", 65, "bpm"),
            ("HEART_RATE_VARIABILITY", 38, "ms"),
            ("HKQuantityTypeIdentifierHeartRateVariabilitySDNN", 41, "ms"),
            ("DISTANCE", 120, "m"),
            ("ACTIVE_CALORIES_BURNED", 1.5, "kcal"),
            ("OXYGEN_SATURATION", 98, "%"),
        ]
    ):
        records.append(
            {
                "id": f"gb-{index}",
                "type": metric,
                "value": value,
                "unit": unit,
                "startDate": "2026-10-06T23:58:00+02:00",
                "endDate": "2026-10-06T23:59:00+02:00",
                "zoneOffset": "+02:00",
                "source": SOURCE,
            }
        )
    return {
        "provider": "gadgetbridge",
        "sdkVersion": "gadgetbridge-converter/test",
        "syncTimestamp": "2026-10-09T12:00:00Z",
        "syncType": "historical",
        "syncSessionId": "gb-test-session",
        "data": {
            "records": records,
            "sleep": [
                {
                    "id": "gb-sleep-1",
                    "stage": "light",
                    "startDate": "2026-10-06T23:00:00+02:00",
                    "endDate": "2026-10-07T00:00:00+02:00",
                    "zoneOffset": "+02:00",
                    "source": SOURCE,
                },
                {
                    "id": "gb-sleep-2",
                    "stage": "deep",
                    "startDate": "2026-10-07T00:00:00+02:00",
                    "endDate": "2026-10-07T01:00:00+02:00",
                    "zoneOffset": "+02:00",
                    "source": SOURCE,
                },
            ],
            "workouts": [
                {
                    "id": "gb-workout-1",
                    "type": "walking",
                    "startDate": "2026-10-06T10:00:00Z",
                    "endDate": "2026-10-06T10:30:00Z",
                    "source": SOURCE,
                    "values": [{"type": "distance", "value": 1800, "unit": "m"}],
                }
            ],
        },
    }


def test_native_provider_has_no_cloud_dependencies() -> None:
    strategy = ProviderFactory().get_provider("gadgetbridge")
    assert normalize_sdk_provider("GADGETBRIDGE") == "gadgetbridge"
    assert strategy.display_name == "Gadgetbridge"
    assert strategy.capabilities.client_sdk
    assert not strategy.capabilities.rest_pull
    assert strategy.oauth is None
    assert strategy.default_live_sync_mode is None
    assert not strategy.has_cloud_api


def test_historical_import_persists_and_replay_deduplicates(db: Session, payload: dict[str, Any]) -> None:
    user = UserFactory()
    service = ImportService(logging.getLogger(__name__))
    first = service.load_data(db, payload, str(user.id))
    assert first["records_inserted"] == 7
    assert first["workouts_saved"] == 1
    assert first["sleep_saved"] == 2
    source = db.query(DataSource).filter_by(user_id=user.id, provider=ProviderName.GADGETBRIDGE).one()
    assert source.device_type == "band"
    samples = (
        db.query(DataPointSeries, SeriesTypeDefinition.code)
        .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
        .filter(DataPointSeries.data_source_id == source.id)
        .all()
    )
    values = {code: sample.value for sample, code in samples}
    assert values["steps"] == Decimal("42")
    assert values["heart_rate_variability_rmssd"] == Decimal("38")
    assert values["heart_rate_variability_sdnn"] == Decimal("41")
    assert values["active_energy"] == Decimal("1.5")
    assert all(sample.recorded_at == datetime(2026, 10, 6, 21, 58, tzinfo=timezone.utc) for sample, _ in samples)
    sleep = db.query(EventRecord).filter_by(category="sleep", data_source_id=source.id).one()
    assert sleep.sleep_detail.sleep_light_minutes == 60
    assert sleep.sleep_detail.sleep_deep_minutes == 60
    second = service.load_data(db, payload, str(user.id))
    assert second["records_inserted"] == 0
    assert second["workouts_saved"] == 0
    assert db.query(DataPointSeries).filter_by(data_source_id=source.id).count() == 7
    assert db.query(EventRecord).filter_by(category="sleep", data_source_id=source.id).count() == 1
    sleep = db.query(EventRecord).filter_by(category="sleep", data_source_id=source.id).one()
    assert sleep.sleep_detail.sleep_light_minutes == 60


def test_api_queues_native_payload_and_worker_persists_it(
    db: Session, client: TestClient, payload: dict[str, Any]
) -> None:
    user = UserFactory()
    api_key = ApiKeyFactory()
    with patch("app.api.routes.v1.sdk_sync.process_sdk_upload") as task:
        response = client.post(
            f"/api/v1/sdk/users/{user.id}/sync", headers={"X-Open-Wearables-API-Key": api_key.plain_key}, json=payload
        )
    assert response.status_code == 202
    kwargs = task.delay.call_args.kwargs
    assert kwargs["provider"] == "gadgetbridge"
    assert kwargs["sync_type"] == "historical"
    with (
        patch(f"{MODULE}.SessionLocal", side_effect=lambda: nullcontext(db)),
        patch("app.services.sync_status_service.SessionLocal", side_effect=lambda: nullcontext(db)),
    ):
        result = process_sdk_upload.run(**kwargs)
    assert result["status_code"] == 200
    assert result["records_inserted"] == 7
    assert db.query(UserConnection).filter_by(user_id=user.id, provider="gadgetbridge").one().status == "active"
    assert db.query(DataSource).filter_by(user_id=user.id, provider="gadgetbridge").count() == 1


def test_partial_invalid_batch_keeps_valid_records(db: Session, payload: dict[str, Any]) -> None:
    user = UserFactory()
    raw = deepcopy(payload)
    raw["data"]["sleep"] = []
    raw["data"]["workouts"] = []
    raw["data"]["records"][0]["startDate"] = "not-a-date"
    result = ImportService(logging.getLogger(__name__)).load_data(db, raw, str(user.id))
    assert len(result["dropped"]) == 1
    assert result["records_inserted"] == 6


def test_worker_reports_invalid_envelope(db: Session) -> None:
    user = UserFactory()
    with (
        patch(f"{MODULE}.SessionLocal", side_effect=lambda: nullcontext(db)),
        patch(f"{MODULE}.emit_sync_failed") as failed,
    ):
        result = process_sdk_upload.run(
            content=json.dumps({"provider": "gadgetbridge", "data": {}}),
            content_type="application/json",
            user_id=str(user.id),
            provider="gadgetbridge",
        )
    assert result["status_code"] == 400
    failed.assert_called_once()
