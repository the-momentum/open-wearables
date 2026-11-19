"""Reproductive health records from the mobile SDKs, normalized to ReproductiveHealthDetailCreate."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from app.constants.series_types.sdk.reproductive_health import (
    SDK_REPRODUCTIVE_HEALTH_VALUES,
    SDK_TYPE_TO_REPRODUCTIVE_HEALTH_TYPE,
)
from app.schemas.enums import CervicalMucusSensation, ReproductiveHealthType
from app.schemas.model_crud.activities import ReproductiveHealthDetailCreate
from app.schemas.providers.mobile_sdk.sync_request import MetricRecord

# SexualActivityRecord.PROTECTION_USED_*: 0 is "unknown"
_HC_PROTECTION_USED = {1: True, 2: False}

# HealthKit metadata keys; the iOS SDK sends every metadata value as a string ("1" / "0" for booleans)
_HK_CYCLE_START = "HKMenstrualCycleStart"
_HK_PROTECTION_USED = "HKSexualActivityProtectionUsed"

_SENSATIONS = {sensation.value for sensation in CervicalMucusSensation}


def _int(value: Decimal) -> int | None:
    return int(value) if value.is_finite() and value == value.to_integral_value() else None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes"):
        return True
    if text in ("0", "false", "no"):
        return False
    return None


def reproductive_health_type(sdk_type: str | None) -> ReproductiveHealthType | None:
    """The normalized type of an SDK record type, or None when it is not reproductive health data."""
    return SDK_TYPE_TO_REPRODUCTIVE_HEALTH_TYPE.get(sdk_type or "")


def reproductive_health_detail(record: MetricRecord, record_id: UUID) -> ReproductiveHealthDetailCreate:
    """The detail of one reproductive health record, normalized across platforms.

    A number a platform added after this table was written leaves `value` null rather than
    dropping the entry: when and that it happened still holds.
    """
    sdk_type = record.type or ""
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    number = _int(record.value)
    value = SDK_REPRODUCTIVE_HEALTH_VALUES.get(sdk_type, {}).get(number) if number is not None else None

    cycle_start = protection_used = sensation = None
    match sdk_type:
        case "HKCategoryTypeIdentifierMenstrualFlow":
            cycle_start = _bool(metadata.get(_HK_CYCLE_START))
        case "HKCategoryTypeIdentifierSexualActivity":
            protection_used = _bool(metadata.get(_HK_PROTECTION_USED))
        case "SEXUAL_ACTIVITY":
            protection_used = _HC_PROTECTION_USED.get(number) if number is not None else None
        case "CERVICAL_MUCUS":
            raw = str(metadata.get("sensation") or "").lower()
            sensation = raw if raw in _SENSATIONS else None

    return ReproductiveHealthDetailCreate(
        record_id=record_id,
        value=value,
        cycle_start=cycle_start,
        protection_used=protection_used,
        cervical_mucus_sensation=sensation,
    )
