"""Generic ANT+ FIT file parser — provider-agnostic (Garmin, Polar, Suunto, etc.)."""

import io
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
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
    _FieldMapping(("enhanced_altitude", "altitude"), SeriesType.elevation),
    _FieldMapping(("position_lat",), SeriesType.latitude, _scale(_SEMICIRCLES_TO_DEGREES)),
    _FieldMapping(("position_long",), SeriesType.longitude, _scale(_SEMICIRCLES_TO_DEGREES)),
    _FieldMapping(("temperature",), SeriesType.air_temperature),
    # fitdecode auto-applies scale=100 for these fields; value arrives already in percent
    _FieldMapping(("vertical_ratio",), SeriesType.running_vertical_ratio),
    _FieldMapping(("stance_time_balance",), SeriesType.running_stance_time_balance),
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class FitParseResult:
    samples: list[TimeSeriesSampleCreate] = field(default_factory=list)
    segments: list[dict] = field(default_factory=list)
    developer_fields_found: list[str] = field(default_factory=list)


def parse_fit_file(
    data: bytes,
    user_id: UUID,
    data_source_id: UUID | None = None,
    source: str | None = None,
) -> FitParseResult:
    result = FitParseResult()
    dev_fields_seen: set[str] = set()
    lap_index = split_index = length_index = 0

    with fitdecode.FitReader(io.BytesIO(data)) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue

            if frame.name == "record":
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

            elif frame.name == "lap":
                seg = _extract_lap(frame, lap_index)
                if seg.get("elapsed_seconds") is not None:
                    result.segments.append(seg)
                lap_index += 1

            elif frame.name == "split":
                seg = _extract_split(frame, split_index)
                if seg.get("elapsed_seconds") is not None:
                    result.segments.append(seg)
                split_index += 1

            elif frame.name == "length":
                seg = _extract_length(frame, length_index)
                if seg.get("elapsed_seconds") is not None:
                    result.segments.append(seg)
                length_index += 1

    result.developer_fields_found = sorted(dev_fields_seen)
    logger.debug(
        "FIT parsed: %d samples, %d segments, dev_fields=%s",
        len(result.samples),
        len(result.segments),
        result.developer_fields_found or "none",
    )
    return result


# ---------------------------------------------------------------------------
# Segment extraction helpers
# ---------------------------------------------------------------------------


def _field_val(frame: fitdecode.FitDataMessage, name: str) -> Any:
    try:
        v = frame.get_value(name)
        return v if v is not None else None
    except KeyError:
        return None


def _r2(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _iso(v: Any) -> str | None:
    if not isinstance(v, datetime):
        return None
    ts = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return ts.isoformat()


def _copy(seg: dict, frame: fitdecode.FitDataMessage, fit_name: str, out_name: str, scale: float = 1.0) -> None:
    v = _field_val(frame, fit_name)
    if v is not None:
        seg[out_name] = _r2(float(v) * scale)


def _extract_lap(frame: fitdecode.FitDataMessage, index: int) -> dict:
    seg: dict = {
        "kind": "lap",
        "index": index,
        "start_time": _iso(_field_val(frame, "start_time")),
        "elapsed_seconds": _r2(_field_val(frame, "total_elapsed_time")),
    }
    _copy(seg, frame, "total_distance", "distance_meters")
    _copy(seg, frame, "avg_heart_rate", "avg_heart_rate")
    _copy(seg, frame, "max_heart_rate", "max_heart_rate")
    _copy(seg, frame, "avg_speed", "avg_speed")
    _copy(seg, frame, "max_speed", "max_speed")
    _copy(seg, frame, "avg_power", "avg_power")
    _copy(seg, frame, "max_power", "max_power")
    _copy(seg, frame, "normalized_power", "normalized_power")
    _copy(seg, frame, "avg_cadence", "avg_cadence")
    _copy(seg, frame, "total_strides", "total_strides")
    _copy(seg, frame, "total_ascent", "total_ascent")
    _copy(seg, frame, "total_descent", "total_descent")
    # FIT stores these in mm; store as cm
    _copy(seg, frame, "avg_vertical_oscillation", "avg_vertical_oscillation", 0.1)
    _copy(seg, frame, "avg_step_length", "avg_step_length", 0.1)
    # fitdecode auto-applies scale for these (already in %)
    _copy(seg, frame, "avg_vertical_ratio", "avg_vertical_ratio")
    _copy(seg, frame, "avg_stance_time", "avg_stance_time")
    _copy(seg, frame, "avg_stance_time_balance", "avg_stance_time_balance")
    return {k: v for k, v in seg.items() if v is not None}


def _extract_split(frame: fitdecode.FitDataMessage, index: int) -> dict:
    seg: dict = {
        "kind": "split",
        "index": index,
        "start_time": _iso(_field_val(frame, "start_time")),
        "elapsed_seconds": _r2(_field_val(frame, "total_elapsed_time")),
    }
    _copy(seg, frame, "total_distance", "distance_meters")
    _copy(seg, frame, "avg_speed", "avg_speed")
    split_type = _field_val(frame, "split_type")
    if split_type is not None:
        seg["split_type"] = str(split_type)
    return {k: v for k, v in seg.items() if v is not None}


def _extract_length(frame: fitdecode.FitDataMessage, index: int) -> dict:
    seg: dict = {
        "kind": "length",
        "index": index,
        "start_time": _iso(_field_val(frame, "start_time")),
        "elapsed_seconds": _r2(_field_val(frame, "total_elapsed_time")),
    }
    _copy(seg, frame, "total_strokes", "total_strokes")
    _copy(seg, frame, "avg_speed", "avg_speed")
    swim_stroke = _field_val(frame, "swim_stroke")
    if swim_stroke is not None:
        seg["swim_stroke"] = str(swim_stroke)
    length_type = _field_val(frame, "length_type")
    if length_type is not None:
        seg["length_type"] = str(length_type)
    return {k: v for k, v in seg.items() if v is not None}


# ---------------------------------------------------------------------------
# Record message helpers
# ---------------------------------------------------------------------------


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
