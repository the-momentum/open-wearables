from datetime import datetime
from decimal import Decimal, InvalidOperation
from logging import getLogger
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.inspection import inspect

from app.database import BaseDbModel

logger = getLogger(__name__)


def to_decimal(value: Any) -> Decimal | None:
    """Coerce a numeric value (often a string) to Decimal; None if not numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def as_int(value: Any) -> int | None:
    """Coerce a value to int; None if missing or not convertible (e.g. NaN/Infinity)."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return None


def as_float(value: Any) -> float | None:
    """Coerce a value to float; None if missing or not convertible. Zero is kept."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return None


def as_model[ModelT: BaseModel](model: type[ModelT], value: Any) -> ModelT | None:
    """Validate a raw mapping (e.g. a json_binary column) into a model; None if empty or malformed."""
    if not value:
        return None
    try:
        return model.model_validate(value)
    except ValidationError:
        logger.warning("Discarding malformed %s payload: %r", model.__name__, value, exc_info=True)
        return None


def as_dict_list(value: Any) -> list[dict] | None:
    """Coerce a raw json_binary array (e.g. workout segments) to objects; None if empty or malformed."""
    if not isinstance(value, list):
        return None
    return [item for item in value if isinstance(item, dict)] or None


def minutes_to_seconds(minutes: int | None) -> int | None:
    return minutes * 60 if minutes is not None else None


_KCAL_PER_KJ = Decimal("0.239006")  # 1 kcal = 4.184 kJ


def kilojoules_to_kcal(kilojoules: Any) -> Decimal | None:
    """Convert kilojoules to kilocalories; None if not numeric."""
    kj = to_decimal(kilojoules)
    return kj * _KCAL_PER_KJ if kj is not None else None


def base_to_dict(instance: BaseDbModel) -> dict[str, str | None]:
    """Function to convert SQLALchemy Base model into dict."""
    b2d = {}
    for column in inspect(instance).mapper.column_attrs:
        value = getattr(instance, column.key)

        if isinstance(value, (datetime)):
            value = value.isoformat()

        b2d[column.key] = value

    return b2d
