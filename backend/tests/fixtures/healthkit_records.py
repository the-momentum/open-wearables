"""Builders for HealthKit quantity records as the SDK sends them, and a loader that imports them."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.services.sdk.import_service import ImportService, LoadDataResult
from tests.factories import APPLE_WATCH_APP_ID

ACTIVE_ENERGY = "HKQuantityTypeIdentifierActiveEnergyBurned"
BASAL_ENERGY = "HKQuantityTypeIdentifierBasalEnergyBurned"
DISTANCE = "HKQuantityTypeIdentifierDistanceWalkingRunning"
HEART_RATE = "HKQuantityTypeIdentifierHeartRate"
UNITS = {ACTIVE_ENERGY: "kcal", BASAL_ENERGY: "kcal", DISTANCE: "m", HEART_RATE: "count/min"}


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def healthkit_record(
    kind: str,
    start: datetime,
    seconds: int,
    value: str,
    *,
    count: int | None = None,
    record_id: str | None = None,
    app_id: str = APPLE_WATCH_APP_ID,
    hardware: str | None = "Watch6,18",
    device_model: str = "Watch",
) -> dict[str, Any]:
    """A HealthKit record as the SDK sends it; the hardware version names the device of Apple's own sources."""
    source: dict[str, Any] = {"appId": app_id, "name": "Test Apple Watch", "deviceModel": device_model}
    if hardware:
        source["deviceHardwareVersion"] = hardware
    record: dict[str, Any] = {
        "id": record_id or str(uuid4()).upper(),
        "type": kind,
        "unit": UNITS[kind],
        "value": value,
        "startDate": iso(start),
        "endDate": iso(start + timedelta(seconds=seconds)),
        "source": source,
    }
    if count is not None:
        record["count"] = count
    return record


def load_healthkit_records(db: Session, user_id: str, records: list[dict[str, Any]]) -> LoadDataResult:
    payload = {
        "provider": "apple",
        "sdkVersion": "0.17.0",
        "syncTimestamp": iso(datetime.now(timezone.utc)),
        "data": {"records": records},
    }
    return ImportService().load_data(db, payload, user_id)
