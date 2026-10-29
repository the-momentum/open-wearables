"""Apple XML percent-unit scaling.

Apple's export.xml writes every unit="%" record as a 0-1 fraction, while
percent series must be stored in whole percent (0-100). Regression tests for
the XML import path matching the SDK import behaviour.
"""

from decimal import Decimal
from io import BytesIO
from logging import getLogger
from uuid import uuid4

from app.constants.series_types.sdk.metric_types import SDKMetricType
from app.services.providers.apple.apple_xml.xml_service import XMLService

UUID_USER = str(uuid4())
XML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="en_US">'
XML_FOOTER = "</HealthData>"


def _record(
    rtype: str,
    start: str,
    end: str,
    value: str,
    *,
    unit: str = "%",
    source: str = "iPhone",
    creation: str = "2026-10-20 08:00:00 +0000",
) -> str:
    parts = [f'sourceName="{source}"']
    if unit:
        parts.append(f'unit="{unit}"')
    parts += [
        f'creationDate="{creation}"',
        f'startDate="{start}"',
        f'endDate="{end}"',
    ]
    attrs = " ".join(parts)
    return f' <Record type="{rtype}" {attrs} value="{value}"/>\n'


def _samples(xml: str) -> list:
    service = XMLService(BytesIO(xml.encode()), getLogger(__name__))
    out: list = []
    for samples, _workouts, _sleep_request in service.parse_xml(UUID_USER):
        out.extend(samples)
    return out


PERCENT_XML = (
    XML_HEADER
    + _record(
        SDKMetricType.APPLE_WALKING_STEADINESS,
        "2026-10-13 00:00:00 +0000",
        "2026-10-20 00:00:00 +0000",
        "0.95",
    )
    + _record(
        SDKMetricType.WALKING_ASYMMETRY_PERCENTAGE,
        "2026-10-20 00:00:00 +0000",
        "2026-10-20 00:05:00 +0000",
        "0.045",
    )
    + _record(
        SDKMetricType.WALKING_DOUBLE_SUPPORT_PERCENTAGE,
        "2026-10-20 00:00:00 +0000",
        "2026-10-20 00:05:00 +0000",
        "0.72",
    )
    + _record(
        SDKMetricType.APPLE_BODY_FAT_PERCENTAGE,
        "2026-10-20 07:00:00 +0000",
        "2026-10-20 07:00:00 +0000",
        "0.18",
        source="Scale",
    )
    + _record(
        SDKMetricType.APPLE_OXYGEN_SATURATION,
        "2026-10-20 08:00:00 +0000",
        "2026-10-20 08:00:30 +0000",
        "0.97",
        source="Watch",
    )
    + XML_FOOTER
)


class TestAppleXmlPercentScaling:
    def test_percent_fraction_records_are_stored_in_whole_percent(self) -> None:
        samples = _samples(PERCENT_XML)
        by_type = {s.series_type: s for s in samples}

        assert by_type["walking_steadiness"].value == Decimal("95")
        assert by_type["walking_asymmetry_percentage"].value == Decimal("4.5")
        assert by_type["walking_double_support_percentage"].value == Decimal("72")
        assert by_type["body_fat_percentage"].value == Decimal("18")
        assert by_type["oxygen_saturation"].value == Decimal("97")

    def test_unitless_records_are_not_scaled(self) -> None:
        xml = (
            XML_HEADER
            + _record(
                SDKMetricType.APPLE_STEP_COUNT,
                "2026-10-20 08:00:00 +0000",
                "2026-10-20 08:05:00 +0000",
                "1200",
                unit="",
                source="Watch",
            )
            + XML_FOOTER
        )
        samples = _samples(xml)
        assert len(samples) == 1
        assert samples[0].value == Decimal("1200")

    def test_non_percent_units_are_not_scaled(self) -> None:
        xml = (
            XML_HEADER
            + _record(
                SDKMetricType.APPLE_BODY_MASS,
                "2026-10-20 07:00:00 +0000",
                "2026-10-20 07:00:00 +0000",
                "80.2",
                unit="kg",
                source="Scale",
            )
            + XML_FOOTER
        )
        samples = [s for s in _samples(xml) if s.series_type == "weight"]
        assert samples, "weight record should parse"
        assert samples[0].value == Decimal("80.2"), "kg values must never be x100"
