"""Tests for reading Google Health dataSource.device.formFactor as a reported device type."""

import pytest

from app.schemas.enums import DeviceType
from app.services.providers.google_health.helpers import extract_form_factor


@pytest.mark.parametrize(
    ("data_source", "expected"),
    [
        ({"device": {"displayName": "Charge 6", "formFactor": "FITNESS_BAND"}}, DeviceType.BAND),
        ({"device": {"manufacturer": "Polar", "formFactor": "CHEST_STRAP"}}, DeviceType.CHEST_STRAP),
        ({"device": {"formFactor": "FORM_FACTOR_UNSPECIFIED"}}, None),
        ({"device": {"displayName": "Apple Watch"}}, None),
        ({"platform": "HEALTH_KIT"}, None),
        (None, None),
    ],
)
def test_extract_form_factor(data_source: object, expected: DeviceType | None) -> None:
    assert extract_form_factor(data_source) == expected
