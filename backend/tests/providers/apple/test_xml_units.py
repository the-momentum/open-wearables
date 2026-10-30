"""Apple Health XML values are converted from the export's display unit to the series unit."""

from decimal import Decimal
from io import BytesIO
from logging import getLogger
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.services.providers.apple.apple_xml.xml_service import XMLService


def _record(record_type: str, unit: str | None, value: str) -> dict[str, Any]:
    document = {
        "type": record_type,
        "sourceName": "iPhone",
        "startDate": "2025-03-01 08:00:00 +0100",
        "endDate": "2025-03-01 08:05:00 +0100",
        "value": value,
    }
    if unit is not None:
        document["unit"] = unit
    return document


class TestAppleXmlRecordUnits:
    @pytest.fixture
    def service(self) -> XMLService:
        return XMLService(Path("export.xml"), getLogger(__name__))

    @pytest.mark.parametrize(
        ("record_type", "unit", "value", "series_type", "expected"),
        [
            (
                "HKQuantityTypeIdentifierBloodGlucose",
                "mmol<180.15588000005408>/L",
                "6.1",
                SeriesType.blood_glucose,
                Decimal("109.91102"),
            ),
            ("HKQuantityTypeIdentifierBloodGlucose", "mg/dL", "110", SeriesType.blood_glucose, Decimal("110")),
            (
                "HKQuantityTypeIdentifierDistanceWalkingRunning",
                "km",
                "0.021",
                SeriesType.distance_walking_running,
                Decimal("21"),
            ),
            ("HKQuantityTypeIdentifierBodyMass", "lb", "150", SeriesType.weight, Decimal("68.0388555")),
            ("HKQuantityTypeIdentifierBodyTemperature", "degF", "98.6", SeriesType.body_temperature, Decimal("37")),
            ("HKQuantityTypeIdentifierHeight", "cm", "175", SeriesType.height, Decimal("175")),
            ("HKQuantityTypeIdentifierHeartRate", "count/min", "72", SeriesType.heart_rate, Decimal("72")),
        ],
    )
    def test_converts_to_series_unit(
        self,
        service: XMLService,
        record_type: str,
        unit: str,
        value: str,
        series_type: SeriesType,
        expected: Decimal,
    ) -> None:
        sample = service._create_record(_record(record_type, unit, value), uuid4())

        assert sample is not None
        assert sample.series_type == series_type
        assert sample.value == pytest.approx(expected, abs=Decimal("0.000001"))
        assert not service.stats.unconverted_units

    @pytest.mark.parametrize("unit", [None, "furlong"])
    def test_keeps_value_and_counts_unknown_unit(self, service: XMLService, unit: str | None) -> None:
        sample = service._create_record(_record("HKQuantityTypeIdentifierDistanceWalkingRunning", unit, "5"), uuid4())

        assert sample is not None
        assert sample.value == Decimal("5")
        assert service.stats.unconverted_units == {f"distance_walking_running:{unit}": 1}

    def test_keeps_value_and_counts_mismatched_quantity(self, service: XMLService) -> None:
        sample = service._create_record(
            _record("HKQuantityTypeIdentifierDistanceWalkingRunning", "km/hr", "5"), uuid4()
        )

        assert sample is not None
        assert sample.value == Decimal("5")
        assert service.stats.unconverted_units == {"distance_walking_running:km/hr": 1}

    def test_skipped_record_is_not_counted_as_unconverted(self, service: XMLService) -> None:
        document = _record("HKQuantityTypeIdentifierDistanceWalkingRunning", "furlong", "5")
        document["startDate"] = "not a date"

        assert service._create_record(document, uuid4()) is None
        assert service.stats.records.reasons == {"invalid_date:HKQuantityTypeIdentifierDistanceWalkingRunning": 1}
        assert not service.stats.unconverted_units


class TestAppleXmlWorkoutEnergyUnits:
    def test_converts_kilojoules_to_kcal(self) -> None:
        service = XMLService(Path("export.xml"), getLogger(__name__))
        metrics = service._init_metrics()

        service._update_metrics_from_stat(
            metrics, {"type": "HKQuantityTypeIdentifierActiveEnergyBurned", "sum": "418.4", "unit": "kJ"}
        )

        assert metrics["energy_burned"] == pytest.approx(Decimal("100"))

    def test_keeps_and_counts_energy_without_unit(self) -> None:
        service = XMLService(Path("export.xml"), getLogger(__name__))
        metrics = service._init_metrics()

        service._update_metrics_from_stat(metrics, {"type": "HKQuantityTypeIdentifierActiveEnergyBurned", "sum": "100"})

        assert metrics["energy_burned"] == Decimal("100")
        assert service.stats.unconverted_units == {"workout_energy:None": 1}


EXPORT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="pl_PL">
 <Record type="HKQuantityTypeIdentifierBloodGlucose" sourceName="Health" unit="mmol&lt;180.15588000005408&gt;/L"
  startDate="2025-03-01 08:00:00 +0100" endDate="2025-03-01 08:00:00 +0100" value="6.1"/>
 <Record type="HKQuantityTypeIdentifierDistanceWalkingRunning" sourceName="iPhone" unit="km"
  startDate="2025-03-01 09:00:00 +0100" endDate="2025-03-01 09:05:00 +0100" value="0.4"/>
 <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="30" durationUnit="min" sourceName="Watch"
  startDate="2025-03-01 10:00:00 +0100" endDate="2025-03-01 10:30:00 +0100">
  <WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned"
   startDate="2025-03-01 10:00:00 +0100" endDate="2025-03-01 10:30:00 +0100" sum="418.4" unit="kJ"/>
 </Workout>
</HealthData>
"""


class TestAppleXmlParseUnits:
    def test_parse_xml_converts_record_and_workout_units(self) -> None:
        service = XMLService(BytesIO(EXPORT_XML), getLogger(__name__))

        chunks = list(service.parse_xml(str(uuid4())))
        records = [record for time_series, _, _ in chunks for record in time_series]
        workouts = [workout for _, chunk_workouts, _ in chunks for workout in chunk_workouts]

        values = {record.series_type: record.value for record in records}
        assert values[SeriesType.blood_glucose] == pytest.approx(Decimal("109.91102"))
        assert values[SeriesType.distance_walking_running] == Decimal("400")
        assert len(workouts) == 1
        _, detail = workouts[0]
        assert detail.energy_burned == pytest.approx(Decimal("100"))
        assert not service.stats.unconverted_units
