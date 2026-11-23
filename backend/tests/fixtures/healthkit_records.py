"""Builders for HealthKit quantity records as the SDK sends them, and a loader that imports them."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import SeriesSample
from app.schemas.enums import SeriesType, get_series_type_id
from app.services.sdk.import_service import ImportService, LoadDataResult

# An Apple Watch's HealthKit source, as the SDK sends it
APPLE_WATCH_APP_ID = "com.apple.health.5C1B9A4E-0D7E-4F7B-9E8A-2E3D4C5B6A70"

ACTIVE_ENERGY = "HKQuantityTypeIdentifierActiveEnergyBurned"
BASAL_ENERGY = "HKQuantityTypeIdentifierBasalEnergyBurned"
DISTANCE = "HKQuantityTypeIdentifierDistanceWalkingRunning"
HEART_RATE = "HKQuantityTypeIdentifierHeartRate"
_UNITS = {ACTIVE_ENERGY: "kcal", BASAL_ENERGY: "kcal", DISTANCE: "m", HEART_RATE: "count/min"}


def _iso(moment: datetime) -> str:
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
        "unit": _UNITS[kind],
        "value": value,
        "startDate": _iso(start),
        "endDate": _iso(start + timedelta(seconds=seconds)),
        "source": source,
    }
    if count is not None:
        record["count"] = count
    return record


def load_healthkit_records(db: Session, user_id: str, records: list[dict[str, Any]]) -> LoadDataResult:
    payload = {
        "provider": "apple",
        "sdkVersion": "0.17.0",
        "syncTimestamp": _iso(datetime.now(timezone.utc)),
        "data": {"records": records},
    }
    return ImportService().load_data(db, payload, user_id)


def stored_samples(
    db: Session, series_type: SeriesType = SeriesType.active_energy
) -> list[tuple[datetime, int | None, Decimal]]:
    """The stored samples of a type, oldest first, as (recorded_at, window_seconds, value)."""
    db.expire_all()
    rows = (
        db.query(SeriesSample)
        .filter(SeriesSample.series_type_definition_id == get_series_type_id(series_type))
        .order_by(SeriesSample.recorded_at)
        .all()
    )
    return [(row.recorded_at, row.window_seconds, row.value) for row in rows]
