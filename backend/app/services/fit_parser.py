"""Generic ANT+ FIT file parser — provider-agnostic (Garmin, Polar, Suunto, etc.)."""

import io
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import fitdecode

from app.schemas.enums.series_types import SeriesType
from app.schemas.model_crud.activities.data_point_series import TimeSeriesSampleCreate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field map — ANT+ FIT Protocol standard field names → SeriesType
#
# fit_fields is ordered: first field present in the record message wins.
# This lets us prefer enhanced_* variants (FIT 2.0 float) over their uint16
# base equivalents without duplicating logic in the parser.
#
# GPS and environmental fields are commented out pending series type seeds (#1074).
# ---------------------------------------------------------------------------

_SEMICIRCLES_TO_DEGREES: float = 180.0 / (2**31)


def _scale(factor: float) -> Callable[[float], Decimal]:
    def _fn(v: float) -> Decimal:
        return Decimal(str(round(v * factor, 6)))

    return _fn


@dataclass(frozen=True)
class _FieldMapping:
    fit_fields: tuple[str, ...]
    series_type: SeriesType
    transform: Callable[[float], Decimal] | None = None


_RECORD_FIELD_MAP: tuple[_FieldMapping, ...] = (
    _FieldMapping(("heart_rate",), SeriesType.heart_rate),
    _FieldMapping(("enhanced_speed", "speed"), SeriesType.speed),
    _FieldMapping(("cadence",), SeriesType.cadence),
    _FieldMapping(("power",), SeriesType.power),
    # FIT stores vertical_oscillation in mm, SeriesType unit is cm
    _FieldMapping(("vertical_oscillation",), SeriesType.running_vertical_oscillation, _scale(0.1)),
    _FieldMapping(("stance_time",), SeriesType.running_ground_contact_time),
    # FIT stores step_length in mm, SeriesType unit is cm
    _FieldMapping(("step_length",), SeriesType.running_stride_length, _scale(0.1)),
    # Pending #1074:
    # _FieldMapping(("enhanced_altitude", "altitude"), SeriesType.elevation),
    # _FieldMapping(("position_lat",), SeriesType.latitude, _scale(_SEMICIRCLES_TO_DEGREES)),
    # _FieldMapping(("position_long",), SeriesType.longitude, _scale(_SEMICIRCLES_TO_DEGREES)),
    # _FieldMapping(("temperature",), SeriesType.air_temperature),
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class FitParseResult:
    samples: list[TimeSeriesSampleCreate] = field(default_factory=list)
    workout_steps: list[dict] = field(default_factory=list)  # pending #1076
    developer_fields_found: list[str] = field(default_factory=list)


def parse_fit_file(
    data: bytes,
    user_id: UUID,
    data_source_id: UUID,
    source: str | None = None,
) -> FitParseResult:
    result = FitParseResult()
    dev_fields_seen: set[str] = set()

    with fitdecode.FitReader(io.BytesIO(data)) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage) or frame.name != "record":
                continue

            ts = _timestamp(frame)
            if ts is None:
                continue

            for f in frame.fields:
                if f.field is None and f.name not in (None, "unknown"):
                    dev_fields_seen.add(str(f.name))

            for mapping in _RECORD_FIELD_MAP:
                if (value := _extract(frame, mapping)) is not None:
                    result.samples.append(
                        TimeSeriesSampleCreate(
                            id=uuid4(),
                            user_id=user_id,
                            data_source_id=data_source_id,
                            source=source,
                            recorded_at=ts,
                            zone_offset=None,
                            value=value,
                            series_type=mapping.series_type,
                        )
                    )

    result.developer_fields_found = sorted(dev_fields_seen)
    logger.debug("FIT parsed: %d samples, dev_fields=%s", len(result.samples), result.developer_fields_found or "none")
    return result


def _timestamp(frame: fitdecode.FitDataMessage) -> datetime | None:
    try:
        ts = frame.get_value("timestamp")
    except KeyError:
        return None
    if not isinstance(ts, datetime):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _extract(frame: fitdecode.FitDataMessage, mapping: _FieldMapping) -> Decimal | None:
    for field_name in mapping.fit_fields:
        try:
            raw = frame.get_value(field_name)
            if raw is None:
                continue
            v = float(raw)
        except (KeyError, TypeError, ValueError):
            continue
        return mapping.transform(v) if mapping.transform else Decimal(str(v))
    return None
