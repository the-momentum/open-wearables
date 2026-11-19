"""Reproductive health records from the iOS and Android SDKs map to one shared vocabulary."""

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.constants.series_types.sdk.reproductive_health import (
    HEALTH_CONNECT_REPRODUCTIVE_HEALTH_TYPES,
    HEALTHKIT_REPRODUCTIVE_HEALTH_TYPES,
    SDK_REPRODUCTIVE_HEALTH_VALUES,
    SDK_TYPE_TO_REPRODUCTIVE_HEALTH_TYPE,
)
from app.schemas.enums import REPRODUCTIVE_HEALTH_VALUE_ENUMS, ReproductiveHealthType
from app.schemas.model_crud.activities import ReproductiveHealthDetailCreate
from app.schemas.providers.mobile_sdk.sync_request import MetricRecord
from app.services.sdk.reproductive_health import reproductive_health_detail, reproductive_health_type

HK = "HKCategoryTypeIdentifier"


def _detail(
    sdk_type: str, value: float | str, metadata: dict[str, Any] | None = None
) -> ReproductiveHealthDetailCreate:
    record = MetricRecord(
        id="entry-1",
        type=sdk_type,
        startDate="2026-11-01T00:00:00Z",
        endDate="2026-11-02T00:00:00Z",
        value=Decimal(str(value)),
        unit=None,
        metadata=metadata,
    )
    return reproductive_health_detail(record, uuid4())


class TestType:
    @pytest.mark.parametrize(
        ("sdk_type", "expected"),
        [
            (f"{HK}MenstrualFlow", ReproductiveHealthType.MENSTRUAL_FLOW),
            ("MENSTRUAL_FLOW", ReproductiveHealthType.MENSTRUAL_FLOW),
            ("MENSTRUAL_PERIOD", ReproductiveHealthType.MENSTRUAL_PERIOD),
            (f"{HK}CervicalMucusQuality", ReproductiveHealthType.CERVICAL_MUCUS),
            ("CERVICAL_MUCUS", ReproductiveHealthType.CERVICAL_MUCUS),
            (f"{HK}PersistentIntermenstrualBleeding", ReproductiveHealthType.PERSISTENT_SPOTTING),
            (f"{HK}Pregnancy", ReproductiveHealthType.PREGNANCY),
        ],
    )
    def test_both_platforms_map_to_one_type(self, sdk_type: str, expected: ReproductiveHealthType) -> None:
        assert reproductive_health_type(sdk_type) == expected

    @pytest.mark.parametrize(
        "sdk_type", ["HKQuantityTypeIdentifierBasalBodyTemperature", "BASAL_BODY_TEMPERATURE", "HEART_RATE", "", None]
    )
    def test_other_types_are_not_reproductive_health(self, sdk_type: str | None) -> None:
        assert reproductive_health_type(sdk_type) is None

    def test_every_type_fits_the_record_type_column(self) -> None:
        assert all(len(entry_type) <= 32 for entry_type in ReproductiveHealthType)

    def test_coverage_splits_types_by_platform(self) -> None:
        assert ReproductiveHealthType.PREGNANCY in HEALTHKIT_REPRODUCTIVE_HEALTH_TYPES
        assert ReproductiveHealthType.PREGNANCY not in HEALTH_CONNECT_REPRODUCTIVE_HEALTH_TYPES
        assert ReproductiveHealthType.MENSTRUAL_PERIOD in HEALTH_CONNECT_REPRODUCTIVE_HEALTH_TYPES
        assert ReproductiveHealthType.MENSTRUAL_PERIOD not in HEALTHKIT_REPRODUCTIVE_HEALTH_TYPES


class TestValue:
    @pytest.mark.parametrize("sdk_type", sorted(SDK_REPRODUCTIVE_HEALTH_VALUES))
    def test_platform_values_are_the_types_documented_values(self, sdk_type: str) -> None:
        entry_type = SDK_TYPE_TO_REPRODUCTIVE_HEALTH_TYPE[sdk_type]
        assert set(SDK_REPRODUCTIVE_HEALTH_VALUES[sdk_type].values()) <= set(
            REPRODUCTIVE_HEALTH_VALUE_ENUMS[entry_type]
        )

    def test_every_type_with_values_has_a_platform_table(self) -> None:
        with_tables = {SDK_TYPE_TO_REPRODUCTIVE_HEALTH_TYPE[sdk_type] for sdk_type in SDK_REPRODUCTIVE_HEALTH_VALUES}
        assert with_tables == set(REPRODUCTIVE_HEALTH_VALUE_ENUMS)

    @pytest.mark.parametrize(
        ("sdk_type", "number", "expected"),
        [
            # The same number means different things on each platform.
            (f"{HK}MenstrualFlow", 2, "light"),
            ("MENSTRUAL_FLOW", 2, "medium"),
            (f"{HK}MenstrualFlow", 1, "unspecified"),
            ("MENSTRUAL_FLOW", 0, "unspecified"),
            (f"{HK}MenstrualFlow", 5, "none"),
            (f"{HK}CervicalMucusQuality", 5, "egg_white"),
            ("CERVICAL_MUCUS", 5, "egg_white"),
            ("CERVICAL_MUCUS", 6, "unusual"),
            ("CERVICAL_MUCUS", 0, "unknown"),
            (f"{HK}OvulationTestResult", 2, "lh_surge"),
            (f"{HK}OvulationTestResult", 4, "estrogen_surge"),
            ("OVULATION_TEST", 1, "lh_surge"),
            ("OVULATION_TEST", 2, "estrogen_surge"),
            ("OVULATION_TEST", 3, "negative"),
            ("OVULATION_TEST", 0, "indeterminate"),
            (f"{HK}PregnancyTestResult", 2, "positive"),
            (f"{HK}ProgesteroneTestResult", 3, "indeterminate"),
            (f"{HK}Contraceptive", 4, "iud"),
            (f"{HK}Contraceptive", 6, "oral"),
        ],
    )
    def test_platform_number_becomes_shared_value(self, sdk_type: str, number: int, expected: str) -> None:
        assert _detail(sdk_type, number).value == expected

    @pytest.mark.parametrize(
        ("sdk_type", "number"),
        [
            (f"{HK}Pregnancy", 0),
            (f"{HK}Lactation", 0),
            (f"{HK}IntermenstrualBleeding", 0),
            ("INTERMENSTRUAL_BLEEDING", 1),
            ("MENSTRUAL_PERIOD", 1),
            (f"{HK}IrregularMenstrualCycles", 0),
        ],
    )
    def test_presence_only_entries_carry_no_value(self, sdk_type: str, number: int) -> None:
        assert _detail(sdk_type, number).value is None

    @pytest.mark.parametrize("number", [99, 2.5])
    def test_unknown_number_keeps_the_entry_without_a_value(self, number: float) -> None:
        assert _detail(f"{HK}MenstrualFlow", number).value is None


class TestFlags:
    @pytest.mark.parametrize(("raw", "expected"), [("1", True), ("0", False), ("true", True), (True, True)])
    def test_healthkit_cycle_start_comes_from_metadata(self, raw: Any, expected: bool) -> None:
        assert _detail(f"{HK}MenstrualFlow", 3, {"HKMenstrualCycleStart": raw}).cycle_start is expected

    def test_cycle_start_is_unknown_without_metadata(self) -> None:
        assert _detail(f"{HK}MenstrualFlow", 3).cycle_start is None
        assert _detail("MENSTRUAL_FLOW", 2).cycle_start is None

    @pytest.mark.parametrize(("raw", "expected"), [("1", True), ("0", False), (None, None)])
    def test_healthkit_protection_comes_from_metadata(self, raw: str | None, expected: bool | None) -> None:
        metadata = {"HKSexualActivityProtectionUsed": raw} if raw is not None else None
        detail = _detail(f"{HK}SexualActivity", 0, metadata)
        assert detail.protection_used is expected
        assert detail.value is None

    @pytest.mark.parametrize(("number", "expected"), [(1, True), (2, False), (0, None)])
    def test_health_connect_protection_comes_from_value(self, number: int, expected: bool | None) -> None:
        detail = _detail("SEXUAL_ACTIVITY", number, {"protectionUsed": "protected"})
        assert detail.protection_used is expected
        assert detail.value is None

    @pytest.mark.parametrize(("raw", "expected"), [("medium", "medium"), ("Heavy", "heavy"), ("unknown", None)])
    def test_health_connect_mucus_sensation_comes_from_metadata(self, raw: str, expected: str | None) -> None:
        detail = _detail("CERVICAL_MUCUS", 3, {"appearance": "creamy", "sensation": raw})
        assert detail.value == "creamy"
        assert detail.cervical_mucus_sensation == expected
