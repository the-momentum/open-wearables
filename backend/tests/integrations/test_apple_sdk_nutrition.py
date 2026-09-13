"""Dietary samples must survive SDK import with source attribution and canonical units."""

from decimal import Decimal
from logging import getLogger
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataPointSeries, DataSource
from app.schemas.enums import SeriesType, get_series_type_id, get_series_type_unit
from app.schemas.enums.aggregation_method import AggregationMethod, get_aggregation_method
from app.schemas.providers.mobile_sdk import SyncRequest
from app.services.apple.healthkit.import_service import ImportService
from tests.factories import UserFactory


def dietary_record(kind: str, value: str, unit: str, hour: int = 8) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "type": f"HKQuantityTypeIdentifier{kind}",
        "value": value,
        "unit": unit,
        "startDate": f"2026-09-01T{hour:02d}:00:00Z",
        "endDate": f"2026-09-01T{hour:02d}:00:00Z",
        "zoneOffset": "+07:00",
        "source": {"name": "Nutrition app", "bundleIdentifier": "com.example.nutrition"},
    }


def sdk_payload(records: list[dict[str, Any]], provider: str = "apple") -> dict[str, Any]:
    return {
        "provider": provider,
        "sdkVersion": "1.0.0",
        "syncTimestamp": "2026-09-01T12:00:00Z",
        "data": {"records": records},
    }


@pytest.mark.parametrize(
    ("kind", "value", "unit", "series_type", "expected", "stored_unit"),
    [
        ("DietaryWater", "0.25", "L", SeriesType.hydration, "250", "mL"),
        ("DietaryWater", "300", "mL", SeriesType.hydration, "300", "mL"),
        ("DietaryWater", "0", "L", SeriesType.hydration, "0", "mL"),
        ("DietaryEnergyConsumed", "600", "kcal", SeriesType.dietary_energy, "600", "kcal"),
        ("DietaryEnergyConsumed", "418.4", "kJ", SeriesType.dietary_energy, "100", "kcal"),
        ("DietaryProtein", "30", "g", SeriesType.dietary_protein, "30", "g"),
        ("DietaryProtein", "0.03", "kg", SeriesType.dietary_protein, "30", "g"),
        ("DietaryFatTotal", "12", "g", SeriesType.dietary_fat, "12", "g"),
        ("DietaryCarbohydrates", "50", "g", SeriesType.dietary_carbohydrates, "50", "g"),
        ("DietaryCarbohydrates", "0.05", "kg", SeriesType.dietary_carbohydrates, "50", "g"),
    ],
)
def test_dietary_mapping_and_units(
    kind: str, value: str, unit: str, series_type: SeriesType, expected: str, stored_unit: str
) -> None:
    request = SyncRequest.model_validate(sdk_payload([dietary_record(kind, value, unit)]))
    samples = ImportService(log=getLogger(__name__))._build_statistic_bundles(request, str(uuid4()))

    assert len(samples) == 1
    sample = samples[0]
    assert sample.series_type == series_type
    assert sample.value == Decimal(expected)
    assert sample.source == "Nutrition app"
    assert sample.external_id == request.data.records[0].id
    assert sample.recorded_at == request.data.records[0].startDate
    assert sample.zone_offset == "+07:00"
    assert sample.is_daily_total is False
    assert get_series_type_unit(series_type) == stored_unit
    assert get_aggregation_method(series_type) is AggregationMethod.SUM


def test_android_hydration_mapping_is_preserved() -> None:
    record = dietary_record("DietaryWater", "250", "mL")
    record["type"] = "HYDRATION"
    request = SyncRequest.model_validate(sdk_payload([record], provider="google"))
    samples = ImportService(log=getLogger(__name__))._build_statistic_bundles(request, str(uuid4()))
    assert samples[0].series_type == SeriesType.hydration
    assert samples[0].value == Decimal("250")
    assert samples[0].is_daily_total is False


def test_dietary_samples_are_persisted_once_on_full_resync(db: Session) -> None:
    user = UserFactory()
    records = [
        dietary_record("DietaryWater", "0.25", "L"),
        dietary_record("DietaryEnergyConsumed", "600", "kcal"),
        dietary_record("DietaryProtein", "30", "g"),
        dietary_record("DietaryFatTotal", "12", "g"),
        dietary_record("DietaryCarbohydrates", "50", "g"),
        dietary_record("DietaryProtein", "20", "g", hour=10),
    ]
    service = ImportService(log=getLogger(__name__))
    payload = sdk_payload(records)
    first = service.load_data(db, payload, str(user.id))
    service.load_data(db, payload, str(user.id))

    assert first["records_saved"] == 6
    assert set(first["types"]) == {
        "hydration",
        "dietary_energy",
        "dietary_protein",
        "dietary_fat",
        "dietary_carbohydrates",
    }
    rows = db.execute(
        select(DataPointSeries, DataSource)
        .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
        .where(DataSource.user_id == user.id)
    ).all()
    assert len(rows) == 6
    assert all(source.source == "Nutrition app" for _, source in rows)
    assert all(sample.is_daily_total is False for sample, _ in rows)
    protein = [
        sample
        for sample, _ in rows
        if sample.series_type_definition_id == get_series_type_id(SeriesType.dietary_protein)
    ]
    assert sum(sample.value for sample in protein) == Decimal("50")
